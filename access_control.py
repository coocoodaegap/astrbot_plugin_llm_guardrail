"""Persistent, principal-scoped input access control for P2.

The AstrBot KV API deliberately exposes only point reads and writes.  This
module therefore stores the small access-control registry as one document and
serializes each read-modify-write operation.  A principal-specific lock is
acquired first so automatic enforcement and operator actions for the same
person are linearizable even when they arrive through different UMOs.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    from astrbot.api import logger
except ImportError:  # pragma: no cover - local tests do not load AstrBot.
    logger = logging.getLogger(__name__)

try:
    from .session_lock import PrincipalLockManager, get_global_principal_lock_manager
    from .state import StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from session_lock import PrincipalLockManager, get_global_principal_lock_manager
    from state import StateStore


ACCESS_CONTROL_NAMESPACE = "access_control"
ACCESS_CONTROL_TABLE_KEY = "principal_records"
ACCESS_CONTROL_SCHEMA_VERSION = 2

DECISION_NONE = "none"
DECISION_BAN = "ban"
DECISION_PARDON = "pardon"
VALID_DECISIONS = frozenset((DECISION_NONE, DECISION_BAN, DECISION_PARDON))
ACTIVE_DECISIONS = frozenset((DECISION_BAN, DECISION_PARDON))

SOURCE_AUTOMATIC = "automatic"
SOURCE_MANUAL = "manual"
VALID_SOURCES = frozenset((SOURCE_AUTOMATIC, SOURCE_MANUAL))

REASON_AUTOMATIC_THRESHOLD = "automatic_threshold"
REASON_INPUT_TERMINAL_BLOCK = "input_terminal_block"
REASON_MANUAL_BAN = "manual_ban"
REASON_MANUAL_PARDON = "manual_pardon"
REASON_MANUAL_COMMAND = "manual_command"
REASON_APPEAL_APPROVED = "appeal_approved"
REASON_TRUSTED_PRINCIPAL = "trusted_principal"

REASON_CODE_LABELS: dict[str, str] = {
    REASON_AUTOMATIC_THRESHOLD: "达到自动封禁阈值",
    REASON_INPUT_TERMINAL_BLOCK: "输入检测终止性拦截",
    REASON_MANUAL_BAN: "手动封禁",
    REASON_MANUAL_PARDON: "手动赦免",
    REASON_MANUAL_COMMAND: "指令操作",
    REASON_APPEAL_APPROVED: "申诉通过",
    REASON_TRUSTED_PRINCIPAL: "受信任主体",
}
MANUAL_BAN_REASON_CODES = frozenset((REASON_MANUAL_BAN, REASON_MANUAL_COMMAND))
MANUAL_PARDON_REASON_CODES = frozenset(
    (
        REASON_MANUAL_PARDON,
        REASON_MANUAL_COMMAND,
        REASON_APPEAL_APPROVED,
        REASON_TRUSTED_PRINCIPAL,
    )
)

MAX_PRINCIPAL_PART_LENGTH = 256


# A StateStore registry is stored as one small KV document because AstrBot's
# public KV contract does not provide an atomic enumerate-and-update API.  A
# service may be rebuilt while another one still drains callbacks, so this lock
# must be shared by all service instances in the same event loop—not merely by
# one AccessControlService object.  Locks remain loop-local to avoid binding an
# asyncio primitive to a closed test/event loop.
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
class PrincipalIdentity:
    """A platform-scoped user identity, independent of a conversation UMO."""

    platform_id: str
    user_id: str

    @property
    def principal_id(self) -> str:
        return f"{self.platform_id}:{self.user_id}"

    @property
    def storage_key(self) -> str:
        """Return a collision-free key even if an adapter ID contains ``:``."""

        return json.dumps(
            [self.platform_id, self.user_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class AccessAdmission:
    """The access-control decision for one incoming event."""

    allowed: bool
    decision: str = DECISION_NONE
    principal_id: str = ""
    notify: bool = False
    warning: str = ""


@dataclass(frozen=True)
class ViolationResult:
    """Result of recording one successfully committed Step 1 block."""

    recorded: bool
    automatic_ban: bool = False
    violation_count: int = 0
    decision: str = DECISION_NONE
    warning: str = ""


@dataclass(frozen=True)
class AccessMutationResult:
    """Result returned to the Pages API for an operator mutation."""

    success: bool
    record: dict[str, Any] | None = None
    conflict: bool = False
    error: str = ""


@dataclass(frozen=True)
class AccessListResult:
    """Result returned when listing active access-control decisions."""

    success: bool
    records: tuple[dict[str, Any], ...] = ()
    warning: str = ""


def make_principal_identity(platform_id: Any, user_id: Any) -> PrincipalIdentity:
    """Validate and normalize an explicit platform/user identity.

    The runtime adapter calls this only after it has read AstrBot's public
    event methods.  Pages uses the same validator, keeping manual actions and
    automatic enforcement on exactly the same identity namespace.
    """

    platform = _clean_principal_part(platform_id, "platform_id")
    user = _clean_principal_part(user_id, "user_id")
    return PrincipalIdentity(platform_id=platform, user_id=user)


def _clean_principal_part(value: Any, field_name: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-empty string or number")
    text = str(value if value is not None else "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > MAX_PRINCIPAL_PART_LENGTH:
        raise ValueError(f"{field_name} is too long")
    return text


class AccessControlService:
    """Coordinate automatic and manual principal-level access decisions.

    Lock order is always ``principal lock -> table lock``.  No caller here
    acquires a UMO lock; the host's message pipeline may already hold one.
    """

    def __init__(
        self,
        state_store: StateStore,
        *,
        principal_locks: PrincipalLockManager | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._state_store = state_store
        self._principal_locks = principal_locks or get_global_principal_lock_manager()
        self._clock = clock or time.time

    async def admit(
        self,
        principal: PrincipalIdentity,
        *,
        blacklist_message_interval_minutes: int = 5,
    ) -> AccessAdmission:
        """Read the active decision, expiring a temporary decision if needed.

        Storage failures deliberately fail open.  The warning is returned to
        the pipeline for diagnostics but never sent as a user-facing message.
        """

        try:
            interval = _notice_interval_minutes(blacklist_message_interval_minutes)
            admission, _record = await self._mutate_principal(
                principal,
                lambda record, now: self._admit_mutation(
                    record,
                    now,
                    blacklist_message_interval_minutes=interval,
                ),
            )
            return admission
        except Exception as exc:  # External KV backends may raise backend-specific errors.
            self._log_storage_failure("read access decision", exc)
            return AccessAdmission(
                allowed=True,
                decision=DECISION_NONE,
                principal_id=principal.principal_id,
                warning="access control state is unavailable; fail open",
            )

    async def record_terminal_input_block(
        self,
        principal: PrincipalIdentity,
        settings: dict[str, Any],
    ) -> ViolationResult:
        """Record exactly one successfully committed terminal Step 1 block."""

        if not bool(settings.get("auto_blacklist_enabled", False)):
            return ViolationResult(recorded=False)

        threshold = _positive_int(settings.get("blacklist_max_violations"), 3)
        duration_minutes = _duration_minutes(
            settings.get("blacklist_duration_minutes"),
            default=60,
        )
        try:
            result, _record = await self._mutate_principal(
                principal,
                lambda record, now: self._violation_mutation(
                    record,
                    now,
                    threshold=threshold,
                    duration_minutes=duration_minutes,
                ),
            )
            return result
        except Exception as exc:  # External KV backends may raise backend-specific errors.
            self._log_storage_failure("record access violation", exc)
            return ViolationResult(
                recorded=False,
                warning="access control state could not record this violation",
            )

    async def set_manual_decision(
        self,
        principal: PrincipalIdentity,
        decision: str,
        duration_minutes: int,
        reason_code: str,
        *,
        expected_record_revision: int | None = None,
    ) -> AccessMutationResult:
        """Replace the active decision with a manual ban or pardon."""

        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in ACTIVE_DECISIONS:
            return AccessMutationResult(False, error="decision must be ban or pardon")
        try:
            normalized_duration = _duration_minutes(duration_minutes, default=None)
        except ValueError:
            return AccessMutationResult(
                False,
                error="duration_minutes must be -1 or a positive integer",
            )
        try:
            normalized_reason = _manual_reason_code(normalized_decision, reason_code)
        except ValueError:
            return AccessMutationResult(False, error="reason_code is invalid for this decision")
        if expected_record_revision is not None and (
            isinstance(expected_record_revision, bool)
            or not isinstance(expected_record_revision, int)
            or expected_record_revision < 0
        ):
            return AccessMutationResult(False, error="expected_record_revision must be a non-negative integer")

        try:
            outcome, record = await self._mutate_principal(
                principal,
                lambda current, now: self._manual_decision_mutation(
                    current,
                    now,
                    decision=normalized_decision,
                    duration_minutes=normalized_duration,
                    reason_code=normalized_reason,
                    expected_record_revision=expected_record_revision,
                ),
            )
            if outcome == "conflict":
                return AccessMutationResult(
                    False,
                    record=_public_record(record),
                    conflict=True,
                    error="the access decision changed; refresh and try again",
                )
            return AccessMutationResult(True, record=_public_record(record))
        except Exception as exc:  # External KV backends may raise backend-specific errors.
            self._log_storage_failure("save manual access decision", exc)
            return AccessMutationResult(False, error="access-control state could not be saved")

    async def clear_manual_decision(
        self,
        principal: PrincipalIdentity,
        *,
        expected_decision: str,
        expected_record_revision: int | None = None,
    ) -> AccessMutationResult:
        """Clear a displayed ban/pardon without overwriting a newer decision.

        ``expected_decision`` and the optional record revision are a small
        compare-and-set guard for stale Pages views.  A new manual decision is
        intentionally a replacement operation; clearing is not.
        """

        decision = str(expected_decision or "").strip().lower()
        if decision not in ACTIVE_DECISIONS:
            return AccessMutationResult(False, error="expected_decision must be ban or pardon")
        if expected_record_revision is not None and (
            isinstance(expected_record_revision, bool)
            or not isinstance(expected_record_revision, int)
            or expected_record_revision < 0
        ):
            return AccessMutationResult(False, error="expected_record_revision must be a non-negative integer")

        try:
            outcome, record = await self._mutate_principal(
                principal,
                lambda current, now: self._clear_mutation(
                    current,
                    now,
                    expected_decision=decision,
                    expected_record_revision=expected_record_revision,
                ),
            )
            if outcome == "conflict":
                return AccessMutationResult(
                    False,
                    record=_public_record(record),
                    conflict=True,
                    error="the access decision changed; refresh and try again",
                )
            return AccessMutationResult(True, record=_public_record(record))
        except Exception as exc:  # External KV backends may raise backend-specific errors.
            self._log_storage_failure("clear manual access decision", exc)
            return AccessMutationResult(False, error="access-control state could not be saved")

    async def list_active_records(self) -> AccessListResult:
        """List active bans and pardons without relying on KV key enumeration."""

        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                identities = tuple(
                    identity
                    for raw_record in table["records"].values()
                    if (identity := _identity_from_record(raw_record)) is not None
                )
        except Exception as exc:  # External KV backends may raise backend-specific errors.
            self._log_storage_failure("list access decisions", exc)
            return AccessListResult(False, warning="access-control state is unavailable")

        records: list[dict[str, Any]] = []
        for identity in identities:
            try:
                _result, record = await self._mutate_principal(
                    identity,
                    self._read_active_mutation,
                )
            except Exception as exc:  # One malformed/stale record must not hide the rest.
                self._log_storage_failure("read listed access decision", exc)
                continue
            if record["decision"] in ACTIVE_DECISIONS:
                records.append(_public_record(record))
        records.sort(
            key=lambda record: (
                record["decision"],
                record["platform_id"],
                record["user_id"],
            )
        )
        return AccessListResult(True, records=tuple(records))

    async def get_active_record(
        self, principal: PrincipalIdentity
    ) -> dict[str, Any] | None:
        """Return a current active record, mainly for administrative status."""

        try:
            _result, record = await self._mutate_principal(
                principal,
                self._read_active_mutation,
            )
        except Exception as exc:  # External KV backends may raise backend-specific errors.
            self._log_storage_failure("read active access decision", exc)
            return None
        return _public_record(record) if record["decision"] in ACTIVE_DECISIONS else None

    async def _mutate_principal(
        self,
        principal: PrincipalIdentity,
        mutation: Callable[[dict[str, Any], int], Any],
    ) -> tuple[Any, dict[str, Any]]:
        """Run one mutation under the documented principal/table lock order."""

        async with self._principal_locks.hold(principal.storage_key):
            async with _shared_table_lock():
                table = await self._load_table_locked()
                previous = table["records"].get(principal.storage_key)
                record = _normalized_record(previous, principal)
                before = copy.deepcopy(record)
                now = _now(self._clock)
                result = mutation(record, now)
                if record != before:
                    record["record_revision"] = before["record_revision"] + 1
                    record["updated_at"] = now
                    table["records"][principal.storage_key] = record
                    table["table_revision"] += 1
                    await self._state_store.set(
                        ACCESS_CONTROL_NAMESPACE,
                        ACCESS_CONTROL_TABLE_KEY,
                        table,
                    )
                return result, copy.deepcopy(record)

    async def _load_table_locked(self) -> dict[str, Any]:
        raw = await self._state_store.get(
            ACCESS_CONTROL_NAMESPACE,
            ACCESS_CONTROL_TABLE_KEY,
            None,
        )
        if not isinstance(raw, dict):
            return _empty_table()
        records = raw.get("records")
        if not isinstance(records, dict):
            records = {}
        return {
            "schema_version": ACCESS_CONTROL_SCHEMA_VERSION,
            "table_revision": _non_negative_int(raw.get("table_revision"), 0),
            "records": {
                str(key): copy.deepcopy(value)
                for key, value in records.items()
                if isinstance(value, dict)
            },
        }

    @staticmethod
    def _admit_mutation(
        record: dict[str, Any],
        now: int,
        *,
        blacklist_message_interval_minutes: int,
    ) -> AccessAdmission:
        _expire_if_needed(record, now)
        decision = record["decision"]
        notify = False
        if decision == DECISION_BAN and blacklist_message_interval_minutes >= 0:
            last_notice_at = record["last_blacklist_notice_at"]
            if (
                blacklist_message_interval_minutes == 0
                or last_notice_at == 0
                or now - last_notice_at
                >= blacklist_message_interval_minutes * 60
            ):
                notify = True
                record["last_blacklist_notice_at"] = now
        return AccessAdmission(
            allowed=decision != DECISION_BAN,
            decision=decision,
            principal_id=record["principal_id"],
            notify=notify,
        )

    @staticmethod
    def _read_active_mutation(record: dict[str, Any], now: int) -> None:
        _expire_if_needed(record, now)
        return None

    @staticmethod
    def _violation_mutation(
        record: dict[str, Any],
        now: int,
        *,
        threshold: int,
        duration_minutes: int,
    ) -> ViolationResult:
        _expire_if_needed(record, now)
        if record["decision"] == DECISION_PARDON:
            return ViolationResult(
                recorded=False,
                violation_count=record["violation_count"],
                decision=DECISION_PARDON,
            )
        if record["decision"] == DECISION_BAN:
            return ViolationResult(
                recorded=False,
                violation_count=record["violation_count"],
                decision=DECISION_BAN,
            )

        record["violation_count"] += 1
        record["last_violation_at"] = now
        record["last_violation_reason_code"] = REASON_INPUT_TERMINAL_BLOCK
        automatic_ban = record["violation_count"] >= threshold
        if automatic_ban:
            _set_decision(
                record,
                decision=DECISION_BAN,
                expires_at=_expires_at(now, duration_minutes),
                source=SOURCE_AUTOMATIC,
                reason_code=REASON_AUTOMATIC_THRESHOLD,
            )
        return ViolationResult(
            recorded=True,
            automatic_ban=automatic_ban,
            violation_count=record["violation_count"],
            decision=record["decision"],
        )

    @staticmethod
    def _manual_decision_mutation(
        record: dict[str, Any],
        now: int,
        *,
        decision: str,
        duration_minutes: int,
        reason_code: str,
        expected_record_revision: int | None,
    ) -> str:
        _expire_if_needed(record, now)
        if expected_record_revision is not None and (
            record["record_revision"] != expected_record_revision
        ):
            return "conflict"
        if (
            expected_record_revision is None
            and record["decision"] in ACTIVE_DECISIONS
        ):
            return "conflict"
        _set_decision(
            record,
            decision=decision,
            expires_at=_expires_at(now, duration_minutes),
            source=SOURCE_MANUAL,
            reason_code=reason_code,
        )
        if decision == DECISION_PARDON:
            _reset_violation_count(record)
        return "saved"

    @staticmethod
    def _clear_mutation(
        record: dict[str, Any],
        now: int,
        *,
        expected_decision: str,
        expected_record_revision: int | None,
    ) -> str:
        _expire_if_needed(record, now)
        if record["decision"] != expected_decision:
            return "conflict"
        if (
            expected_record_revision is not None
            and record["record_revision"] != expected_record_revision
        ):
            return "conflict"
        _clear_decision(record)
        _reset_violation_count(record)
        return "cleared"

    @staticmethod
    def _log_storage_failure(operation: str, exc: Exception) -> None:
        logger.warning(
            "[LLMGuardrail] access control failed to %s: %s",
            operation,
            type(exc).__name__,
        )


def _empty_table() -> dict[str, Any]:
    return {
        "schema_version": ACCESS_CONTROL_SCHEMA_VERSION,
        "table_revision": 0,
        "records": {},
    }


def _empty_record(principal: PrincipalIdentity) -> dict[str, Any]:
    return {
        "principal_id": principal.principal_id,
        "platform_id": principal.platform_id,
        "user_id": principal.user_id,
        "decision": DECISION_NONE,
        "decision_expires_at": None,
        "decision_source": "",
        "decision_reason_code": "",
        "violation_count": 0,
        "last_violation_at": 0,
        "last_violation_reason_code": "",
        "last_blacklist_notice_at": 0,
        "updated_at": 0,
        "record_revision": 0,
    }


def _normalized_record(raw: Any, principal: PrincipalIdentity) -> dict[str, Any]:
    record = _empty_record(principal)
    if not isinstance(raw, dict):
        return record
    # Schema v1 used ``sender_id``.  Do not silently migrate or honor that
    # state: an old storage key can collide with the v2 key for the same text.
    # Only a record that explicitly identifies this v2 principal is readable.
    if _identity_from_record(raw) != principal:
        return record

    decision = str(raw.get("decision", DECISION_NONE) or "").strip().lower()
    if decision not in VALID_DECISIONS:
        decision = DECISION_NONE
    expiration = raw.get("decision_expires_at")
    if decision == DECISION_NONE:
        expiration = None
    elif isinstance(expiration, bool):
        decision = DECISION_NONE
        expiration = None
    else:
        try:
            expiration = int(expiration)
        except (TypeError, ValueError):
            decision = DECISION_NONE
            expiration = None
        if expiration is not None and expiration < 0:
            decision = DECISION_NONE
            expiration = None

    source = str(raw.get("decision_source", "") or "").strip().lower()
    reason = str(raw.get("decision_reason_code", "") or "").strip()
    if decision == DECISION_NONE:
        source = ""
        reason = ""
    elif source not in VALID_SOURCES:
        source = SOURCE_MANUAL
    if reason not in REASON_CODE_LABELS:
        reason = ""

    record.update(
        {
            "decision": decision,
            "decision_expires_at": expiration,
            "decision_source": source,
            "decision_reason_code": reason,
            "violation_count": _non_negative_int(raw.get("violation_count"), 0),
            "last_violation_at": _non_negative_int(raw.get("last_violation_at"), 0),
            "last_violation_reason_code": _known_reason_code(
                raw.get("last_violation_reason_code")
            ),
            "last_blacklist_notice_at": _non_negative_int(
                raw.get("last_blacklist_notice_at"), 0
            ),
            "updated_at": _non_negative_int(raw.get("updated_at"), 0),
            "record_revision": _non_negative_int(raw.get("record_revision"), 0),
        }
    )
    return record


def _identity_from_record(raw: Any) -> PrincipalIdentity | None:
    if not isinstance(raw, dict):
        return None
    try:
        return make_principal_identity(raw.get("platform_id"), raw.get("user_id"))
    except (TypeError, ValueError):
        return None


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    decision_reason = record["decision_reason_code"]
    violation_reason = record["last_violation_reason_code"]
    return {
        "principal_id": record["principal_id"],
        "platform_id": record["platform_id"],
        "user_id": record["user_id"],
        "decision": record["decision"],
        "decision_expires_at": record["decision_expires_at"],
        "decision_source": record["decision_source"],
        "decision_reason_code": decision_reason,
        "decision_reason_label": REASON_CODE_LABELS.get(decision_reason, ""),
        "violation_count": record["violation_count"],
        "last_violation_at": record["last_violation_at"],
        "last_violation_reason_code": violation_reason,
        "last_violation_reason_label": REASON_CODE_LABELS.get(violation_reason, ""),
        "updated_at": record["updated_at"],
        "record_revision": record["record_revision"],
    }


def _expire_if_needed(record: dict[str, Any], now: int) -> bool:
    expiration = record["decision_expires_at"]
    if (
        record["decision"] in ACTIVE_DECISIONS
        and isinstance(expiration, int)
        and expiration > 0
        and expiration <= now
    ):
        _clear_decision(record)
        _reset_violation_count(record)
        return True
    return False


def _set_decision(
    record: dict[str, Any],
    *,
    decision: str,
    expires_at: int,
    source: str,
    reason_code: str,
) -> None:
    record["decision"] = decision
    record["decision_expires_at"] = expires_at
    record["decision_source"] = source
    record["decision_reason_code"] = reason_code
    record["last_blacklist_notice_at"] = 0


def _clear_decision(record: dict[str, Any]) -> None:
    record["decision"] = DECISION_NONE
    record["decision_expires_at"] = None
    record["decision_source"] = ""
    record["decision_reason_code"] = ""
    record["last_blacklist_notice_at"] = 0


def _reset_violation_count(record: dict[str, Any]) -> None:
    record["violation_count"] = 0
    record["last_violation_at"] = 0
    record["last_violation_reason_code"] = ""


def _expires_at(now: int, duration_minutes: int) -> int:
    if duration_minutes == -1:
        return 0
    return now + duration_minutes * 60


def _notice_interval_minutes(value: Any) -> int:
    """Defensively normalize the configured per-principal notice interval."""

    if isinstance(value, bool):
        return 5
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return 5
    return interval if interval >= -1 else 5


def _duration_minutes(value: Any, default: int | None) -> int:
    if isinstance(value, bool):
        if default is None:
            raise ValueError("duration is invalid")
        return default
    try:
        duration = int(value)
    except (TypeError, ValueError):
        if default is None:
            raise ValueError("duration is invalid") from None
        return default
    if duration == -1 or duration > 0:
        return duration
    if default is None:
        raise ValueError("duration is invalid")
    return default


def _positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


def _non_negative_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 0 else default


def _known_reason_code(value: Any) -> str:
    code = str(value or "").strip()
    return code if code in REASON_CODE_LABELS else ""


def _manual_reason_code(decision: str, value: Any) -> str:
    code = str(value or "").strip()
    if not code:
        return REASON_MANUAL_BAN if decision == DECISION_BAN else REASON_MANUAL_PARDON
    allowed = (
        MANUAL_BAN_REASON_CODES
        if decision == DECISION_BAN
        else MANUAL_PARDON_REASON_CODES
    )
    if code not in allowed:
        raise ValueError("reason code is invalid")
    return code


def _now(clock: Callable[[], float]) -> int:
    try:
        value = int(clock())
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(value, 0)
