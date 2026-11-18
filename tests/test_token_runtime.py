"""Runtime tests for the adapter usage sink (v0.10.0)."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from adapters import AstrBotAdapter, RetryRequestSnapshot


class _Usage:
    input_other = 100
    input_cached = 20
    output = 50

    @property
    def total(self):
        return 170


class _Response:
    def __init__(self):
        self.usage = _Usage()
        self.role = "assistant"
        self.completion_text = "review text"


class _Event:
    unified_msg_origin = "platform:group:1"


class _Context:
    def __init__(self):
        self.kb_manager = _KbManager()

    async def llm_generate(self, **kwargs):
        return _Response()


class _KbManager:
    def __init__(self):
        self.fail = False

    async def retrieve(self, **kwargs):
        if self.fail:
            raise RuntimeError("kb down")
        return [{"text": "evidence", "score": 0.9, "kb_name": "kb"}]


class _Provider:
    async def text_chat(self, **kwargs):
        return _Response()


class AdapterUsageSinkTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        async def sink(**kwargs):
            self.calls.append(kwargs)

        self.context = _Context()
        self.adapter = AstrBotAdapter(self.context)
        self.adapter.set_usage_sink(sink)
        self.event = _Event()

    def test_review_call_reports_usage_with_review_task(self):
        async def run():
            with patch.object(
                self.adapter,
                "_resolve_chat_provider_id",
                new=AsyncMock(return_value="p1"),
            ), patch.object(self.adapter, "_provider_exists", return_value=True):
                return await self.adapter.request_llm_text(
                    self.event,
                    provider_id="",
                    prompt="user prompt",
                    system_prompt="system prompt",
                )

        result = asyncio.run(run())
        self.assertTrue(result.success)
        self.assertEqual(len(self.calls), 1)
        call = self.calls[0]
        self.assertEqual(call["kind"], "llm")
        self.assertEqual(call["task"], "guardrail_review")
        self.assertEqual(call["provider_id"], "p1")
        self.assertTrue(call["success"])
        self.assertIsInstance(call["response"], _Response)
        self.assertIn("system prompt", call["prompt"])
        self.assertEqual(call["completion"], "review text")

    def test_recheck_call_uses_recheck_task(self):
        async def run():
            with patch.object(
                self.adapter,
                "_resolve_chat_provider_id",
                new=AsyncMock(return_value="p1"),
            ), patch.object(self.adapter, "_provider_exists", return_value=True):
                return await self.adapter.request_llm_text(
                    self.event,
                    provider_id="p1",
                    prompt="p",
                    system_prompt="s",
                    purpose="recheck",
                )

        asyncio.run(run())
        self.assertEqual(self.calls[0]["task"], "guardrail_recheck")

    def test_failed_review_reports_attempt_without_usage(self):
        async def run():
            with patch.object(
                self.adapter,
                "_resolve_chat_provider_id",
                new=AsyncMock(return_value="p1"),
            ), patch.object(self.adapter, "_provider_exists", return_value=True), patch.object(
                self.context, "llm_generate", side_effect=RuntimeError("boom")
            ):
                return await self.adapter.request_llm_text(
                    self.event, provider_id="p1", prompt="p", system_prompt="s"
                )

        result = asyncio.run(run())
        self.assertFalse(result.success)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.calls[0]["success"])
        self.assertIsNone(self.calls[0]["response"])
        self.assertIn("RuntimeError", self.calls[0]["error"])

    def test_unavailable_provider_is_not_counted_as_a_call(self):
        async def run():
            with patch.object(
                self.adapter,
                "_resolve_chat_provider_id",
                new=AsyncMock(return_value=""),
            ):
                return await self.adapter.request_llm_text(
                    self.event, provider_id="", prompt="p", system_prompt="s"
                )

        result = asyncio.run(run())
        self.assertFalse(result.success)
        self.assertEqual(self.calls, [])

    def test_retry_call_reports_retry_task_and_usage(self):
        snapshot = RetryRequestSnapshot(
            prompt="p",
            system_prompt="s",
            contexts=(),
            extra_user_text_parts=(),
            provider_id="p1",
            provider_source="provider_request",
        )

        async def run():
            with patch.object(
                self.adapter, "_get_provider_by_id", return_value=_Provider()
            ):
                return await self.adapter.regenerate_llm_text(
                    self.event, snapshot, "retry prompt", timeout_seconds=5
                )

        result = asyncio.run(run())
        self.assertTrue(result.success)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["task"], "guardrail_retry")
        self.assertIsInstance(self.calls[0]["response"], _Response)
        self.assertIn("s\n\nretry prompt", self.calls[0]["prompt"])

    def test_retrieval_reports_counts_without_tokens(self):
        async def run():
            with patch.object(
                self.adapter,
                "_resolve_knowledge_bases",
                new=AsyncMock(return_value=(["kb"], [])),
            ):
                return await self.adapter.search_knowledge_base(
                    ["kb"], query="q", top_k=3, event=self.event
                )

        result = asyncio.run(run())
        self.assertTrue(result.success)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["kind"], "retrieval")
        self.assertTrue(self.calls[0]["success"])

    def test_failed_retrieval_is_reported(self):
        self.context.kb_manager.fail = True

        async def run():
            with patch.object(
                self.adapter,
                "_resolve_knowledge_bases",
                new=AsyncMock(return_value=(["kb"], [])),
            ):
                return await self.adapter.search_knowledge_base(
                    ["kb"], query="q", top_k=3, event=self.event
                )

        result = asyncio.run(run())
        self.assertFalse(result.success)
        self.assertEqual(self.calls[0]["kind"], "retrieval")
        self.assertFalse(self.calls[0]["success"])

    def test_sink_failure_does_not_break_the_call(self):
        async def bad_sink(**kwargs):
            raise RuntimeError("sink down")

        self.adapter.set_usage_sink(bad_sink)

        async def run():
            with patch.object(
                self.adapter,
                "_resolve_chat_provider_id",
                new=AsyncMock(return_value="p1"),
            ), patch.object(self.adapter, "_provider_exists", return_value=True):
                return await self.adapter.request_llm_text(
                    self.event, provider_id="p1", prompt="p", system_prompt="s"
                )

        result = asyncio.run(run())
        self.assertTrue(result.success)

    def test_no_sink_keeps_legacy_behavior(self):
        adapter = AstrBotAdapter(self.context)

        async def run():
            with patch.object(
                adapter,
                "_resolve_chat_provider_id",
                new=AsyncMock(return_value="p1"),
            ), patch.object(adapter, "_provider_exists", return_value=True):
                return await adapter.request_llm_text(
                    self.event, provider_id="p1", prompt="p", system_prompt="s"
                )

        result = asyncio.run(run())
        self.assertTrue(result.success)
        self.assertNotIn("_usage_attempted", result.metadata)


if __name__ == "__main__":
    unittest.main()
