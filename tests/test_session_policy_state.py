import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from session_lock import UmoLockManager
from session_policy_state import (
    SESSION_POLICY_STATE_NAMESPACE,
    SESSION_POLICY_STATE_TABLE_KEY,
    SessionPolicyStateService,
    umo_storage_key,
)
from state import MemoryStateStore


class _Clock:
    def __init__(self, now=100):
        self.now = now

    def __call__(self):
        return self.now


def _settings(**overrides):
    result = {
        "enabled": True,
        "state_ttl_seconds": 0,
        "max_entries": 500,
        "activity_log_limit": 50,
    }
    result.update(overrides)
    return result


def _signal(node_id="risk"):
    return {
        "rail": "input_rail",
        "node_id": node_id,
        "user_node_id": node_id,
        "template_key": "plain_keywords",
        "signal": {
            "value": True,
            "truthy": True,
            "payload": {"matched_text": "secret"},
        },
    }


class SessionPolicyStateServiceTests(unittest.TestCase):
    def _service(self, clock=None):
        return SessionPolicyStateService(
            MemoryStateStore(),
            session_locks=UmoLockManager(),
            clock=clock,
        )

    def test_records_blocked_policy_result_and_original_node_signal(self):
        async def run_case():
            service = self._service(_Clock(100))
            written = await service.record_phase(
                "qq:group:1",
                run_id="run-a",
                policy_id="safe-chat",
                snapshot_revision=7,
                started_at=90,
                phase="message_input",
                outcome="blocked",
                terminal_action={
                    "rail": "input_rail",
                    "source_kind": "rule",
                    "node_id": "risk",
                    "action": "block",
                    "target": "input",
                    "adapter_success": True,
                },
                rail_outcomes={"input_rail": {"outcome": "blocked"}},
                signals=[_signal()],
                settings=_settings(),
            )
            detail = await service.get_detail("qq:group:1", settings=_settings())
            return written, detail

        written, detail = asyncio.run(run_case())

        self.assertTrue(written.success)
        self.assertTrue(written.recorded)
        self.assertTrue(detail.found)
        result = detail.record["last_policy_result"]
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["terminal_action"]["node_id"], "risk")
        self.assertEqual(result["signals"][0]["signal"], _signal()["signal"])
        self.assertEqual(detail.record["activities"]["items"][0]["kind"], "policy_stage_completed")

    def test_route_candidate_and_request_observation_are_independent(self):
        async def run_case():
            service = self._service(_Clock(200))
            common = {
                "run_id": "run-a",
                "policy_id": "safe-chat",
                "snapshot_revision": 9,
                "started_at": 190,
                "outcome": "allowed",
                "terminal_action": None,
                "signals": [],
                "settings": _settings(),
            }
            await service.record_phase(
                "qq:group:1",
                phase="message_input",
                rail_outcomes={"input_rail": {"outcome": "completed"}},
                **common,
            )
            await service.record_phase(
                "qq:group:1",
                phase="message_route",
                rail_outcomes={"routing_rail": {"outcome": "completed"}},
                route_candidate={
                    "provider_id": "provider-a",
                    "model_id": "",
                    "source_route_node_id": "route-main",
                },
                **common,
            )
            await service.record_phase(
                "qq:group:1",
                phase="request",
                rail_outcomes={"request_rail": {"outcome": "completed"}},
                request_target_observation={
                    "provider_id": "provider-b",
                    "model_id": "model-b",
                    "source": "provider_request",
                },
                **common,
            )
            return await service.get_detail("qq:group:1", settings=_settings())

        detail = asyncio.run(run_case())

        candidate = detail.record["route_candidate"]
        observed = detail.record["last_request_target_observation"]
        self.assertEqual(candidate["provider_id"], "provider-a")
        self.assertEqual(candidate["mode"], "observe_only")
        self.assertEqual(candidate["run_id"], "run-a")
        self.assertEqual(observed["provider_id"], "provider-b")
        self.assertEqual(observed["model_id"], "model-b")
        self.assertEqual(observed["run_id"], "run-a")

    def test_late_foreign_phase_preserves_newer_result_but_keeps_independent_observations(self):
        async def run_case():
            service = self._service(_Clock(300))
            base = {
                "policy_id": "safe-chat",
                "snapshot_revision": 1,
                "started_at": 290,
                "phase": "message_input",
                "outcome": "allowed",
                "terminal_action": None,
                "rail_outcomes": {"input_rail": {"outcome": "completed"}},
                "signals": [],
                "settings": _settings(),
            }
            await service.record_phase("qq:group:1", run_id="run-old", **base)
            await service.record_phase("qq:group:1", run_id="run-new", **base)
            stale_candidate = await service.record_phase(
                "qq:group:1",
                run_id="run-old",
                policy_id="safe-chat",
                snapshot_revision=1,
                started_at=290,
                phase="message_route",
                outcome="allowed",
                terminal_action=None,
                rail_outcomes={"routing_rail": {"outcome": "completed"}},
                signals=[],
                settings=_settings(),
                route_candidate={
                    "provider_id": "provider-old",
                    "model_id": "",
                    "source_route_node_id": "route-old",
                },
            )
            stale_request = await service.record_phase(
                "qq:group:1",
                run_id="run-old",
                policy_id="safe-chat",
                snapshot_revision=1,
                started_at=290,
                phase="request",
                outcome="allowed",
                terminal_action=None,
                rail_outcomes={"request_rail": {"outcome": "completed"}},
                signals=[],
                settings=_settings(),
                request_target_observation={
                    "provider_id": "provider-old-request",
                    "model_id": "model-old",
                    "source": "provider_request",
                },
            )
            detail = await service.get_detail("qq:group:1", settings=_settings())
            return stale_candidate, stale_request, detail

        stale_candidate, stale_request, detail = asyncio.run(run_case())

        self.assertTrue(stale_candidate.success)
        self.assertTrue(stale_candidate.recorded)
        self.assertTrue(stale_request.success)
        self.assertTrue(stale_request.recorded)
        self.assertEqual(detail.record["last_policy_result"]["run_id"], "run-new")
        self.assertEqual(detail.record["route_candidate"]["run_id"], "run-old")
        self.assertEqual(
            detail.record["last_request_target_observation"]["provider_id"],
            "provider-old-request",
        )
        self.assertIn(
            "late_policy_stage_observed",
            [item["kind"] for item in detail.record["activities"]["items"]],
        )

    def test_activity_retention_ttl_and_capacity_are_bounded(self):
        async def run_case():
            clock = _Clock(100)
            service = self._service(clock)
            settings = _settings(activity_log_limit=2, max_entries=1)
            common = {
                "run_id": "run-a",
                "policy_id": "safe-chat",
                "snapshot_revision": 1,
                "started_at": 90,
                "outcome": "allowed",
                "terminal_action": None,
                "rail_outcomes": {"input_rail": {"outcome": "completed"}},
                "signals": [],
                "settings": settings,
            }
            await service.record_phase("qq:group:old", phase="message_input", **common)
            clock.now = 101
            await service.record_phase("qq:group:new", phase="message_input", **common)
            clock.now = 102
            await service.record_phase("qq:group:new", phase="message_route", **common)
            clock.now = 103
            await service.record_phase("qq:group:new", phase="request", **common)
            listed = await service.list_summaries(settings=settings)
            detail = await service.get_detail("qq:group:new", settings=settings)
            clock.now = 163
            expired = await service.list_summaries(
                settings=_settings(state_ttl_seconds=60, max_entries=1),
            )
            return listed, detail, expired

        listed, detail, expired = asyncio.run(run_case())

        self.assertEqual([item["umo"] for item in listed.items], ["qq:group:new"])
        self.assertEqual(len(detail.record["activities"]["items"]), 2)
        self.assertEqual(expired.total, 0)

    def test_list_query_handles_normalized_record_without_policy_result(self):
        async def run_case():
            store = MemoryStateStore()
            service = SessionPolicyStateService(
                store,
                session_locks=UmoLockManager(),
            )
            await store.set(
                SESSION_POLICY_STATE_NAMESPACE,
                SESSION_POLICY_STATE_TABLE_KEY,
                {
                    "schema_version": 1,
                    "table_revision": 0,
                    "records": {
                        umo_storage_key("qq:group:incomplete"): {
                            "umo": "qq:group:incomplete",
                            "last_policy_result": None,
                        }
                    },
                },
            )
            return await service.list_summaries(
                settings=_settings(),
                query="safe-chat",
            )

        listed = asyncio.run(run_case())

        self.assertTrue(listed.success)
        self.assertEqual(listed.total, 0)


if __name__ == "__main__":
    unittest.main()
