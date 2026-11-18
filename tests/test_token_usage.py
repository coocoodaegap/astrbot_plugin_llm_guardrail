"""Tests for the v0.10.0 Token usage ledger."""

import asyncio
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from state import MemoryStateStore
from token_usage import TokenUsageService, estimate_token_count


@dataclass
class Usage:
    input_other: int = 0
    input_cached: int = 0
    output: int = 0

    @property
    def total(self) -> int:
        return self.input_other + self.input_cached + self.output

    @property
    def input(self) -> int:
        return self.input_other + self.input_cached


class Resp:
    def __init__(self, usage=None, role="assistant", text="answer"):
        if usage is not None:
            self.usage = usage
        self.role = role
        self.completion_text = text


class Dumpable:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return dict(self._payload)


class RawResp:
    def __init__(self, raw_completion=None, raw_response=None):
        self.raw_completion = raw_completion
        self.raw_response = raw_response
        self.role = "assistant"
        self.completion_text = "answer"


class CountingStore(MemoryStateStore):
    def __init__(self):
        super().__init__()
        self.set_calls = 0
        self.deleted = []

    async def set(self, namespace, key, value):
        self.set_calls += 1
        await super().set(namespace, key, value)

    async def delete(self, namespace, key):
        self.deleted.append((namespace, key))
        await super().delete(namespace, key)


class FailingStore(MemoryStateStore):
    async def set(self, namespace, key, value):
        raise RuntimeError("storage is down")


class TokenUsageServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = CountingStore()
        self.now = 1_760_000_000
        self.service = TokenUsageService(self.store, clock=lambda: self.now)

    def record(self, **kwargs):
        return asyncio.run(self.service.record(**kwargs))

    def snapshot(self, **kwargs):
        return asyncio.run(self.service.snapshot(**kwargs))

    # -- extraction -----------------------------------------------------
    def test_extracts_astrbot_token_usage(self):
        result = self.record(
            task="main_reply",
            umo="u1",
            run_id="r1",
            response=Resp(Usage(input_other=100, input_cached=20, output=50)),
        )
        self.assertTrue(result.recorded)
        self.assertEqual(result.total_tokens, 170)
        self.assertEqual(result.usage_source, "final_response")
        snapshot = self.snapshot()
        self.assertEqual(snapshot.totals["prompt_tokens"], 120)
        self.assertEqual(snapshot.totals["completion_tokens"], 50)
        self.assertEqual(snapshot.totals["cached_tokens"], 20)
        self.assertEqual(snapshot.totals["total_tokens"], 170)
        self.assertEqual(
            snapshot.totals["total_tokens"],
            snapshot.totals["prompt_tokens"] + snapshot.totals["completion_tokens"],
        )

    def test_extracts_openai_completion_via_model_dump(self):
        raw = Dumpable(
            {
                "prompt_tokens": 120,
                "completion_tokens": 50,
                "total_tokens": 170,
                "prompt_tokens_details": {"cached_tokens": 20},
            }
        )
        result = self.record(task="main_reply", run_id="r1", response=RawResp(raw))
        self.assertEqual(result.total_tokens, 170)
        snapshot = self.snapshot()
        self.assertEqual(snapshot.totals["cached_tokens"], 20)

    def test_extracts_gemini_usage_metadata(self):
        class Metadata:
            prompt_token_count = 200
            candidates_token_count = 40
            thoughts_token_count = 10
            cached_content_token_count = 50

        class Container:
            usage_metadata = Metadata()

        result = self.record(
            task="main_reply",
            run_id="r1",
            response=RawResp(raw_response=Container()),
        )
        self.assertEqual(result.total_tokens, 250)
        self.assertEqual(self.snapshot().totals["completion_tokens"], 50)

    def test_total_invariants_are_normalized(self):
        smaller = self.record(
            task="main_reply",
            run_id="small",
            response=Resp({"prompt_tokens": 100, "completion_tokens": 70, "total_tokens": 100}),
        )
        self.assertEqual(smaller.total_tokens, 170)
        larger = self.record(
            task="main_reply",
            run_id="large",
            response=Resp({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 200}),
        )
        self.assertEqual(larger.total_tokens, 200)
        snapshot = self.snapshot()
        self.assertEqual(
            snapshot.totals["total_tokens"],
            snapshot.totals["prompt_tokens"] + snapshot.totals["completion_tokens"],
        )

    def test_estimates_when_usage_is_missing(self):
        result = self.record(
            task="main_reply",
            run_id="r1",
            prompt="hello world",
            completion="answer",
            response=Resp(),
        )
        self.assertTrue(result.estimated)
        self.assertEqual(result.usage_source, "estimated")
        self.assertGreater(result.total_tokens, 0)
        snapshot = self.snapshot()
        self.assertEqual(snapshot.totals["estimated_tokens"], result.total_tokens)

    def test_disabling_estimation_counts_missing_usage(self):
        result = self.record(
            task="main_reply",
            run_id="r1",
            prompt="hello",
            completion="answer",
            response=Resp(),
            settings={"estimate_when_usage_missing": False},
        )
        self.assertEqual(result.total_tokens, 0)
        snapshot = self.snapshot(settings={"estimate_when_usage_missing": False})
        self.assertEqual(snapshot.unaccounted["missing_usage"], 1)
        self.assertEqual(snapshot.totals["estimated_tokens"], 0)

    # -- accounting rules ----------------------------------------------
    def test_error_role_is_counted_without_estimation(self):
        result = self.record(
            task="main_reply",
            run_id="r1",
            completion="provider exploded",
            response=Resp(role="err", text="provider exploded"),
            success=False,
        )
        self.assertEqual(result.total_tokens, 0)
        snapshot = self.snapshot()
        self.assertEqual(snapshot.totals["calls"], 1)
        self.assertEqual(snapshot.totals["errors"], 1)
        self.assertEqual(snapshot.unaccounted["error_no_usage"], 1)

    def test_aborted_run_is_counted_without_estimation(self):
        self.record(
            task="main_reply",
            run_id="r1",
            completion="partial",
            response=Resp(),
            aborted=True,
        )
        snapshot = self.snapshot()
        self.assertEqual(snapshot.unaccounted["aborted_partial"], 1)
        self.assertEqual(snapshot.totals["total_tokens"], 0)

    def test_run_usage_wins_over_final_response(self):
        result = self.record(
            task="main_reply",
            run_id="r1",
            response=Resp(Usage(input_other=1, output=1)),
            run_usage=Usage(input_other=1000, input_cached=0, output=100),
        )
        self.assertEqual(result.usage_source, "agent_stats")
        self.assertEqual(result.total_tokens, 1100)

    def test_duplicate_fingerprint_is_skipped(self):
        dedupe = set()
        usage = Usage(input_other=10, output=5)
        first = self.record(
            task="main_reply", run_id="r1", response=Resp(usage), dedupe_set=dedupe
        )
        second = self.record(
            task="main_reply", run_id="r1", response=Resp(usage), dedupe_set=dedupe
        )
        self.assertTrue(first.recorded)
        self.assertTrue(second.duplicate)
        self.assertFalse(second.recorded)
        self.assertEqual(self.snapshot().totals["calls"], 1)

    def test_disabled_service_writes_nothing(self):
        result = self.record(
            task="main_reply",
            run_id="r1",
            response=Resp(Usage(input_other=1, output=1)),
            settings={"enabled": False},
        )
        self.assertFalse(result.recorded)
        self.assertEqual(self.store.set_calls, 0)

    def test_each_record_writes_at_most_two_keys(self):
        before = self.store.set_calls
        self.record(
            task="main_reply",
            umo="u1",
            run_id="r1",
            response=Resp(Usage(input_other=1, output=1)),
        )
        self.assertEqual(self.store.set_calls - before, 2)

    # -- scopes and storage --------------------------------------------
    def test_global_and_umo_scopes_aggregate_consistently(self):
        self.record(task="main_reply", umo="u1", run_id="r1", response=Resp(Usage(10, 0, 5)))
        self.record(task="main_reply", umo="u2", run_id="r2", response=Resp(Usage(20, 0, 5)))
        global_snapshot = self.snapshot()
        umo_snapshot = self.snapshot(scope="umo", umo="u1")
        self.assertEqual(global_snapshot.totals["total_tokens"], 40)
        self.assertEqual(umo_snapshot.totals["total_tokens"], 15)
        self.assertEqual(umo_snapshot.recent, [])
        self.assertTrue(global_snapshot.recent)

    def test_recent_is_newest_first(self):
        self.record(task="main_reply", run_id="r1", response=Resp(Usage(1, 0, 1)))
        self.now += 10
        self.record(task="guardrail_review", run_id="r2", response=Resp(Usage(2, 0, 2)))
        recent = self.snapshot().recent
        self.assertEqual(recent[0]["task"], "guardrail_review")

    def test_day_buckets_are_pruned_by_retention(self):
        settings = {"retention_days": 1}
        self.record(
            task="main_reply",
            run_id="r1",
            response=Resp(Usage(1, 0, 1)),
            settings=settings,
        )
        self.now += 86_400
        self.record(
            task="main_reply",
            run_id="r2",
            response=Resp(Usage(2, 0, 2)),
            settings=settings,
        )
        snapshot = self.snapshot(days=7, settings=settings)
        self.assertEqual(len(snapshot.by_day), 1)
        self.assertEqual(snapshot.by_day[0]["total_tokens"], 4)

    def test_retrieval_calls_are_counted_separately(self):
        asyncio.run(self.service.record_retrieval(success=True, umo="u1"))
        asyncio.run(self.service.record_retrieval(success=False, umo="u1"))
        snapshot = self.snapshot()
        self.assertEqual(snapshot.other_calls["retrieval"], 2)
        self.assertEqual(snapshot.other_calls["retrieval_failed"], 1)
        self.assertEqual(snapshot.totals["total_tokens"], 0)

    def test_corrupt_ledger_is_tolerated(self):
        asyncio.run(
            self.store.set(
                "token_usage",
                "global",
                {"buckets": "broken", "totals": "broken", "recent": 5},
            )
        )
        result = self.record(
            task="main_reply", run_id="r1", response=Resp(Usage(3, 0, 1))
        )
        self.assertTrue(result.recorded)
        self.assertEqual(self.snapshot().totals["total_tokens"], 4)

    def test_storage_failure_never_raises(self):
        service = TokenUsageService(FailingStore(), clock=lambda: self.now)
        result = asyncio.run(
            service.record(task="main_reply", run_id="r1", response=Resp(Usage(1, 0, 1)))
        )
        self.assertFalse(result.success)
        self.assertFalse(result.recorded)

    def test_estimate_token_count_matches_documented_formula(self):
        self.assertEqual(estimate_token_count("abcd"), 1)
        self.assertEqual(estimate_token_count("中文"), 2)
        self.assertEqual(estimate_token_count(""), 0)


if __name__ == "__main__":
    unittest.main()
