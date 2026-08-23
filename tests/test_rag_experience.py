"""Independent tests for local RAG experience records."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from rag_experience import RagExperienceService, select_best_evidence_source
from state import MemoryStateStore


class RagExperienceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1_700_000_000
        self.ids = iter(("record-a", "record-b", "record-c", "record-d"))
        self.service = RagExperienceService(
            MemoryStateStore(),
            clock=lambda: self.now,
            record_id_factory=lambda: next(self.ids),
        )

    def _capture(self):
        return asyncio.run(
            self.service.capture_match(
                rail="input_rail",
                rule_id="rag_policy",
                content="A matched user request",
                evidence=[
                    {
                        "text": "lower source",
                        "score": 0.72,
                        "metadata": {"kb_name": "lower", "doc_name": "a.md"},
                    },
                    {
                        "text": "winning source",
                        "score": 0.91,
                        "metadata": {
                            "kb_id": "kb-2",
                            "kb_name": "winning",
                            "doc_id": "doc-2",
                            "doc_name": "winner.md",
                        },
                    },
                ],
            )
        )

    def test_capture_uses_highest_score_source(self) -> None:
        result = self._capture()

        self.assertTrue(result.success)
        self.assertEqual(result.record["source_kb_name"], "winning")
        self.assertEqual(result.record["source_doc_id"], "doc-2")
        self.assertEqual(result.record["source_score"], 0.91)
        self.assertEqual(result.record["title"], "winner.md")

    def test_capture_without_stable_source_remains_viewable(self) -> None:
        result = asyncio.run(
            self.service.capture_match(
                rail="input_rail",
                rule_id="rag_policy",
                content="matched",
                evidence=[{"text": "scoreless", "score": None, "metadata": {}}],
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.record["source_kb_name"], "")
        detail = asyncio.run(self.service.get_record(result.record["record_id"]))
        self.assertTrue(detail.found)

    def test_edit_and_delete_require_matching_revision(self) -> None:
        captured = self._capture().record
        conflict = asyncio.run(
            self.service.update_record(
                captured["record_id"],
                expected_revision=99,
                title="Edited title",
                content="Edited content",
            )
        )
        self.assertTrue(conflict.conflict)
        updated = asyncio.run(
            self.service.update_record(
                captured["record_id"],
                expected_revision=captured["record_revision"],
                title="Edited title",
                content="Edited content",
            )
        )
        self.assertTrue(updated.success)
        self.assertEqual(updated.record["record_revision"], 2)
        self.assertEqual(updated.record["content"], "Edited content")

        stale_delete = asyncio.run(
            self.service.delete_record(
                captured["record_id"], expected_revision=captured["record_revision"]
            )
        )
        self.assertTrue(stale_delete.conflict)
        deleted = asyncio.run(
            self.service.delete_record(
                captured["record_id"], expected_revision=updated.record["record_revision"]
            )
        )
        self.assertTrue(deleted.success)
        self.assertTrue(deleted.found)
        self.assertFalse(
            asyncio.run(self.service.get_record(captured["record_id"])).found
        )

    def test_list_returns_summary_not_full_content(self) -> None:
        self._capture()
        listed = asyncio.run(self.service.list_records(query="winning"))

        self.assertTrue(listed.success)
        self.assertEqual(listed.total, 1)
        self.assertNotIn("content", listed.items[0])
        self.assertIn("content_preview", listed.items[0])


class SourceSelectionTests(unittest.TestCase):
    def test_equal_scores_keep_first_retrieval_result(self) -> None:
        source = select_best_evidence_source(
            [
                {
                    "text": "first",
                    "score": 0.8,
                    "metadata": {"kb_name": "first-kb"},
                },
                {
                    "text": "second",
                    "score": 0.8,
                    "metadata": {"kb_name": "second-kb"},
                },
            ]
        )

        self.assertEqual(source["source_kb_name"], "first-kb")

    def test_does_not_guess_source_when_top_result_has_no_kb_name(self) -> None:
        source = select_best_evidence_source(
            [
                {"text": "top", "score": 0.9, "metadata": {}},
                {
                    "text": "lower",
                    "score": 0.8,
                    "metadata": {"kb_name": "lower-kb"},
                },
            ]
        )

        self.assertEqual(source["source_kb_name"], "")


if __name__ == "__main__":
    unittest.main()
