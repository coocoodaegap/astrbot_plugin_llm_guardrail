import asyncio
import unittest

from session_lock import UmoLockManager, get_global_umo_lock_manager
from state import AstrBotKvStateStore, MemoryStateStore


class UmoLockManagerTests(unittest.TestCase):
    def test_global_lock_manager_is_shared(self):
        self.assertIs(get_global_umo_lock_manager(), get_global_umo_lock_manager())

    def test_manual_lease_blocks_same_umo_until_released(self):
        async def run_case():
            manager = UmoLockManager()
            lease = await manager.acquire("platform:message:1")
            acquired = False

            async def waiter():
                nonlocal acquired
                async with manager.hold("platform:message:1"):
                    acquired = True

            task = asyncio.create_task(waiter())
            await asyncio.sleep(0)
            blocked_before_release = not acquired
            await lease.release()
            await asyncio.wait_for(task, 1.0)
            return blocked_before_release, acquired, manager.active_keys()

        blocked_before_release, acquired, keys = asyncio.run(run_case())

        self.assertTrue(blocked_before_release)
        self.assertTrue(acquired)
        self.assertEqual(keys, [])

    def test_same_umo_runs_serially(self):
        async def run_case():
            manager = UmoLockManager()
            order = []

            async def worker(name, delay):
                async with manager.hold("platform:message:1"):
                    order.append(f"{name}:start")
                    await asyncio.sleep(delay)
                    order.append(f"{name}:end")

            await asyncio.gather(worker("a", 0.02), worker("b", 0.0))
            return order, manager.active_keys()

        order, keys = asyncio.run(run_case())

        self.assertEqual(order, ["a:start", "a:end", "b:start", "b:end"])
        self.assertEqual(keys, [])

    def test_different_umo_can_overlap(self):
        async def run_case():
            manager = UmoLockManager()
            first_started = asyncio.Event()
            second_started = asyncio.Event()

            async def first():
                async with manager.hold("platform:message:1"):
                    first_started.set()
                    await second_started.wait()

            async def second():
                await first_started.wait()
                async with manager.hold("platform:message:2"):
                    second_started.set()

            await asyncio.wait_for(asyncio.gather(first(), second()), 1.0)
            return manager.active_keys()

        keys = asyncio.run(run_case())

        self.assertEqual(keys, [])


class MemoryStateStoreTests(unittest.TestCase):
    def test_set_get_delete_and_list_keys(self):
        async def run_case():
            store = MemoryStateStore()
            await store.set("activity", "umo:1", {"count": 1})
            await store.set("activity", "umo:2", {"count": 2})
            value = await store.get("activity", "umo:1")
            keys = await store.list_keys("activity", "umo:")
            await store.delete("activity", "umo:1")
            deleted = await store.get("activity", "umo:1", {"missing": True})
            return value, keys, deleted

        value, keys, deleted = asyncio.run(run_case())

        self.assertEqual(value, {"count": 1})
        self.assertEqual(keys, ["umo:1", "umo:2"])
        self.assertEqual(deleted, {"missing": True})

    def test_values_are_copied(self):
        async def run_case():
            store = MemoryStateStore()
            value = {"items": ["a"]}
            await store.set("config", "snapshot", value)
            value["items"].append("b")
            stored = await store.get("config", "snapshot")
            stored["items"].append("c")
            stored_again = await store.get("config", "snapshot")
            return stored, stored_again

        stored, stored_again = asyncio.run(run_case())

        self.assertEqual(stored, {"items": ["a", "c"]})
        self.assertEqual(stored_again, {"items": ["a"]})


class _FakeKv:
    def __init__(self):
        self.data = {}

    async def get(self, key, default=None):
        return self.data.get(key, default)

    async def set(self, key, value):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)

    async def list_keys(self, prefix):
        return [key for key in self.data if key.startswith(prefix)]


class AstrBotKvStateStoreTests(unittest.TestCase):
    def test_wraps_astrbot_like_kv(self):
        async def run_case():
            kv = _FakeKv()
            store = AstrBotKvStateStore(kv, prefix="guardrail")
            await store.set("access_control", "user:1", {"blocked": True})
            value = await store.get("access_control", "user:1")
            keys = await store.list_keys("access_control", "user:")
            await store.delete("access_control", "user:1")
            missing = await store.get("access_control", "user:1", {})
            return value, keys, missing

        value, keys, missing = asyncio.run(run_case())

        self.assertEqual(value, {"blocked": True})
        self.assertEqual(keys, ["user:1"])
        self.assertEqual(missing, {})


if __name__ == "__main__":
    unittest.main()
