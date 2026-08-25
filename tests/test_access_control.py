import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from access_control import (
    ACCESS_CONTROL_NAMESPACE,
    ACCESS_CONTROL_TABLE_KEY,
    DECISION_BAN,
    DECISION_NONE,
    DECISION_PARDON,
    REASON_MANUAL_BAN,
    REASON_MANUAL_PARDON,
    AccessControlService,
    make_principal_identity,
)
from session_lock import PrincipalLockManager
from state import MemoryStateStore


class _Clock:
    def __init__(self, value=1_700_000_000):
        self.value = value

    def __call__(self):
        return self.value


class _YieldingMemoryStateStore(MemoryStateStore):
    """Force interleaving around point KV operations for registry race tests."""

    async def get(self, namespace, key, default=None):
        value = await super().get(namespace, key, default)
        await asyncio.sleep(0)
        return value

    async def set(self, namespace, key, value):
        await asyncio.sleep(0)
        await super().set(namespace, key, value)


class AccessControlServiceTests(unittest.TestCase):
    def _service(self, clock=None):
        return AccessControlService(
            MemoryStateStore(),
            principal_locks=PrincipalLockManager(),
            clock=clock,
        )

    def test_threshold_creates_temporary_automatic_ban(self):
        async def run_case():
            clock = _Clock()
            service = self._service(clock)
            principal = make_principal_identity("qq", "1001")
            settings = {
                "auto_blacklist_enabled": True,
                "blacklist_max_violations": 2,
                "blacklist_duration_minutes": 15,
            }
            first = await service.record_terminal_input_block(principal, settings)
            second = await service.record_terminal_input_block(principal, settings)
            record = await service.get_active_record(principal)
            admission = await service.admit(principal)
            return first, second, record, admission

        first, second, record, admission = asyncio.run(run_case())

        self.assertTrue(first.recorded)
        self.assertFalse(first.automatic_ban)
        self.assertTrue(second.recorded)
        self.assertTrue(second.automatic_ban)
        self.assertEqual(record["decision"], DECISION_BAN)
        self.assertEqual(record["violation_count"], 2)
        self.assertEqual(record["decision_expires_at"], 1_700_000_900)
        self.assertFalse(admission.allowed)

    def test_legacy_sender_id_record_is_not_read_as_a_user_id_record(self):
        async def run_case():
            store = MemoryStateStore()
            principal = make_principal_identity("qq", "1001")
            await store.set(
                ACCESS_CONTROL_NAMESPACE,
                ACCESS_CONTROL_TABLE_KEY,
                {
                    "schema_version": 1,
                    "table_revision": 1,
                    "records": {
                        principal.storage_key: {
                            "principal_id": "qq:1001",
                            "platform_id": "qq",
                            "sender_id": "1001",
                            "decision": DECISION_BAN,
                            "decision_expires_at": 0,
                        }
                    },
                },
            )
            service = AccessControlService(store, principal_locks=PrincipalLockManager())
            return await service.admit(principal), await service.get_active_record(principal)

        admission, record = asyncio.run(run_case())

        self.assertTrue(admission.allowed)
        self.assertIsNone(record)

    def test_concurrent_cross_umo_violations_are_not_lost(self):
        async def run_case():
            service = self._service()
            principal = make_principal_identity("qq", "same-user")
            settings = {
                "auto_blacklist_enabled": True,
                "blacklist_max_violations": 50,
                "blacklist_duration_minutes": -1,
            }
            results = await asyncio.gather(
                *(
                    service.record_terminal_input_block(principal, settings)
                    for _ in range(50)
                )
            )
            record = await service.get_active_record(principal)
            return results, record

        results, record = asyncio.run(run_case())

        self.assertEqual(sum(result.recorded for result in results), 50)
        self.assertEqual(sum(result.automatic_ban for result in results), 1)
        self.assertEqual(record["decision"], DECISION_BAN)
        self.assertEqual(record["violation_count"], 50)
        self.assertEqual(record["decision_expires_at"], 0)

    def test_separate_services_cannot_clobber_different_principal_records(self):
        async def run_case():
            store = _YieldingMemoryStateStore()
            first_service = AccessControlService(
                store,
                principal_locks=PrincipalLockManager(),
            )
            second_service = AccessControlService(
                store,
                principal_locks=PrincipalLockManager(),
            )
            first_principal = make_principal_identity("qq", "first-user")
            second_principal = make_principal_identity("qq", "second-user")
            settings = {
                "auto_blacklist_enabled": True,
                "blacklist_max_violations": 1,
                "blacklist_duration_minutes": -1,
            }
            await asyncio.gather(
                first_service.record_terminal_input_block(first_principal, settings),
                second_service.record_terminal_input_block(second_principal, settings),
            )
            records = await first_service.list_active_records()
            return records

        records = asyncio.run(run_case())

        self.assertTrue(records.success)
        self.assertEqual(
            {(record["platform_id"], record["user_id"]) for record in records.records},
            {("qq", "first-user"), ("qq", "second-user")},
        )

    def test_persisted_ban_is_visible_to_a_recreated_service(self):
        async def run_case():
            store = MemoryStateStore()
            principal = make_principal_identity("qq", "persisted-user")
            first_service = AccessControlService(
                store,
                principal_locks=PrincipalLockManager(),
            )
            saved = await first_service.set_manual_decision(
                principal,
                DECISION_BAN,
                -1,
                REASON_MANUAL_BAN,
            )
            recreated_service = AccessControlService(
                store,
                principal_locks=PrincipalLockManager(),
            )
            admission = await recreated_service.admit(principal)
            listed = await recreated_service.list_active_records()
            return saved, admission, listed

        saved, admission, listed = asyncio.run(run_case())

        self.assertTrue(saved.success)
        self.assertFalse(admission.allowed)
        self.assertEqual(len(listed.records), 1)
        self.assertEqual(listed.records[0]["decision_reason_code"], REASON_MANUAL_BAN)

    def test_pardon_blocks_automatic_updates_even_when_requests_race(self):
        async def run_case():
            service = self._service()
            principal = make_principal_identity("qq", "pardoned-user")
            saved = await service.set_manual_decision(
                principal,
                DECISION_PARDON,
                -1,
                REASON_MANUAL_PARDON,
            )
            results = await asyncio.gather(
                *(
                    service.record_terminal_input_block(
                        principal,
                        {
                            "auto_blacklist_enabled": True,
                            "blacklist_max_violations": 1,
                            "blacklist_duration_minutes": -1,
                        },
                    )
                    for _ in range(24)
                )
            )
            record = await service.get_active_record(principal)
            return saved, results, record

        saved, results, record = asyncio.run(run_case())

        self.assertTrue(saved.success)
        self.assertTrue(all(not result.recorded for result in results))
        self.assertEqual(record["decision"], DECISION_PARDON)
        self.assertEqual(record["violation_count"], 0)

    def test_temporary_decision_expiry_resets_old_count_before_new_violation(self):
        async def run_case():
            clock = _Clock(100)
            service = self._service(clock)
            principal = make_principal_identity("qq", "expiring-user")
            saved = await service.set_manual_decision(
                principal,
                DECISION_BAN,
                1,
                REASON_MANUAL_BAN,
            )
            clock.value = 160
            admission = await service.admit(principal)
            violation = await service.record_terminal_input_block(
                principal,
                {
                    "auto_blacklist_enabled": True,
                    "blacklist_max_violations": 2,
                    "blacklist_duration_minutes": -1,
                },
            )
            active = await service.get_active_record(principal)
            return saved, admission, violation, active

        saved, admission, violation, active = asyncio.run(run_case())

        self.assertTrue(saved.success)
        self.assertTrue(admission.allowed)
        self.assertEqual(admission.decision, DECISION_NONE)
        self.assertTrue(violation.recorded)
        self.assertEqual(violation.violation_count, 1)
        self.assertIsNone(active)

    def test_stale_manual_action_cannot_overwrite_newer_pardon(self):
        async def run_case():
            service = self._service()
            principal = make_principal_identity("qq", "operator-race")
            first = await service.set_manual_decision(
                principal,
                DECISION_BAN,
                -1,
                REASON_MANUAL_BAN,
            )
            pardon = await service.set_manual_decision(
                principal,
                DECISION_PARDON,
                -1,
                REASON_MANUAL_PARDON,
                expected_record_revision=first.record["record_revision"],
            )
            stale_ban = await service.set_manual_decision(
                principal,
                DECISION_BAN,
                -1,
                REASON_MANUAL_BAN,
                expected_record_revision=first.record["record_revision"],
            )
            active = await service.get_active_record(principal)
            return first, pardon, stale_ban, active

        first, pardon, stale_ban, active = asyncio.run(run_case())

        self.assertTrue(first.success)
        self.assertTrue(pardon.success)
        self.assertFalse(stale_ban.success)
        self.assertTrue(stale_ban.conflict)
        self.assertEqual(active["decision"], DECISION_PARDON)

    def test_clear_requires_the_current_record_version(self):
        async def run_case():
            service = self._service()
            principal = make_principal_identity("qq", "clear-race")
            saved = await service.set_manual_decision(
                principal,
                DECISION_BAN,
                -1,
                REASON_MANUAL_BAN,
            )
            stale_clear = await service.clear_manual_decision(
                principal,
                expected_decision=DECISION_BAN,
                expected_record_revision=saved.record["record_revision"] - 1,
            )
            clear = await service.clear_manual_decision(
                principal,
                expected_decision=DECISION_BAN,
                expected_record_revision=saved.record["record_revision"],
            )
            admission = await service.admit(principal)
            return stale_clear, clear, admission

        stale_clear, clear, admission = asyncio.run(run_case())

        self.assertTrue(stale_clear.conflict)
        self.assertTrue(clear.success)
        self.assertTrue(admission.allowed)


if __name__ == "__main__":
    unittest.main()
