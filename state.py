"""State storage abstraction for P1 runtime state."""

from __future__ import annotations

import inspect
import json
from abc import ABC, abstractmethod
from typing import Any


class StateStore(ABC):
    """Small async key-value interface with explicit namespaces."""

    @abstractmethod
    async def get(self, namespace: str, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def set(self, namespace: str, key: str, value: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, namespace: str, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_keys(self, namespace: str, prefix: str = "") -> list[str]:
        raise NotImplementedError


class MemoryStateStore(StateStore):
    """In-memory StateStore used by tests and runtime fallback."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def get(self, namespace: str, key: str, default: Any = None) -> Any:
        bucket = self._data.get(_clean_namespace(namespace), {})
        if key not in bucket:
            return _copy_json_value(default)
        return _copy_json_value(bucket[key])

    async def set(self, namespace: str, key: str, value: Any) -> None:
        _ensure_json_value(value)
        bucket = self._data.setdefault(_clean_namespace(namespace), {})
        bucket[str(key)] = _copy_json_value(value)

    async def delete(self, namespace: str, key: str) -> None:
        bucket = self._data.get(_clean_namespace(namespace))
        if bucket is not None:
            bucket.pop(str(key), None)

    async def list_keys(self, namespace: str, prefix: str = "") -> list[str]:
        bucket = self._data.get(_clean_namespace(namespace), {})
        key_prefix = str(prefix or "")
        return sorted(key for key in bucket if key.startswith(key_prefix))


class AstrBotKvStateStore(StateStore):
    """StateStore wrapper around an AstrBot-like async KV object."""

    def __init__(self, kv: Any, prefix: str = "llm_guardrail") -> None:
        self.kv = kv
        self.prefix = str(prefix or "llm_guardrail").strip() or "llm_guardrail"

    async def get(self, namespace: str, key: str, default: Any = None) -> Any:
        raw = await self._call_get(self._full_key(namespace, key), default)
        if raw is None:
            return _copy_json_value(default)
        return _decode_value(raw, default)

    async def set(self, namespace: str, key: str, value: Any) -> None:
        _ensure_json_value(value)
        await self._call(("set", "set_data", "put"), self._full_key(namespace, key), _encode_value(value))

    async def delete(self, namespace: str, key: str) -> None:
        await self._call(("delete", "delete_data", "remove"), self._full_key(namespace, key))

    async def list_keys(self, namespace: str, prefix: str = "") -> list[str]:
        full_prefix = self._full_key(namespace, prefix)
        keys = await self._call(("list_keys", "keys"), full_prefix, default=[])
        if keys is None:
            return []
        result: list[str] = []
        namespace_prefix = self._full_key(namespace, "")
        for item in keys:
            text = str(item)
            if text.startswith(namespace_prefix):
                text = text[len(namespace_prefix):]
            if text.startswith(str(prefix or "")):
                result.append(text)
        return sorted(result)

    async def _call(self, names: tuple[str, ...], *args: Any, default: Any = None) -> Any:
        for name in names:
            method = getattr(self.kv, name, None)
            if not callable(method):
                continue
            try:
                value = method(*args)
            except TypeError:
                if default is not None and name in {"get", "get_data"}:
                    value = method(args[0])
                else:
                    raise
            return await value if inspect.isawaitable(value) else value
        if default is not None:
            return default
        raise RuntimeError(f"KV backend does not support any of: {', '.join(names)}")

    async def _call_get(self, key: str, default: Any) -> Any:
        for name in ("get", "get_data"):
            method = getattr(self.kv, name, None)
            if not callable(method):
                continue
            try:
                value = method(key, default)
            except TypeError:
                value = method(key)
            return await value if inspect.isawaitable(value) else value
        return default

    def _full_key(self, namespace: str, key: str) -> str:
        ns = _clean_namespace(namespace)
        return f"{self.prefix}:{ns}:{str(key)}"


def _clean_namespace(namespace: str) -> str:
    value = str(namespace or "").strip()
    if not value:
        raise ValueError("StateStore namespace must not be empty")
    if ":" in value:
        raise ValueError("StateStore namespace must not contain ':'")
    return value


def _ensure_json_value(value: Any) -> None:
    json.dumps(value, ensure_ascii=False)


def _copy_json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _encode_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _decode_value(value: Any, default: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return _copy_json_value(default)
    return _copy_json_value(value)
