"""RAG experience capture integration tests, independent of AstrBot runtime."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))


class _FakeProviderType:
    CHAT_COMPLETION = "chat_completion"


sys.modules.setdefault("astrbot", types.ModuleType("astrbot"))
sys.modules.setdefault("astrbot.core", types.ModuleType("astrbot.core"))
sys.modules.setdefault("astrbot.core.provider", types.ModuleType("astrbot.core.provider"))
_entities = types.ModuleType("astrbot.core.provider.entities")
_entities.ProviderType = _FakeProviderType
sys.modules["astrbot.core.provider.entities"] = _entities

from adapters import AstrBotAdapter
from config import normalize_config
from rag_experience import RagExperienceService
from rails import GuardrailPipeline
from state import MemoryStateStore


class _Event:
    def __init__(self) -> None:
        self.message_str = "matched request"
        self.message_outline = ""
        self.command_name = ""
        self.unified_msg_origin = "platform:message:session"
        self.platform_id = "platform"
        self.platform_name = "platform"
        self.sender_id = "sender"
        self.extras: dict[str, object] = {}
        self.is_at_or_wake_command = True
        self.private = False

    def get_message_str(self):
        return self.message_str

    def get_message_outline(self):
        return self.message_outline

    def get_platform_id(self):
        return self.platform_id

    def get_platform_name(self):
        return self.platform_name

    def get_sender_id(self):
        return self.sender_id

    def is_private_chat(self):
        return self.private

    def is_admin(self):
        return False

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)


class _KBManager:
    async def get_kb_by_name(self, name):
        return types.SimpleNamespace(kb=types.SimpleNamespace(kb_id=name, kb_name=name))

    async def retrieve(self, **_kwargs):
        return {
            "results": [
                {
                    "content": "first result",
                    "score": 0.72,
                    "kb_id": "kb-low",
                    "kb_name": "low-kb",
                    "doc_id": "doc-low",
                    "doc_name": "low.md",
                },
                {
                    "content": "highest result",
                    "score": 0.93,
                    "kb_id": "kb-high",
                    "kb_name": "high-kb",
                    "doc_id": "doc-high",
                    "doc_name": "high.md",
                },
            ]
        }


class _Context:
    def __init__(self) -> None:
        self.kb_manager = _KBManager()


class _ScorelessKBManager(_KBManager):
    async def retrieve(self, **_kwargs):
        return {
            "results": [
                {
                    "content": "compatibility result without a score",
                    "kb_id": "kb-scoreless",
                    "kb_name": "scoreless-kb",
                }
            ]
        }


class _ScorelessContext(_Context):
    def __init__(self) -> None:
        self.kb_manager = _ScorelessKBManager()


class _FailingExperienceService:
    async def capture_match(self, **_kwargs):
        raise RuntimeError("storage unavailable")


_UNSET = object()


def _config(*, min_score=0.7, experience_candidate_threshold=_UNSET):
    rule = {
        "__template_key": "rag_judge",
        "rule_id": "rag_policy",
        "knowledge_bases": ["low-kb", "high-kb"],
        "min_score": min_score,
        "action_on_hit": "observe",
    }
    if experience_candidate_threshold is not _UNSET:
        rule["experience_candidate_threshold"] = experience_candidate_threshold
    return normalize_config(
        {
            "input_rail": {
                "rule_list": [rule]
            }
        }
    )


class RagExperienceRuntimeTests(unittest.TestCase):
    def test_adapter_preserves_object_result_source_metadata(self) -> None:
        adapter = AstrBotAdapter(_Context())
        object_result = types.SimpleNamespace(
            content="object result",
            score=0.88,
            metadata={
                "kb_id": "object-kb-id",
                "kb_name": "object-kb",
                "doc_id": "object-doc-id",
                "doc_name": "object.md",
            },
        )

        evidence = adapter._normalize_kb_evidence([object_result], 5)

        self.assertEqual(evidence[0]["metadata"]["kb_name"], "object-kb")
        self.assertEqual(evidence[0]["metadata"]["doc_name"], "object.md")

    def test_matched_rag_captures_highest_source_once(self) -> None:
        service = RagExperienceService(MemoryStateStore())
        event = _Event()
        pipeline = GuardrailPipeline(
            _config(),
            AstrBotAdapter(_Context()),
            rag_experience=service,
        )

        context = asyncio.run(pipeline.run_message_input(event))
        listed = asyncio.run(service.list_records())
        asyncio.run(pipeline.run_message_route(event))
        listed_after_route = asyncio.run(service.list_records())

        self.assertTrue(context.results["rag_policy"].matched)
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0]["source_kb_name"], "high-kb")
        self.assertEqual(listed_after_route.total, 1)

    def test_blank_candidate_threshold_keeps_unmatched_result_out_of_experience(self) -> None:
        service = RagExperienceService(MemoryStateStore())
        pipeline = GuardrailPipeline(
            _config(min_score=0.95),
            AstrBotAdapter(_Context()),
            rag_experience=service,
        )

        context = asyncio.run(pipeline.run_message_input(_Event()))
        listed = asyncio.run(service.list_records())

        self.assertFalse(context.results["rag_policy"].matched)
        self.assertEqual(listed.total, 0)

    def test_blank_candidate_threshold_keeps_legacy_scoreless_match_behavior(self) -> None:
        service = RagExperienceService(MemoryStateStore())
        pipeline = GuardrailPipeline(
            _config(),
            AstrBotAdapter(_ScorelessContext()),
            rag_experience=service,
        )

        context = asyncio.run(pipeline.run_message_input(_Event()))
        listed = asyncio.run(service.list_records())

        self.assertTrue(context.results["rag_policy"].matched)
        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0]["candidate_reason"], "matched")

    def test_score_candidate_threshold_records_high_score_without_a_match(self) -> None:
        service = RagExperienceService(MemoryStateStore())
        pipeline = GuardrailPipeline(
            _config(min_score=0.95, experience_candidate_threshold=0.85),
            AstrBotAdapter(_Context()),
            rag_experience=service,
        )

        context = asyncio.run(pipeline.run_message_input(_Event()))
        listed = asyncio.run(service.list_records())

        self.assertFalse(context.results["rag_policy"].matched)
        self.assertEqual(listed.total, 1)
        detail = asyncio.run(service.get_record(listed.items[0]["record_id"]))
        self.assertTrue(detail.found)
        self.assertFalse(detail.record["matched"])
        self.assertEqual(detail.record["candidate_reason"], "score_threshold")
        self.assertEqual(detail.record["source_score"], 0.93)

    def test_zero_candidate_threshold_records_any_finite_score(self) -> None:
        service = RagExperienceService(MemoryStateStore())
        pipeline = GuardrailPipeline(
            _config(min_score=0.95, experience_candidate_threshold=0),
            AstrBotAdapter(_Context()),
            rag_experience=service,
        )

        asyncio.run(pipeline.run_message_input(_Event()))
        listed = asyncio.run(service.list_records())

        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0]["candidate_reason"], "score_threshold")

    def test_zero_candidate_threshold_keeps_scoreless_compatibility_match(self) -> None:
        service = RagExperienceService(MemoryStateStore())
        pipeline = GuardrailPipeline(
            _config(experience_candidate_threshold=0),
            AstrBotAdapter(_ScorelessContext()),
            rag_experience=service,
        )

        asyncio.run(pipeline.run_message_input(_Event()))
        listed = asyncio.run(service.list_records())

        self.assertEqual(listed.total, 1)
        self.assertEqual(listed.items[0]["candidate_reason"], "matched")

    def test_experience_capture_failure_is_fail_open(self) -> None:
        event = _Event()
        pipeline = GuardrailPipeline(
            _config(),
            AstrBotAdapter(_Context()),
            rag_experience=_FailingExperienceService(),
        )

        context = asyncio.run(pipeline.run_message_input(event))

        self.assertTrue(context.results["rag_policy"].matched)
        self.assertFalse(context.input_blocked)
        self.assertTrue(any("rag experience capture failed" in item for item in context.warnings))


if __name__ == "__main__":
    unittest.main()
