"""Per-UMO async lock management."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass


EMPTY_UMO_KEY = "__empty_umo__"


@dataclass
class _LockEntry:
    lock: asyncio.Lock
    refs: int = 0
    last_used: float = 0.0


@dataclass
class UmoLockLease:
    """A held UMO lock that can be released by a later hook."""

    manager: "UmoLockManager"
    key: str
    entry: _LockEntry
    released: bool = False

    async def release(self) -> None:
        if self.released:
            return
        self.released = True
        self.entry.lock.release()
        await self.manager._release_entry(self.key, self.entry)


class UmoLockManager:
    """Serialize guardrail execution for the same UMO."""

    def __init__(self) -> None:
        self._entries: dict[str, _LockEntry] = {}
        self._registry_lock = asyncio.Lock()

    @asynccontextmanager
    async def hold(self, umo: str) -> AsyncGenerator[None, None]:
        lease = await self.acquire(umo)
        try:
            yield
        finally:
            await lease.release()

    async def acquire(self, umo: str) -> UmoLockLease:
        key = self._key(umo)
        entry = await self._acquire_entry(key)
        await entry.lock.acquire()
        return UmoLockLease(self, key, entry)

    async def _acquire_entry(self, key: str) -> _LockEntry:
        async with self._registry_lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = _LockEntry(lock=asyncio.Lock())
                self._entries[key] = entry
            entry.refs += 1
            entry.last_used = time.monotonic()
            return entry

    async def _release_entry(self, key: str, entry: _LockEntry) -> None:
        async with self._registry_lock:
            entry.refs = max(entry.refs - 1, 0)
            entry.last_used = time.monotonic()
            if entry.refs == 0 and not entry.lock.locked():
                current = self._entries.get(key)
                if current is entry:
                    self._entries.pop(key, None)

    def active_keys(self) -> list[str]:
        return sorted(self._entries)

    @staticmethod
    def _key(umo: str) -> str:
        value = str(umo or "").strip()
        return value or EMPTY_UMO_KEY


_GLOBAL_UMO_LOCK_MANAGER = UmoLockManager()


def get_global_umo_lock_manager() -> UmoLockManager:
    """Return the process-wide lock manager shared by plugin instances."""
    return _GLOBAL_UMO_LOCK_MANAGER
