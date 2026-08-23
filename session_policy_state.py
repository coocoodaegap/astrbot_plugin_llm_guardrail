"""Persistent, UMO-scoped observation state for the P2-A monitor.

The service is intentionally observation-only.  It owns the JSON schema,
retention, and concurrency around session-policy state, but never offers a
route-cache lookup API.  That separation keeps P2-A from changing an AstrBot
request merely because a historic state record exists.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

try:
    from astrbot.api import logger
except ImportError:  # pragma: no cover - local unit tests do not load AstrBot.
    logger = logging.getLogger(__name__)

try:
    from .session_lock import (
        UmoLockManager,
        get_global_session_policy_state_lock_manager,
    )
    from .state import StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from session_lock import (
        UmoLockManager,
        get_global_session_policy_state_lock_manager,
    )
    from state import StateStore


SESSION_POLICY_STATE_NAMESPACE = "session_policy_state"
SESSION_POLICY_STATE_TABLE_KEY = "umo_records"
SESSION_POLICY_STATE_SCHEMA_VERSION = 1

MAX_UMO_LENGTH = 1_024
MAX_IDENTIFIER_LENGTH = 512
VALID_PHASES = frozenset(
    ("message_input", "message_route", "request", "response")
)
VALID_OUTCOMES = frozenset(("allowed", "blocked", "skipped"))
VALID_REQUEST_TARGET_SOURCES = frozenset(
    ("provider_request", "context_current_chat_provider_id", "unavailable")
)


# StateStore exposes only point reads and writes.  All services sharing one
# event loop therefore need the same lock around the registry document.  Like
# access_control.py, locks are loop-local so a completed unittest loop cannot
# poison the next one.
_TABLE_LOCKS_BY_LOOP: weakref.WeakKeyDictionary[Any, asyncio.Lock] = (
    weakref.WeakKeyDictionary()
)


def _shared_table_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _TABLE_LOCKS_BY_LOOP.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _TABLE_LOCKS_BY_LOOP[loop] = lock
    return lock


@dataclass(frozen=True)
class SessionPolicyStateWriteResult:
    """Non-throwing outcome for an observation write."""

    success: bool
    recorded: bool = False
    record: dict[str, Any] | None = None
    warning: str = ""


@dataclass(frozen=True)
class SessionPolicyStateListResult:
    """Pageable, summary-only monitor list outcome."""

    success: bool
    items: tuple[dict[str, Any], ...] = ()
    total: int = 0
    page: int = 1
    page_size: int = 30
    warning: str = ""


@dataclass(frozen=True)
class SessionPolicyStateDetailResult:
    """Single UMO detail outcome."""

    success: bool
    found: bool = False
    record: dict[str, Any] | None = None
    warning: str = ""


def clean_umo(value: Any) -> str:
    """Return the UMO identity used by runtime and Pages alike."""

    if isinstance(value, bool):
        raise ValueError("umo must be a non-empty string or number")
    umo = str(value if value is not None else "").strip()
    if not umo:
        raise ValueError("umo must not be empty")
    if len(umo) > MAX_UMO_LENGTH:
        raise ValueError("umo is too long")
    return umo


def umo_storage_key(umo: str) -> str:
    """Use a JSON tuple so all UMO strings remain unambiguous map keys."""

    return json.dumps([umo], ensure_ascii=False, separators=(",", ":"))


class SessionPolicyStateService:
    """Persist and expose P2-A UMO policy observations.

    Lock order is always ``session-state UMO lock -> table lock``.  Runtime
    code may already hold the P1 execution UMO lock; this service deliberately
    never obtains that lock and therefore cannot self-deadlock it.
    """

    def __init__(
        self,
        state_store: StateStore,
        *,
        session_locks: UmoLockManager | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._state_store = state_store
        self._session_locks = (
            session_locks or get_global_session_policy_state_lock_manager()
        )
        self._clock = clock or time.time

    async def record_phase(
        self,
        umo: Any,
        *,
        run_id: Any,
        policy_id: Any,
        snapshot_revision: Any,
        started_at: Any,
        phase: str,
        outcome: str,
        terminal_action: Mapping[str, Any] | None,
        rail_outcomes: Mapping[str, Any] | None,
        signals: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
        settings: Mapping[str, Any] | None,
        route_candidate: Mapping[str, Any] | None = None,
        request_target_observation: Mapping[str, Any] | None = None,
    ) -> SessionPolicyStateWriteResult:
        """Merge one completed pipeline phase into the UMO state.

        A late request/response from an older ``run_id`` must not overwrite a
        newer message's "last policy result".  Its request-target and
        route-candidate observations are still useful, independent lifecycle
        facts, so they remain recordable and are explicitly marked in the
        activity stream.  A different run is therefore allowed to replace the
        current policy result only from ``message_input``; request-only
        execution can still create a record when none exists.
        """

        if not _monitoring_enabled(settings):
            return SessionPolicyStateWriteResult(True, recorded=False)
        try:
            normalized_umo = clean_umo(umo)
            normalized_run_id = _clean_identifier(run_id, "run_id")
            normalized_phase = _clean_phase(phase)
            normalized_outcome = _clean_outcome(outcome)
            observation = _normalize_phase_observation(
                run_id=normalized_run_id,
                policy_id=policy_id,
                snapshot_revision=snapshot_revision,
                started_at=started_at,
                phase=normalized_phase,
                outcome=normalized_outcome,
                terminal_action=terminal_action,
                rail_outcomes=rail_outcomes,
                signals=signals,
                route_candidate=route_candidate,
                request_target_observation=request_target_observation,
            )
        except (TypeError, ValueError) as exc:
            return SessionPolicyStateWriteResult(
                False,
                warning=f"session-policy observation is invalid: {exc}",
            )

        key = umo_storage_key(normalized_umo)
        try:
            async with self._session_locks.hold(key):
                async with _shared_table_lock():
                    table = await self._load_table_locked()
                    now = _now(self._clock)
                    table_changed = _prune_expired_records(
                        table,
                        now,
                        _state_ttl_seconds(settings),
                    )
                    raw_record = table["records"].get(key)
                    record = _normalized_record(raw_record, normalized_umo)
                    current_result = record["last_policy_result"]
                    late_foreign_phase = _is_late_foreign_phase(
                        current_result,
                        normalized_run_id,
                        normalized_phase,
                    )
                    before = copy.deepcopy(record)
                    _merge_phase_observation(
                        record,
                        observation,
                        now,
                        merge_policy_result=not late_foreign_phase,
                    )
                    _prune_activity_items(record, _activity_log_limit(settings))
                    record["updated_at"] = now
                    record["last_activity_at"] = now
                    record["record_revision"] = before["record_revision"] + 1
                    table["records"][key] = record
                    table_changed = True
                    table_changed = (
                        _prune_capacity(
                            table,
                            _max_entries(settings),
                            protect_key=key,
                        )
                        or table_changed
                    )
                    if table_changed:
                        table["table_revision"] += 1
                        await self._save_table_locked(table)
                    return SessionPolicyStateWriteResult(
                        True,
                        recorded=True,
                        record=_public_record(record),
                        warning=(
                            "late phase did not replace the newer policy result"
                            if late_foreign_phase
                            else ""
                        ),
                    )
        except Exception as exc:  # State failure must never break an LLM request.
            self._log_storage_failure("record session-policy observation", exc)
            return SessionPolicyStateWriteResult(
                False,
                warning="session-policy state could not be recorded",
            )

    async def list_summaries(
        self,
        *,
        settings: Mapping[str, Any] | None,
        query: Any = "",
        page: Any = 1,
        page_size: Any = 30,
    ) -> SessionPolicyStateListResult:
        """Return summary records, with lazy retention cleanup."""

        try:
            normalized_page = _positive_int(page, 1)
            normalized_page_size = min(_positive_int(page_size, 30), 100)
            query_text = str(query or "").strip().casefold()
        except (TypeError, ValueError) as exc:
            return SessionPolicyStateListResult(False, warning=str(exc))

        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                now = _now(self._clock)
                if _prune_expired_records(table, now, _state_ttl_seconds(settings)):
                    table["table_revision"] += 1
                    await self._save_table_locked(table)
                records = [
                    _normalized_record(raw, str(raw.get("umo", "")))
                    for raw in table["records"].values()
                    if isinstance(raw, dict) and str(raw.get("umo", "")).strip()
                ]
        except Exception as exc:
            self._log_storage_failure("list session-policy state", exc)
            return SessionPolicyStateListResult(
                False,
                warning="session-policy state is unavailable",
            )

        summaries = [_summary_record(record) for record in records]
        if query_text:
            summaries = [
                item
                for item in summaries
                if query_text in item["umo"].casefold()
                or query_text
                in str(
                    (item.get("last_policy_result") or {}).get("policy_id", "")
                ).casefold()
            ]
        summaries.sort(key=lambda item: (-item["updated_at"], item["umo"]))
        total = len(summaries)
        offset = (normalized_page - 1) * normalized_page_size
        return SessionPolicyStateListResult(
            True,
            items=tuple(copy.deepcopy(summaries[offset : offset + normalized_page_size])),
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        )

    async def get_detail(
        self,
        umo: Any,
        *,
        settings: Mapping[str, Any] | None,
    ) -> SessionPolicyStateDetailResult:
        """Return one full state record without extending its lifetime."""

        try:
            normalized_umo = clean_umo(umo)
        except (TypeError, ValueError) as exc:
            return SessionPolicyStateDetailResult(False, warning=str(exc))
        key = umo_storage_key(normalized_umo)
        try:
            async with self._session_locks.hold(key):
                async with _shared_table_lock():
                    table = await self._load_table_locked()
                    now = _now(self._clock)
                    changed = _prune_expired_records(
                        table,
                        now,
                        _state_ttl_seconds(settings),
                    )
                    raw = table["records"].get(key)
                    if changed:
                        table["table_revision"] += 1
                        await self._save_table_locked(table)
                    if not isinstance(raw, dict):
                        return SessionPolicyStateDetailResult(True, found=False)
                    record = _normalized_record(raw, normalized_umo)
                    return SessionPolicyStateDetailResult(
                        True,
                        found=True,
                        record=_public_record(record),
                    )
        except Exception as exc:
            self._log_storage_failure("read session-policy state", exc)
            return SessionPolicyStateDetailResult(
                False,
                warning="session-policy state is unavailable",
            )

    async def _load_table_locked(self) -> dict[str, Any]:
        raw = await self._state_store.get(
            SESSION_POLICY_STATE_NAMESPACE,
            SESSION_POLICY_STATE_TABLE_KEY,
            None,
        )
        if not isinstance(raw, dict):
            return _empty_table()
        raw_records = raw.get("records")
        if not isinstance(raw_records, dict):
            raw_records = {}
        records: dict[str, dict[str, Any]] = {}
        for key, record in raw_records.items():
            if not isinstance(record, dict):
                continue
            umo = str(record.get("umo", "") or "").strip()
            if not umo:
                continue
            try:
                normalized_umo = clean_umo(umo)
            except ValueError:
                continue
            records[str(key)] = _normalized_record(record, normalized_umo)
        return {
            "schema_version": SESSION_POLICY_STATE_SCHEMA_VERSION,
            "table_revision": _non_negative_int(raw.get("table_revision"), 0),
            "records": records,
        }

    async def _save_table_locked(self, table: dict[str, Any]) -> None:
        await self._state_store.set(
            SESSION_POLICY_STATE_NAMESPACE,
            SESSION_POLICY_STATE_TABLE_KEY,
            table,
        )

    @staticmethod
    def _log_storage_failure(action: str, exc: Exception) -> None:
        warning = getattr(logger, "warning", None)
        if callable(warning):
            warning("[LLMGuardrail] failed to %s: %s", action, exc)


def _empty_table() -> dict[str, Any]:
    return {
        "schema_version": SESSION_POLICY_STATE_SCHEMA_VERSION,
        "table_revision": 0,
        "records": {},
    }


def _empty_record(umo: str) -> dict[str, Any]:
    return {
        "umo": umo,
        "record_revision": 0,
        "created_at": 0,
        "updated_at": 0,
        "last_activity_at": 0,
        "last_policy_result": None,
        "route_candidate": None,
        "last_request_target_observation": None,
        "activities": {
            "revision": 0,
            "generation": 0,
            "cleared_at": None,
            "items": [],
        },
    }


def _normalized_record(raw: Any, umo: str) -> dict[str, Any]:
    record = _empty_record(umo)
    if not isinstance(raw, dict):
        return record
    record.update(
        {
            "created_at": _non_negative_int(raw.get("created_at"), 0),
            "updated_at": _non_negative_int(raw.get("updated_at"), 0),
            "last_activity_at": _non_negative_int(raw.get("last_activity_at"), 0),
            "record_revision": _non_negative_int(raw.get("record_revision"), 0),
            "last_policy_result": _normalized_policy_result(
                raw.get("last_policy_result")
            ),
            "route_candidate": _normalized_route_candidate(raw.get("route_candidate")),
            "last_request_target_observation": _normalized_request_observation(
                raw.get("last_request_target_observation")
            ),
            "activities": _normalized_activities(raw.get("activities")),
        }
    )
    if not record["created_at"] and record["updated_at"]:
        record["created_at"] = record["updated_at"]
    if not record["last_activity_at"]:
        record["last_activity_at"] = record["updated_at"]
    return record


def _normalized_policy_result(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    run_id = _safe_identifier(raw.get("run_id"))
    policy_id = _safe_identifier(raw.get("policy_id"))
    if not run_id or not policy_id:
        return None
    outcome = str(raw.get("outcome", "skipped") or "").strip().lower()
    if outcome not in VALID_OUTCOMES:
        outcome = "skipped"
    phase = str(raw.get("last_stage", "message_input") or "").strip()
    if phase not in VALID_PHASES:
        phase = "message_input"
    return {
        "result_revision": _non_negative_int(raw.get("result_revision"), 0),
        "run_id": run_id,
        "policy_id": policy_id,
        "snapshot_revision": _non_negative_int(raw.get("snapshot_revision"), 0),
        "started_at": _non_negative_int(raw.get("started_at"), 0),
        "last_stage": phase,
        "outcome": outcome,
        "terminal_action": _safe_json_mapping(raw.get("terminal_action")),
        "rail_outcomes": _safe_json_mapping(raw.get("rail_outcomes")),
        "signals": _safe_json_signal_list(raw.get("signals")),
        "observed_at": _non_negative_int(raw.get("observed_at"), 0),
    }


def _normalized_route_candidate(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    provider_id = _safe_identifier(raw.get("provider_id"))
    policy_id = _safe_identifier(raw.get("policy_id"))
    run_id = _safe_identifier(raw.get("run_id"))
    if not provider_id or not policy_id or not run_id:
        return None
    return {
        "candidate_revision": _non_negative_int(raw.get("candidate_revision"), 0),
        "mode": "observe_only",
        "run_id": run_id,
        "policy_id": policy_id,
        "snapshot_revision": _non_negative_int(raw.get("snapshot_revision"), 0),
        "provider_id": provider_id,
        "model_id": _safe_identifier(raw.get("model_id")),
        "source_route_node_id": _safe_identifier(raw.get("source_route_node_id")),
        "created_at": _non_negative_int(raw.get("created_at"), 0),
        "observed_at": _non_negative_int(raw.get("observed_at"), 0),
        "last_used_at": None,
        "expires_at": None,
    }


def _normalized_request_observation(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    run_id = _safe_identifier(raw.get("run_id"))
    if not run_id:
        return None
    source = str(raw.get("source", "unavailable") or "").strip()
    if source not in VALID_REQUEST_TARGET_SOURCES:
        source = "unavailable"
    return {
        "observation_revision": _non_negative_int(
            raw.get("observation_revision"), 0
        ),
        "run_id": run_id,
        "provider_id": _safe_identifier(raw.get("provider_id")),
        "model_id": _safe_identifier(raw.get("model_id")),
        "source": source,
        "observed_at": _non_negative_int(raw.get("observed_at"), 0),
    }


def _normalized_activities(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _empty_record("")["activities"]
    items = raw.get("items")
    if not isinstance(items, list):
        items = []
    normalized_items = [
        _safe_json_mapping(item)
        for item in items
        if _safe_json_mapping(item) is not None
    ]
    return {
        "revision": _non_negative_int(raw.get("revision"), 0),
        "generation": _non_negative_int(raw.get("generation"), 0),
        "cleared_at": None,
        "items": normalized_items,
    }


def _normalize_phase_observation(
    *,
    run_id: str,
    policy_id: Any,
    snapshot_revision: Any,
    started_at: Any,
    phase: str,
    outcome: str,
    terminal_action: Mapping[str, Any] | None,
    rail_outcomes: Mapping[str, Any] | None,
    signals: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    route_candidate: Mapping[str, Any] | None,
    request_target_observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized_signals = _safe_json_signal_list(signals)
    if signals and len(normalized_signals) != len(signals):
        raise ValueError("signals must contain JSON-compatible NodeSignal values")
    return {
        "run_id": run_id,
        "policy_id": _clean_identifier(policy_id, "policy_id"),
        "snapshot_revision": _non_negative_int(snapshot_revision, 0),
        "started_at": _non_negative_int(started_at, 0),
        "phase": phase,
        "outcome": outcome,
        "terminal_action": _safe_json_mapping(terminal_action),
        "rail_outcomes": _safe_json_mapping(rail_outcomes) or {},
        "signals": normalized_signals,
        "route_candidate": _normalize_route_candidate_input(route_candidate),
        "request_target_observation": _normalize_request_observation_input(
            request_target_observation
        ),
    }


def _normalize_route_candidate_input(
    raw: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if raw is None:
        return None
    provider_id = _safe_identifier(raw.get("provider_id"))
    if not provider_id:
        return None
    return {
        "provider_id": provider_id,
        "model_id": _safe_identifier(raw.get("model_id")),
        "source_route_node_id": _safe_identifier(raw.get("source_route_node_id")),
    }


def _normalize_request_observation_input(
    raw: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if raw is None:
        return None
    source = str(raw.get("source", "unavailable") or "").strip()
    if source not in VALID_REQUEST_TARGET_SOURCES:
        source = "unavailable"
    return {
        "provider_id": _safe_identifier(raw.get("provider_id")),
        "model_id": _safe_identifier(raw.get("model_id")),
        "source": source,
    }


def _merge_phase_observation(
    record: dict[str, Any],
    observation: dict[str, Any],
    now: int,
    *,
    merge_policy_result: bool,
) -> None:
    if merge_policy_result:
        current = record["last_policy_result"]
        if current is None or current["run_id"] != observation["run_id"]:
            result_revision = (current or {}).get("result_revision", 0) + 1
            current = {
                "result_revision": result_revision,
                "run_id": observation["run_id"],
                "policy_id": observation["policy_id"],
                "snapshot_revision": observation["snapshot_revision"],
                "started_at": observation["started_at"],
                "last_stage": observation["phase"],
                "outcome": observation["outcome"],
                "terminal_action": observation["terminal_action"],
                "rail_outcomes": {},
                "signals": [],
                "observed_at": now,
            }
            record["last_policy_result"] = current
        else:
            current["result_revision"] += 1
            current["policy_id"] = observation["policy_id"]
            current["snapshot_revision"] = observation["snapshot_revision"]
            current["last_stage"] = observation["phase"]
            current["outcome"] = observation["outcome"]
            if (
                observation["terminal_action"] is not None
                or current["terminal_action"] is None
            ):
                current["terminal_action"] = observation["terminal_action"]
            current["observed_at"] = now
        current["rail_outcomes"].update(copy.deepcopy(observation["rail_outcomes"]))
        _merge_signals(current["signals"], observation["signals"])
        if not record["created_at"]:
            record["created_at"] = now
        _append_activity(
            record,
            {
                "at": now,
                "kind": "policy_stage_completed",
                "phase": observation["phase"],
                "run_id": observation["run_id"],
                "policy_id": observation["policy_id"],
                "snapshot_revision": observation["snapshot_revision"],
                "outcome": observation["outcome"],
                "signal_count": len(observation["signals"]),
                "terminal_action": _terminal_action_summary(observation["terminal_action"]),
            },
        )
    else:
        _append_activity(
            record,
            {
                "at": now,
                "kind": "late_policy_stage_observed",
                "phase": observation["phase"],
                "run_id": observation["run_id"],
                "policy_id": observation["policy_id"],
                "snapshot_revision": observation["snapshot_revision"],
                "outcome": observation["outcome"],
                "reason": "newer_policy_result_exists",
            },
        )

    candidate = observation["route_candidate"]
    if candidate is not None:
        previous = record["route_candidate"] or {}
        record["route_candidate"] = {
            "candidate_revision": _non_negative_int(
                previous.get("candidate_revision"), 0
            )
            + 1,
            "mode": "observe_only",
            "run_id": observation["run_id"],
            "policy_id": observation["policy_id"],
            "snapshot_revision": observation["snapshot_revision"],
            "provider_id": candidate["provider_id"],
            "model_id": candidate["model_id"],
            "source_route_node_id": candidate["source_route_node_id"],
            "created_at": now,
            "observed_at": now,
            "last_used_at": None,
            "expires_at": None,
        }
        _append_activity(
            record,
            {
                "at": now,
                "kind": "route_candidate_recorded",
                "phase": observation["phase"],
                "run_id": observation["run_id"],
                "policy_id": observation["policy_id"],
                "provider_id": candidate["provider_id"],
                "source_route_node_id": candidate["source_route_node_id"],
            },
        )

    request_target = observation["request_target_observation"]
    if request_target is not None:
        previous = record["last_request_target_observation"] or {}
        record["last_request_target_observation"] = {
            "observation_revision": _non_negative_int(
                previous.get("observation_revision"), 0
            )
            + 1,
            "run_id": observation["run_id"],
            "provider_id": request_target["provider_id"],
            "model_id": request_target["model_id"],
            "source": request_target["source"],
            "observed_at": now,
        }
        _append_activity(
            record,
            {
                "at": now,
                "kind": "request_target_observed",
                "phase": observation["phase"],
                "run_id": observation["run_id"],
                "provider_id": request_target["provider_id"],
                "source": request_target["source"],
            },
        )


def _is_late_foreign_phase(
    current: dict[str, Any] | None,
    run_id: str,
    phase: str,
) -> bool:
    if current is None or current.get("run_id") == run_id:
        return False
    # A message input is the start of a new event execution.  Other phases are
    # continuations, so a foreign one is necessarily an older/late event while
    # a state record already exists for this UMO.
    return phase != "message_input"


def _merge_signals(target: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    known = {
        _signal_key(item)
        for item in target
        if isinstance(item, dict)
    }
    for signal in incoming:
        key = _signal_key(signal)
        if key in known:
            continue
        target.append(copy.deepcopy(signal))
        known.add(key)


def _signal_key(signal: Mapping[str, Any]) -> str:
    return json.dumps(signal, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_activity(record: dict[str, Any], activity: dict[str, Any]) -> None:
    activities = record["activities"]
    activities["revision"] += 1
    activities["items"].append(activity)


def _prune_activity_items(record: dict[str, Any], limit: int) -> None:
    items = record["activities"]["items"]
    if len(items) > limit:
        record["activities"]["items"] = items[-limit:]


def _prune_expired_records(table: dict[str, Any], now: int, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0:
        return False
    expired_keys = [
        key
        for key, raw in table["records"].items()
        if _non_negative_int(raw.get("last_activity_at"), 0) + ttl_seconds <= now
    ]
    for key in expired_keys:
        table["records"].pop(key, None)
    return bool(expired_keys)


def _prune_capacity(table: dict[str, Any], max_entries: int, *, protect_key: str) -> bool:
    changed = False
    while len(table["records"]) > max_entries:
        candidates = [
            (key, record)
            for key, record in table["records"].items()
            if key != protect_key
        ]
        if not candidates:
            break
        key, _record = min(
            candidates,
            key=lambda item: (
                _non_negative_int(item[1].get("updated_at"), 0),
                str(item[1].get("umo", "")),
            ),
        )
        table["records"].pop(key, None)
        changed = True
    return changed


def _summary_record(record: dict[str, Any]) -> dict[str, Any]:
    result = record["last_policy_result"]
    candidate = record["route_candidate"]
    request_target = record["last_request_target_observation"]
    return {
        "umo": record["umo"],
        "record_revision": record["record_revision"],
        "updated_at": record["updated_at"],
        "last_policy_result": _summary_policy_result(result),
        "route_candidate": copy.deepcopy(candidate),
        "last_request_target_observation": copy.deepcopy(request_target),
        "activity_count": len(record["activities"]["items"]),
    }


def _summary_policy_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        key: copy.deepcopy(result.get(key))
        for key in (
            "result_revision",
            "run_id",
            "policy_id",
            "snapshot_revision",
            "last_stage",
            "outcome",
            "terminal_action",
            "observed_at",
        )
    }


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    public = copy.deepcopy(record)
    public["activities"]["items"].reverse()
    return public


def _safe_json_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return _json_clone(dict(value))
    except (TypeError, ValueError):
        return None


def _safe_json_signal_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        normalized = _safe_json_mapping(item)
        if normalized is not None:
            result.append(normalized)
    return result


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _terminal_action_summary(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return {
        key: str(value.get(key, "") or "")
        for key in ("rail", "source_kind", "node_id", "action", "target")
        if str(value.get(key, "") or "")
    }


def _monitoring_enabled(settings: Mapping[str, Any] | None) -> bool:
    return bool((settings or {}).get("enabled", False))


def _state_ttl_seconds(settings: Mapping[str, Any] | None) -> int:
    value = (settings or {}).get("state_ttl_seconds", 604_800)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 604_800
    return parsed if parsed >= 0 else 604_800


def _max_entries(settings: Mapping[str, Any] | None) -> int:
    return _positive_int((settings or {}).get("max_entries"), 500)


def _activity_log_limit(settings: Mapping[str, Any] | None) -> int:
    return _positive_int((settings or {}).get("activity_log_limit"), 50)


def _clean_identifier(value: Any, field_name: str) -> str:
    text = _safe_identifier(value)
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def _safe_identifier(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    text = str(value if value is not None else "").strip()
    return text[:MAX_IDENTIFIER_LENGTH]


def _clean_phase(value: Any) -> str:
    phase = str(value or "").strip()
    if phase not in VALID_PHASES:
        raise ValueError("phase is invalid")
    return phase


def _clean_outcome(value: Any) -> str:
    outcome = str(value or "").strip().lower()
    if outcome not in VALID_OUTCOMES:
        raise ValueError("outcome is invalid")
    return outcome


def _positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _now(clock: Callable[[], float]) -> int:
    return max(0, int(clock()))
