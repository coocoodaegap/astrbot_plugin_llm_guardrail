"""Token usage ledger for LLM Guardrail (v0.10.0).

The ledger records every LLM call Guardrail can observe.  It never changes the
request path: failures are swallowed, and unobservable spend is counted in the
``unaccounted`` map instead of being dropped silently.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger

try:
    from .session_lock import UmoLockManager
    from .state import StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from session_lock import UmoLockManager
    from state import StateStore


TOKEN_USAGE_NAMESPACE = "token_usage"
TOKEN_USAGE_TABLE_KEY = "global"
TOKEN_USAGE_SCHEMA_VERSION = 1
UMO_KEY_PREFIX = "umo:"
RECENT_MAX = 500

TASK_MAIN_REPLY = "main_reply"
TASK_GUARDRAIL_REVIEW = "guardrail_review"
TASK_GUARDRAIL_RECHECK = "guardrail_recheck"
TASK_GUARDRAIL_RETRY = "guardrail_retry"
TOKEN_TASKS = frozenset(
    (TASK_MAIN_REPLY, TASK_GUARDRAIL_REVIEW, TASK_GUARDRAIL_RECHECK, TASK_GUARDRAIL_RETRY)
)

USAGE_SOURCE_AGENT_STATS = "agent_stats"
USAGE_SOURCE_FINAL_RESPONSE = "final_response"
USAGE_SOURCE_ESTIMATED = "estimated"
USAGE_SOURCE_UNAVAILABLE = "unavailable"

UNACCOUNTED_STREAM_CHUNK = "stream_chunk"
UNACCOUNTED_ABORTED_PARTIAL = "aborted_partial"
UNACCOUNTED_ERROR_NO_USAGE = "error_no_usage"
UNACCOUNTED_MISSING_USAGE = "missing_usage"
UNACCOUNTED_KEYS = (
    UNACCOUNTED_STREAM_CHUNK,
    UNACCOUNTED_ABORTED_PARTIAL,
    UNACCOUNTED_ERROR_NO_USAGE,
    UNACCOUNTED_MISSING_USAGE,
)

COUNT_FIELDS = (
    "calls",
    "success",
    "errors",
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "cached_tokens",
    "total_tokens",
    "estimated_tokens",
    "elapsed_ms",
    "last_ts",
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "retention_days": 31,
    "max_umo_records": 500,
    "recent_limit": 100,
    "estimate_when_usage_missing": True,
    "read_agent_run_stats": True,
}

_NESTED_USAGE_KEYS = ("usage", "token_usage", "raw_usage", "usage_metadata", "model_extra")
_MAX_USAGE_DEPTH = 3


@dataclass(frozen=True)
class TokenRecordResult:
    success: bool
    recorded: bool
    duplicate: bool = False
    estimated: bool = False
    total_tokens: int = 0
    usage_source: str = ""
    warning: str = ""


@dataclass(frozen=True)
class TokenSnapshot:
    success: bool
    scope: str
    umo: str = ""
    totals: dict[str, Any] = field(default_factory=dict)
    by_day: list[dict[str, Any]] = field(default_factory=list)
    by_task: list[dict[str, Any]] = field(default_factory=list)
    by_provider: list[dict[str, Any]] = field(default_factory=list)
    recent: list[dict[str, Any]] = field(default_factory=list)
    unaccounted: dict[str, int] = field(default_factory=dict)
    other_calls: dict[str, int] = field(default_factory=dict)
    updated_at: int = 0
    warning: str = ""


class TokenUsageService:
    """Persist and read the Token usage ledger.

    Lock order: this service owns a dedicated lock domain.  It must never use
    the P1 execution UMO lock or the principal lock, because Guardrail records
    its own LLM calls while already holding them.
    """

    def __init__(
        self,
        state_store: StateStore,
        *,
        clock: Callable[[], float] | None = None,
        lock_manager: UmoLockManager | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> None:
        self._state_store = state_store
        self._clock = clock or time.time
        self._locks = lock_manager or UmoLockManager()
        self._defaults = normalize_settings(settings)

    async def record(
        self,
        *,
        task: str,
        umo: str = "",
        run_id: str = "",
        provider_id: str = "",
        prompt: str = "",
        completion: str = "",
        prompt_tokens_hint: int = 0,
        response: Any = None,
        run_usage: Any = None,
        elapsed_ms: int = 0,
        success: bool = True,
        error: str = "",
        entry: str = "unavailable",
        chat_type: str = "",
        aborted: bool = False,
        dedupe_set: set[str] | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> TokenRecordResult:
        """Record one observable LLM call.  Never raises."""

        try:
            cfg = normalize_settings(settings, fallback=self._defaults)
            if not cfg["enabled"]:
                return TokenRecordResult(True, False, warning="token usage is disabled")

            task_key = str(task or "").strip()
            if task_key not in TOKEN_TASKS:
                task_key = TASK_MAIN_REPLY
            provider_key = _clean_identifier(provider_id, 160)
            entry_key = _clean_identifier(entry, 40) or "unavailable"
            chat_key = _clean_identifier(chat_type, 20)
            umo_key = _clean_identifier(umo, 300)
            run_key = _clean_identifier(run_id, 120)

            counts, usage_source, unaccounted_reason = _resolve_counts(
                response=response,
                run_usage=run_usage,
                prompt=prompt,
                completion=completion,
                success=success,
                estimate=bool(cfg["estimate_when_usage_missing"]),
                aborted=aborted,
                prompt_tokens_hint=prompt_tokens_hint,
            )
            counts = {**counts, "elapsed_ms": max(0, int(elapsed_ms or 0))}
            total = int(counts["total_tokens"])
            dedupe_key = _fingerprint(
                run_key, task_key, provider_key, prompt, completion, total
            )
            if dedupe_set is not None and dedupe_key in dedupe_set:
                return TokenRecordResult(
                    True,
                    False,
                    duplicate=True,
                    total_tokens=total,
                    usage_source=usage_source,
                )

            now = int(self._clock())
            await self._update_ledger(
                TOKEN_USAGE_TABLE_KEY,
                scope="global",
                umo="",
                counts=counts,
                task=task_key,
                provider=provider_key,
                entry=entry_key,
                chat_type=chat_key,
                success=success,
                error=error,
                usage_source=usage_source,
                unaccounted_reason=unaccounted_reason,
                umo_label=umo_key,
                settings=cfg,
                now=now,
            )
            if umo_key:
                await self._update_ledger(
                    _umo_key(umo_key),
                    scope="umo",
                    umo=umo_key,
                    counts=counts,
                    task=task_key,
                    provider=provider_key,
                    entry=entry_key,
                    chat_type=chat_key,
                    success=success,
                    error=error,
                    usage_source=usage_source,
                    unaccounted_reason=unaccounted_reason,
                    umo_label=umo_key,
                    settings=cfg,
                    now=now,
                )
            if dedupe_set is not None:
                dedupe_set.add(dedupe_key)
                while len(dedupe_set) > 64:
                    dedupe_set.pop()
            return TokenRecordResult(
                True,
                True,
                estimated=usage_source == USAGE_SOURCE_ESTIMATED,
                total_tokens=total,
                usage_source=usage_source,
            )
        except Exception as exc:  # Accounting must never break a request.
            _log_failure("record token usage", exc)
            return TokenRecordResult(False, False, warning="token ledger write failed")

    async def record_unaccounted(
        self,
        *,
        reason: str,
        umo: str = "",
        settings: Mapping[str, Any] | None = None,
    ) -> None:
        """Count one call whose Token spend could not be observed."""

        try:
            cfg = normalize_settings(settings, fallback=self._defaults)
            if not cfg["enabled"] or reason not in UNACCOUNTED_KEYS:
                return
            umo_key = _clean_identifier(umo, 300)
            targets = [(TOKEN_USAGE_TABLE_KEY, "global", "")]
            if umo_key:
                targets.append((_umo_key(umo_key), "umo", umo_key))
            now = int(self._clock())
            for key, scope, label in targets:
                async with self._locks.hold(key):
                    ledger = await self._load_ledger(key, scope, label)
                    ledger["unaccounted"][reason] += 1
                    ledger["updated_at"] = now
                    await self._save_ledger(key, ledger)
        except Exception as exc:
            _log_failure("record unaccounted call", exc)

    async def record_retrieval(
        self,
        *,
        success: bool,
        umo: str = "",
        settings: Mapping[str, Any] | None = None,
    ) -> None:
        """Count one retrieval call.  Retrieval tokens are not observable."""

        try:
            cfg = normalize_settings(settings, fallback=self._defaults)
            if not cfg["enabled"]:
                return
            umo_key = _clean_identifier(umo, 300)
            for key, scope in ((TOKEN_USAGE_TABLE_KEY, "global"),):
                await self._update_other_calls(key, scope, "", success, cfg)
            if umo_key:
                await self._update_other_calls(
                    _umo_key(umo_key), "umo", umo_key, success, cfg
                )
        except Exception as exc:
            _log_failure("record retrieval call", exc)

    async def snapshot(
        self,
        *,
        scope: str = "global",
        umo: str = "",
        days: int = 7,
        settings: Mapping[str, Any] | None = None,
    ) -> TokenSnapshot:
        try:
            cfg = normalize_settings(settings, fallback=self._defaults)
            normalized_scope = str(scope or "").strip().lower()
            if normalized_scope not in {"global", "umo"}:
                return TokenSnapshot(False, normalized_scope, warning="scope must be global or umo")
            umo_key = _clean_identifier(umo, 300)
            if normalized_scope == "umo" and not umo_key:
                return TokenSnapshot(False, "umo", warning="umo is required")
            window = _bounded_int(days, 7, 1, int(cfg["retention_days"]))
            key = TOKEN_USAGE_TABLE_KEY if normalized_scope == "global" else _umo_key(umo_key)
            async with self._locks.hold(key):
                ledger = await self._load_ledger(key, normalized_scope, umo_key)
            return _build_snapshot(ledger, normalized_scope, umo_key, window, cfg)
        except Exception as exc:
            _log_failure("read token usage", exc)
            return TokenSnapshot(False, str(scope or ""), warning="token ledger is unavailable")

    async def overview(self, *, settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
        snapshot = await self.snapshot(scope="global", days=1, settings=settings)
        if not snapshot.success:
            return {"success": False, "warning": snapshot.warning}
        return {
            "success": True,
            "today": snapshot.by_day[-1] if snapshot.by_day else {},
            "totals": snapshot.totals,
            "unaccounted": snapshot.unaccounted,
            "other_calls": snapshot.other_calls,
        }

    # -- storage ---------------------------------------------------------
    async def _update_ledger(
        self,
        key: str,
        *,
        scope: str,
        umo: str,
        counts: Mapping[str, int],
        task: str,
        provider: str,
        entry: str,
        chat_type: str,
        success: bool,
        error: str,
        usage_source: str,
        unaccounted_reason: str,
        umo_label: str,
        settings: Mapping[str, Any],
        now: int,
    ) -> None:
        async with self._locks.hold(key):
            ledger = await self._load_ledger(key, scope, umo)
            is_new = not ledger["buckets"] and not ledger["totals"]["calls"]
            day = _day_key(now)
            estimated = usage_source == USAGE_SOURCE_ESTIMATED
            _bump(ledger["totals"], counts, success, now, estimated)
            bucket = ledger["buckets"].setdefault(day, _empty_counts())
            _bump(bucket, counts, success, now, estimated)
            _bump_nested(bucket.setdefault("tasks", {}), task, counts, success, now, estimated)
            _bump_nested(
                bucket.setdefault("providers", {}),
                provider or "(default)",
                counts,
                success,
                now,
                estimated,
            )
            _prune_buckets(ledger, int(settings["retention_days"]))
            if unaccounted_reason in UNACCOUNTED_KEYS:
                ledger["unaccounted"][unaccounted_reason] += 1
            if scope == "global":
                _append_recent(
                    ledger,
                    {
                        "ts": now,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                        "task": task,
                        "provider": provider,
                        "umo": umo_label,
                        "entry": entry,
                        "chat_type": chat_type,
                        "success": bool(success),
                        "prompt_tokens": int(counts["prompt_tokens"]),
                        "completion_tokens": int(counts["completion_tokens"]),
                        "total_tokens": int(counts["total_tokens"]),
                        "estimated": usage_source == USAGE_SOURCE_ESTIMATED,
                        "usage_source": usage_source,
                        "elapsed_ms": int(counts["elapsed_ms"]),
                        "error": _clean_identifier(error, 60),
                    },
                    int(settings["recent_limit"]),
                )
            ledger["updated_at"] = now
            await self._save_ledger(key, ledger)
            if is_new and scope == "umo":
                await self._enforce_umo_capacity(int(settings["max_umo_records"]))

    async def _update_other_calls(
        self,
        key: str,
        scope: str,
        umo: str,
        success: bool,
        settings: Mapping[str, Any],
    ) -> None:
        async with self._locks.hold(key):
            ledger = await self._load_ledger(key, scope, umo)
            ledger["other_calls"]["retrieval"] += 1
            if not success:
                ledger["other_calls"]["retrieval_failed"] += 1
            ledger["updated_at"] = int(self._clock())
            await self._save_ledger(key, ledger)

    async def _enforce_umo_capacity(self, limit: int) -> None:
        if limit < 1:
            return
        keys = await self._state_store.list_keys(TOKEN_USAGE_NAMESPACE, UMO_KEY_PREFIX)
        if len(keys) <= limit:
            return
        stamped: list[tuple[int, str]] = []
        for key in keys:
            async with self._locks.hold(key):
                ledger = await self._load_ledger(key, "umo", "")
            stamped.append((int(ledger.get("updated_at", 0)), key))
        stamped.sort()
        for _updated, key in stamped[: max(0, len(stamped) - limit)]:
            await self._state_store.delete(TOKEN_USAGE_NAMESPACE, key)

    async def _load_ledger(self, key: str, scope: str, umo: str) -> dict[str, Any]:
        raw = await self._state_store.get(TOKEN_USAGE_NAMESPACE, key, None)
        if not isinstance(raw, dict):
            return _empty_ledger(scope, umo)
        totals = _normalize_counts(raw.get("totals"))
        buckets: dict[str, dict[str, Any]] = {}
        raw_buckets = raw.get("buckets")
        if isinstance(raw_buckets, dict):
            for day, bucket in raw_buckets.items():
                if not _valid_day(str(day)) or not isinstance(bucket, dict):
                    continue
                normalized = _normalize_counts(bucket)
                normalized["tasks"] = _normalize_named_counts(bucket.get("tasks"))
                normalized["providers"] = _normalize_named_counts(bucket.get("providers"))
                buckets[str(day)] = normalized
        unaccounted = {name: 0 for name in UNACCOUNTED_KEYS}
        raw_unaccounted = raw.get("unaccounted")
        if isinstance(raw_unaccounted, dict):
            for name in UNACCOUNTED_KEYS:
                unaccounted[name] = _safe_int(raw_unaccounted.get(name), 0)
        other_calls = {"retrieval": 0, "retrieval_failed": 0}
        raw_other = raw.get("other_calls")
        if isinstance(raw_other, dict):
            for name in other_calls:
                other_calls[name] = _safe_int(raw_other.get(name), 0)
        recent: list[dict[str, Any]] = []
        raw_recent = raw.get("recent")
        if isinstance(raw_recent, list):
            recent = [_normalize_recent(item) for item in raw_recent if isinstance(item, dict)]
        return {
            "schema_version": TOKEN_USAGE_SCHEMA_VERSION,
            "scope": scope,
            "umo": umo,
            "updated_at": _safe_int(raw.get("updated_at"), 0),
            "unaccounted": unaccounted,
            "other_calls": other_calls,
            "totals": totals,
            "buckets": buckets,
            "recent": recent,
        }

    async def _save_ledger(self, key: str, ledger: dict[str, Any]) -> None:
        await self._state_store.set(TOKEN_USAGE_NAMESPACE, key, ledger)


# -- usage extraction -------------------------------------------------------


def estimate_token_count(text: Any) -> int:
    raw = str(text or "")
    if not raw:
        return 0
    ascii_chars = sum(1 for ch in raw if ord(ch) < 128)
    return max(1, int(ascii_chars / 4.0 + (len(raw) - ascii_chars)))


def extract_usage(response: Any) -> dict[str, Any]:
    """Extract Token counts from one AstrBot response object."""

    candidates: list[Any] = []
    for source in (
        response,
        getattr(response, "raw_completion", None),
        getattr(response, "raw_response", None),
    ):
        candidates.extend(_usage_candidates(source))
    for candidate in candidates:
        counts = _counts_from_candidate(candidate)
        if counts is not None:
            return counts
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0, "found": False}


def _usage_candidates(value: Any, depth: int = 0) -> list[Any]:
    if value is None or depth > _MAX_USAGE_DEPTH:
        return []
    result = [value]
    if isinstance(value, dict):
        for key in _NESTED_USAGE_KEYS:
            nested = value.get(key)
            if nested is not None and nested is not value:
                result.extend(_usage_candidates(nested, depth + 1))
        return result
    for key in _NESTED_USAGE_KEYS:
        try:
            nested = getattr(value, key, None)
        except Exception:
            nested = None
        if nested is not None and nested is not value:
            result.extend(_usage_candidates(nested, depth + 1))
    dumper = getattr(value, "model_dump", None)
    if callable(dumper):
        try:
            dumped = dumper()
        except Exception:
            dumped = None
        if dumped is not None and dumped is not value:
            result.extend(_usage_candidates(dumped, depth + 1))
    return result


def _counts_from_candidate(candidate: Any) -> dict[str, Any] | None:
    input_other = _read_int(candidate, "input_other")
    input_cached = _read_int(candidate, "input_cached")
    output = _read_int(candidate, "output")
    if input_other or input_cached or output:
        return {
            "prompt_tokens": input_other + input_cached,
            "completion_tokens": output,
            "total_tokens": input_other + input_cached + output,
            "cached_tokens": input_cached,
            "found": True,
        }
    prompt = _read_int(candidate, "prompt_tokens", "input_tokens", "input_token_count")
    completion = _read_int(
        candidate, "completion_tokens", "output_tokens", "output_token_count", "generated_tokens"
    )
    total = _read_int(candidate, "total_tokens", "total_token_count")
    if prompt or completion or total:
        cached = min(
            _read_int(
                candidate,
                "prompt_tokens_details.cached_tokens",
                "input_tokens_details.cached_tokens",
                "cache_read_input_tokens",
            ),
            prompt,
        )
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "cached_tokens": max(cached, 0),
            "found": True,
        }
    gemini_prompt = _read_int(candidate, "prompt_token_count")
    gemini_candidates = _read_int(candidate, "candidates_token_count")
    gemini_thoughts = _read_int(candidate, "thoughts_token_count")
    if gemini_prompt or gemini_candidates:
        completion = gemini_candidates + gemini_thoughts
        return {
            "prompt_tokens": gemini_prompt,
            "completion_tokens": completion,
            "total_tokens": gemini_prompt + completion,
            "cached_tokens": min(_read_int(candidate, "cached_content_token_count"), gemini_prompt),
            "found": True,
        }
    return None


def _resolve_counts(
    *,
    response: Any,
    run_usage: Any,
    prompt: str,
    completion: str,
    success: bool,
    estimate: bool,
    aborted: bool = False,
    prompt_tokens_hint: int = 0,
) -> tuple[dict[str, int], str, str]:
    if run_usage is not None:
        counts = extract_usage(run_usage)
        if counts["found"] and counts["total_tokens"] > 0:
            return _finalize_counts(counts), USAGE_SOURCE_AGENT_STATS, ""

    if response is not None:
        counts = extract_usage(response)
        if counts["found"] and counts["total_tokens"] > 0:
            return _finalize_counts(counts), USAGE_SOURCE_FINAL_RESPONSE, ""
        role = str(getattr(response, "role", "") or "").strip().lower()
        if role == "err":
            return _empty_usage_counts(), USAGE_SOURCE_UNAVAILABLE, UNACCOUNTED_ERROR_NO_USAGE

    if aborted:
        return _empty_usage_counts(), USAGE_SOURCE_UNAVAILABLE, UNACCOUNTED_ABORTED_PARTIAL
    if not success:
        return _empty_usage_counts(), USAGE_SOURCE_UNAVAILABLE, UNACCOUNTED_ERROR_NO_USAGE
    if not estimate:
        return _empty_usage_counts(), USAGE_SOURCE_UNAVAILABLE, UNACCOUNTED_MISSING_USAGE
    prompt_tokens = (
        max(0, int(prompt_tokens_hint))
        if prompt_tokens_hint
        else estimate_token_count(prompt)
    )
    completion_tokens = estimate_token_count(completion)
    if prompt_tokens == 0 and completion_tokens == 0:
        return _empty_usage_counts(), USAGE_SOURCE_UNAVAILABLE, UNACCOUNTED_MISSING_USAGE
    return (
        {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": 0,
        },
        USAGE_SOURCE_ESTIMATED,
        "",
    )


def _finalize_counts(counts: Mapping[str, Any]) -> dict[str, int]:
    prompt = _safe_int(counts.get("prompt_tokens"), 0)
    completion = _safe_int(counts.get("completion_tokens"), 0)
    total = _safe_int(counts.get("total_tokens"), 0)
    if total <= 0:
        total = prompt + completion
    elif prompt <= 0 and completion <= 0:
        total = max(total, 0)
        prompt = total
    elif total < prompt + completion:
        total = prompt + completion
    elif total > prompt + completion:
        completion += total - (prompt + completion)
    return {
        "prompt_tokens": max(prompt, 0),
        "completion_tokens": max(completion, 0),
        "total_tokens": max(total, 0),
        "cached_tokens": min(max(_safe_int(counts.get("cached_tokens"), 0), 0), max(prompt, 0)),
    }


def _empty_usage_counts() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}


# -- ledger shape -----------------------------------------------------------


def _empty_counts() -> dict[str, int]:
    return {name: 0 for name in COUNT_FIELDS}


def _empty_ledger(scope: str, umo: str) -> dict[str, Any]:
    return {
        "schema_version": TOKEN_USAGE_SCHEMA_VERSION,
        "scope": scope,
        "umo": umo,
        "updated_at": 0,
        "unaccounted": {name: 0 for name in UNACCOUNTED_KEYS},
        "other_calls": {"retrieval": 0, "retrieval_failed": 0},
        "totals": _empty_counts(),
        "buckets": {},
        "recent": [],
    }


def _normalize_counts(raw: Any) -> dict[str, int]:
    source = raw if isinstance(raw, Mapping) else {}
    counts = {name: _safe_int(source.get(name), 0) for name in COUNT_FIELDS}
    counts["success"] = counts["success"] or 0
    counts["errors"] = counts["errors"] or 0
    return counts


def _normalize_named_counts(raw: Any) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    if not isinstance(raw, Mapping):
        return result
    for name, value in raw.items():
        key = _clean_identifier(name, 160)
        if key:
            result[key] = _normalize_counts(value)
    return result


def _normalize_recent(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ts": _safe_int(raw.get("ts"), 0),
        "time": _clean_identifier(raw.get("time"), 24),
        "task": _clean_identifier(raw.get("task"), 40),
        "provider": _clean_identifier(raw.get("provider"), 160),
        "umo": _clean_identifier(raw.get("umo"), 300),
        "entry": _clean_identifier(raw.get("entry"), 40),
        "chat_type": _clean_identifier(raw.get("chat_type"), 20),
        "success": bool(raw.get("success", True)),
        "prompt_tokens": _safe_int(raw.get("prompt_tokens"), 0),
        "completion_tokens": _safe_int(raw.get("completion_tokens"), 0),
        "total_tokens": _safe_int(raw.get("total_tokens"), 0),
        "estimated": bool(raw.get("estimated", False)),
        "usage_source": _clean_identifier(raw.get("usage_source"), 32),
        "elapsed_ms": _safe_int(raw.get("elapsed_ms"), 0),
        "error": _clean_identifier(raw.get("error"), 60),
    }


def _bump(
    bucket: dict[str, Any],
    counts: Mapping[str, int],
    success: bool,
    now: int,
    estimated: bool = False,
) -> None:
    bucket["calls"] = _safe_int(bucket.get("calls"), 0) + 1
    bucket["success"] = _safe_int(bucket.get("success"), 0) + (1 if success else 0)
    bucket["errors"] = _safe_int(bucket.get("errors"), 0) + (0 if success else 1)
    for name in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_tokens", "total_tokens"):
        bucket[name] = _safe_int(bucket.get(name), 0) + _safe_int(counts.get(name), 0)
    total = _safe_int(counts.get("total_tokens"), 0)
    if estimated and total > 0:
        bucket["estimated_tokens"] = _safe_int(bucket.get("estimated_tokens"), 0) + total
    bucket["elapsed_ms"] = _safe_int(bucket.get("elapsed_ms"), 0) + _safe_int(counts.get("elapsed_ms"), 0)
    bucket["last_ts"] = now


def _bump_nested(
    target: dict[str, dict[str, int]],
    name: str,
    counts: Mapping[str, int],
    success: bool,
    now: int,
    estimated: bool = False,
) -> None:
    bucket = target.setdefault(name, _empty_counts())
    _bump(bucket, counts, success, now, estimated)


def _build_snapshot(
    ledger: Mapping[str, Any],
    scope: str,
    umo: str,
    days: int,
    settings: Mapping[str, Any],
) -> TokenSnapshot:
    buckets = ledger.get("buckets", {})
    day_keys = sorted(buckets)[-days:]
    by_day = []
    for day in day_keys:
        bucket = buckets[day]
        by_day.append(
            {
                "day": day,
                "calls": bucket["calls"],
                "success": bucket["success"],
                "errors": bucket["errors"],
                "prompt_tokens": bucket["prompt_tokens"],
                "completion_tokens": bucket["completion_tokens"],
                "reasoning_tokens": bucket["reasoning_tokens"],
                "cached_tokens": bucket["cached_tokens"],
                "total_tokens": bucket["total_tokens"],
                "estimated_tokens": bucket["estimated_tokens"],
                "known_tokens": max(0, bucket["total_tokens"] - bucket["estimated_tokens"]),
                "tasks": _ranked(bucket.get("tasks")),
                "providers": _ranked(bucket.get("providers")),
            }
        )
    totals = _normalize_counts(ledger.get("totals"))
    totals["known_tokens"] = max(0, totals["total_tokens"] - totals["estimated_tokens"])
    totals["estimated_ratio"] = (
        round(totals["estimated_tokens"] / totals["total_tokens"], 4)
        if totals["total_tokens"] > 0
        else 0
    )
    recent = ledger.get("recent", []) if scope == "global" else []
    limit = int(settings["recent_limit"])
    return TokenSnapshot(
        True,
        scope,
        umo,
        totals=totals,
        by_day=by_day,
        by_task=_aggregate(ledger, "tasks"),
        by_provider=_aggregate(ledger, "providers"),
        recent=list(reversed(recent[-limit:])),
        unaccounted=dict(ledger.get("unaccounted", {})),
        other_calls=dict(ledger.get("other_calls", {})),
        updated_at=_safe_int(ledger.get("updated_at"), 0),
    )


def _ranked(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return []
    items = [
        {"name": str(name), "total_tokens": _safe_int(value.get("total_tokens"), 0), "calls": _safe_int(value.get("calls"), 0)}
        for name, value in raw.items()
        if isinstance(value, Mapping)
    ]
    items.sort(key=lambda item: item["total_tokens"], reverse=True)
    return items


def _aggregate(ledger: Mapping[str, Any], field_name: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, int]] = {}
    for bucket in ledger.get("buckets", {}).values():
        raw = bucket.get(field_name)
        if not isinstance(raw, Mapping):
            continue
        for name, value in raw.items():
            if not isinstance(value, Mapping):
                continue
            current = merged.setdefault(str(name), {"total_tokens": 0, "calls": 0})
            current["total_tokens"] += _safe_int(value.get("total_tokens"), 0)
            current["calls"] += _safe_int(value.get("calls"), 0)
    items = [{"name": name, **value} for name, value in merged.items()]
    items.sort(key=lambda item: item["total_tokens"], reverse=True)
    return items


def _append_recent(ledger: dict[str, Any], item: dict[str, Any], limit: int) -> None:
    recent = ledger.setdefault("recent", [])
    if not isinstance(recent, list):
        recent = []
        ledger["recent"] = recent
    recent.append(item)
    del recent[:-max(1, min(limit, RECENT_MAX))]


def _prune_buckets(ledger: dict[str, Any], retention_days: int) -> None:
    buckets = ledger.get("buckets")
    if not isinstance(buckets, dict) or len(buckets) <= retention_days:
        return
    keep = sorted(buckets)[-retention_days:]
    ledger["buckets"] = {day: buckets[day] for day in keep}


# -- helpers ----------------------------------------------------------------


def normalize_settings(
    settings: Mapping[str, Any] | None,
    *,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = dict(fallback or DEFAULT_SETTINGS)
    raw = settings if isinstance(settings, Mapping) else {}
    merged = {**base, **raw}
    return {
        "enabled": _bool(merged.get("enabled"), True),
        "retention_days": _bounded_int(merged.get("retention_days"), 31, 1, 365),
        "max_umo_records": _bounded_int(merged.get("max_umo_records"), 500, 1, 100000),
        "recent_limit": _bounded_int(merged.get("recent_limit"), 100, 1, RECENT_MAX),
        "estimate_when_usage_missing": _bool(merged.get("estimate_when_usage_missing"), True),
        "read_agent_run_stats": _bool(merged.get("read_agent_run_stats"), True),
    }


def _umo_key(umo: str) -> str:
    return UMO_KEY_PREFIX + json.dumps([umo], ensure_ascii=False, separators=(",", ":"))


def _day_key(now: int) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


def _valid_day(value: str) -> bool:
    try:
        time.strptime(value, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def _fingerprint(
    run_id: str,
    task: str,
    provider: str,
    prompt: str,
    completion: str,
    total_tokens: int,
) -> str:
    digest = hashlib.sha1(str(completion or "")[:4000].encode("utf-8", "ignore")).hexdigest()[:16]
    raw = "|".join(
        (
            run_id,
            task,
            provider,
            str(len(str(prompt or ""))),
            str(len(str(completion or ""))),
            digest,
            str(total_tokens),
        )
    )
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()


def _read_int(source: Any, *keys: str) -> int:
    for key in keys:
        current = source
        for part in key.split("."):
            if current is None:
                break
            if isinstance(current, Mapping):
                current = current.get(part)
            else:
                try:
                    current = getattr(current, part, None)
                except Exception:
                    current = None
        try:
            value = int(current)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = _safe_int(value, default)
    return min(max(parsed, minimum), maximum)


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clean_identifier(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _log_failure(action: str, exc: Exception) -> None:
    warning = getattr(logger, "warning", None)
    if callable(warning):
        try:
            warning("[LLMGuardrail] failed to %s: %s", action, exc)
        except Exception:
            pass
