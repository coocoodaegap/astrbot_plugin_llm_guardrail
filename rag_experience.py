"""Persistent RAG-match experience records for the Guardrail Pages UI.

The service deliberately owns only Guardrail's local experience records.  A
document created later in an AstrBot knowledge base is outside this service's
scope and is never updated or deleted here.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import math
import time
import uuid
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

try:
    from astrbot.api import logger
except ImportError:  # pragma: no cover - local unit tests do not load AstrBot.
    logger = logging.getLogger(__name__)

try:
    from .state import StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from state import StateStore


RAG_EXPERIENCE_NAMESPACE = "rag_experience"
RAG_EXPERIENCE_TABLE_KEY = "records"
RAG_EXPERIENCE_SCHEMA_VERSION = 1
MAX_RAG_EXPERIENCE_RECORDS = 500
MAX_PAGE_SIZE = 100
MAX_IDENTIFIER_LENGTH = 512
MAX_TITLE_LENGTH = 240
MAX_CONTENT_LENGTH = 60_000
MAX_EVIDENCE_PREVIEW_LENGTH = 2_000


# StateStore offers point reads/writes only, so all instances in one event loop
# must share a table lock.  Loop-local locks keep independent unittest loops
# from retaining stale lock state.
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
class RagExperienceMutationResult:
    """Non-throwing outcome for a record mutation or runtime capture."""

    success: bool
    found: bool = False
    conflict: bool = False
    record: dict[str, Any] | None = None
    warning: str = ""


@dataclass(frozen=True)
class RagExperienceListResult:
    """Pageable, summary-only result for the experience list."""

    success: bool
    items: tuple[dict[str, Any], ...] = ()
    total: int = 0
    page: int = 1
    page_size: int = 30
    warning: str = ""


@dataclass(frozen=True)
class RagExperienceDetailResult:
    """One complete experience record for the editor Page."""

    success: bool
    found: bool = False
    record: dict[str, Any] | None = None
    warning: str = ""


class RagExperienceService:
    """Persist RAG matches and expose a minimal editable record lifecycle."""

    def __init__(
        self,
        state_store: StateStore,
        *,
        clock: Callable[[], float] | None = None,
        record_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._state_store = state_store
        self._clock = clock or time.time
        self._record_id_factory = record_id_factory or (lambda: uuid.uuid4().hex)

    async def capture_match(
        self,
        *,
        rail: Any,
        rule_id: Any,
        content: Any,
        evidence: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    ) -> RagExperienceMutationResult:
        """Store one matched ``rag_judge`` result without raising into the rail.

        The selected source is the evidence record with the highest finite
        numeric score.  If an adapter cannot provide both a score and a source
        knowledge-base name, the experience remains viewable but cannot be
        uploaded from Pages.
        """
        try:
            normalized_rail = _clean_identifier(rail, "rail")
            normalized_rule_id = _clean_identifier(rule_id, "rule_id")
            normalized_content = _clean_content(content)
            source = select_best_evidence_source(evidence)
            record_id = _clean_record_id(self._record_id_factory())
        except (TypeError, ValueError) as exc:
            return RagExperienceMutationResult(
                False,
                warning=f"rag experience capture is invalid: {exc}",
            )

        now = _now(self._clock)
        record = {
            "schema_version": RAG_EXPERIENCE_SCHEMA_VERSION,
            "record_id": record_id,
            "record_revision": 1,
            "created_at": now,
            "updated_at": now,
            "rail": normalized_rail,
            "rule_id": normalized_rule_id,
            "title": _default_title(normalized_rule_id, source),
            "content": normalized_content,
            **source,
        }
        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                while record_id in table["records"]:
                    record_id = _clean_record_id(self._record_id_factory())
                    record["record_id"] = record_id
                table["records"][record_id] = record
                _prune_capacity(table, MAX_RAG_EXPERIENCE_RECORDS)
                table["table_revision"] += 1
                await self._save_table_locked(table)
        except Exception as exc:  # Capturing experience must never break a rail.
            self._log_storage_failure("capture RAG experience", exc)
            return RagExperienceMutationResult(
                False,
                warning="rag experience could not be recorded",
            )
        return RagExperienceMutationResult(
            True,
            found=True,
            record=_public_record(record),
        )

    async def list_records(
        self,
        *,
        query: Any = "",
        page: Any = 1,
        page_size: Any = 30,
    ) -> RagExperienceListResult:
        """Return newest records first, without loading full editor content."""
        try:
            normalized_page = _positive_int(page, 1)
            normalized_page_size = min(_positive_int(page_size, 30), MAX_PAGE_SIZE)
            query_text = str(query or "").strip().casefold()
        except (TypeError, ValueError) as exc:
            return RagExperienceListResult(False, warning=str(exc))

        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                records = list(table["records"].values())
        except Exception as exc:
            self._log_storage_failure("list RAG experience", exc)
            return RagExperienceListResult(
                False,
                warning="rag experience is unavailable",
            )

        summaries = [_summary_record(record) for record in records]
        if query_text:
            summaries = [
                item
                for item in summaries
                if query_text
                in " ".join(
                    str(item.get(key, "") or "")
                    for key in (
                        "title",
                        "rule_id",
                        "rail",
                        "source_kb_name",
                        "source_doc_name",
                        "content_preview",
                    )
                ).casefold()
            ]
        summaries.sort(
            key=lambda item: (-_non_negative_int(item.get("updated_at"), 0), item["record_id"])
        )
        total = len(summaries)
        offset = (normalized_page - 1) * normalized_page_size
        return RagExperienceListResult(
            True,
            items=tuple(
                copy.deepcopy(summaries[offset : offset + normalized_page_size])
            ),
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        )

    async def get_record(self, record_id: Any) -> RagExperienceDetailResult:
        """Read one experience record without changing it."""
        try:
            normalized_record_id = _clean_record_id(record_id)
        except (TypeError, ValueError) as exc:
            return RagExperienceDetailResult(False, warning=str(exc))
        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                record = table["records"].get(normalized_record_id)
        except Exception as exc:
            self._log_storage_failure("read RAG experience", exc)
            return RagExperienceDetailResult(
                False,
                warning="rag experience is unavailable",
            )
        if not isinstance(record, dict):
            return RagExperienceDetailResult(True, found=False)
        return RagExperienceDetailResult(
            True,
            found=True,
            record=_public_record(record),
        )

    async def update_record(
        self,
        record_id: Any,
        *,
        expected_revision: Any,
        title: Any,
        content: Any,
    ) -> RagExperienceMutationResult:
        """Replace editable fields only when the Page revision still matches."""
        try:
            normalized_record_id = _clean_record_id(record_id)
            expected = _positive_int(expected_revision, 1)
            normalized_title = _clean_title(title)
            normalized_content = _clean_content(content)
        except (TypeError, ValueError) as exc:
            return RagExperienceMutationResult(False, warning=str(exc))

        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                record = table["records"].get(normalized_record_id)
                if not isinstance(record, dict):
                    return RagExperienceMutationResult(True, found=False)
                if record["record_revision"] != expected:
                    return RagExperienceMutationResult(
                        True,
                        found=True,
                        conflict=True,
                        record=_public_record(record),
                        warning="record revision conflict",
                    )
                record["title"] = normalized_title
                record["content"] = normalized_content
                record["updated_at"] = _now(self._clock)
                record["record_revision"] += 1
                table["table_revision"] += 1
                await self._save_table_locked(table)
        except Exception as exc:
            self._log_storage_failure("update RAG experience", exc)
            return RagExperienceMutationResult(
                False,
                warning="rag experience could not be updated",
            )
        return RagExperienceMutationResult(
            True,
            found=True,
            record=_public_record(record),
        )

    async def delete_record(
        self,
        record_id: Any,
        *,
        expected_revision: Any,
    ) -> RagExperienceMutationResult:
        """Delete only the local Guardrail record, never a KB document."""
        try:
            normalized_record_id = _clean_record_id(record_id)
            expected = _positive_int(expected_revision, 1)
        except (TypeError, ValueError) as exc:
            return RagExperienceMutationResult(False, warning=str(exc))

        try:
            async with _shared_table_lock():
                table = await self._load_table_locked()
                record = table["records"].get(normalized_record_id)
                if not isinstance(record, dict):
                    return RagExperienceMutationResult(True, found=False)
                if record["record_revision"] != expected:
                    return RagExperienceMutationResult(
                        True,
                        found=True,
                        conflict=True,
                        record=_public_record(record),
                        warning="record revision conflict",
                    )
                removed = _public_record(record)
                del table["records"][normalized_record_id]
                table["table_revision"] += 1
                await self._save_table_locked(table)
        except Exception as exc:
            self._log_storage_failure("delete RAG experience", exc)
            return RagExperienceMutationResult(
                False,
                warning="rag experience could not be deleted",
            )
        return RagExperienceMutationResult(True, found=True, record=removed)

    async def _load_table_locked(self) -> dict[str, Any]:
        raw = await self._state_store.get(
            RAG_EXPERIENCE_NAMESPACE,
            RAG_EXPERIENCE_TABLE_KEY,
            None,
        )
        if not isinstance(raw, dict):
            return _empty_table()
        raw_records = raw.get("records")
        records: dict[str, dict[str, Any]] = {}
        if isinstance(raw_records, dict):
            for key, value in raw_records.items():
                record = _normalized_record(value, fallback_record_id=key)
                if record is not None:
                    records[record["record_id"]] = record
        return {
            "schema_version": RAG_EXPERIENCE_SCHEMA_VERSION,
            "table_revision": _non_negative_int(raw.get("table_revision"), 0),
            "records": records,
        }

    async def _save_table_locked(self, table: dict[str, Any]) -> None:
        await self._state_store.set(
            RAG_EXPERIENCE_NAMESPACE,
            RAG_EXPERIENCE_TABLE_KEY,
            table,
        )

    @staticmethod
    def _log_storage_failure(action: str, exc: Exception) -> None:
        warning = getattr(logger, "warning", None)
        if callable(warning):
            warning("[LLMGuardrail] failed to %s: %s", action, exc)


def select_best_evidence_source(
    evidence: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
) -> dict[str, Any]:
    """Project the highest-scoring evidence into stable source fields.

    A source is deliberately absent when no finite score or no knowledge-base
    name is available.  That avoids silently choosing a configured but
    non-winning knowledge base on compatibility/fallback retrieval paths.
    """
    best: tuple[float, int, Mapping[str, Any]] | None = None
    for index, item in enumerate(evidence or ()):
        if not isinstance(item, Mapping):
            continue
        score = _finite_float(item.get("score"))
        if score is None:
            continue
        if best is None or score > best[0]:
            best = (score, index, item)
    if best is None:
        return _empty_source()

    score, _index, item = best
    metadata = item.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    kb_name = _safe_text(metadata.get("kb_name"), MAX_IDENTIFIER_LENGTH)
    if not kb_name:
        return _empty_source()
    return {
        "source_kb_id": _safe_text(metadata.get("kb_id"), MAX_IDENTIFIER_LENGTH),
        "source_kb_name": kb_name,
        "source_doc_id": _safe_text(metadata.get("doc_id"), MAX_IDENTIFIER_LENGTH),
        "source_doc_name": _safe_text(
            metadata.get("doc_name"), MAX_IDENTIFIER_LENGTH
        ),
        "source_score": score,
        "source_evidence_preview": _safe_text(
            item.get("text"), MAX_EVIDENCE_PREVIEW_LENGTH
        ),
    }


def _empty_table() -> dict[str, Any]:
    return {
        "schema_version": RAG_EXPERIENCE_SCHEMA_VERSION,
        "table_revision": 0,
        "records": {},
    }


def _empty_source() -> dict[str, Any]:
    return {
        "source_kb_id": "",
        "source_kb_name": "",
        "source_doc_id": "",
        "source_doc_name": "",
        "source_score": None,
        "source_evidence_preview": "",
    }


def _normalized_record(raw: Any, *, fallback_record_id: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    try:
        record_id = _clean_record_id(raw.get("record_id", fallback_record_id))
        rail = _clean_identifier(raw.get("rail"), "rail")
        rule_id = _clean_identifier(raw.get("rule_id"), "rule_id")
        title = _clean_title(raw.get("title"))
        content = _clean_content(raw.get("content"))
    except (TypeError, ValueError):
        return None
    source = _empty_source()
    source.update(
        {
            "source_kb_id": _safe_text(raw.get("source_kb_id"), MAX_IDENTIFIER_LENGTH),
            "source_kb_name": _safe_text(raw.get("source_kb_name"), MAX_IDENTIFIER_LENGTH),
            "source_doc_id": _safe_text(raw.get("source_doc_id"), MAX_IDENTIFIER_LENGTH),
            "source_doc_name": _safe_text(raw.get("source_doc_name"), MAX_IDENTIFIER_LENGTH),
            "source_score": _finite_float(raw.get("source_score")),
            "source_evidence_preview": _safe_text(
                raw.get("source_evidence_preview"), MAX_EVIDENCE_PREVIEW_LENGTH
            ),
        }
    )
    created_at = _non_negative_int(raw.get("created_at"), 0)
    updated_at = _non_negative_int(raw.get("updated_at"), created_at)
    if not created_at:
        created_at = updated_at
    return {
        "schema_version": RAG_EXPERIENCE_SCHEMA_VERSION,
        "record_id": record_id,
        "record_revision": max(_positive_int_or_default(raw.get("record_revision"), 1), 1),
        "created_at": created_at,
        "updated_at": updated_at,
        "rail": rail,
        "rule_id": rule_id,
        "title": title,
        "content": content,
        **source,
    }


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(record))


def _summary_record(record: Mapping[str, Any]) -> dict[str, Any]:
    content = str(record.get("content", "") or "")
    return {
        "record_id": record["record_id"],
        "record_revision": record["record_revision"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "rail": record["rail"],
        "rule_id": record["rule_id"],
        "title": record["title"],
        "source_kb_name": record["source_kb_name"],
        "source_doc_name": record["source_doc_name"],
        "source_score": record["source_score"],
        "content_preview": _preview(content, 180),
    }


def _prune_capacity(table: dict[str, Any], max_entries: int) -> None:
    records = table["records"]
    overflow = len(records) - max_entries
    if overflow <= 0:
        return
    for record_id, _record in sorted(
        records.items(),
        key=lambda pair: (
            _non_negative_int(pair[1].get("updated_at"), 0),
            pair[0],
        ),
    )[:overflow]:
        del records[record_id]


def _default_title(rule_id: str, source: Mapping[str, Any]) -> str:
    source_doc = _safe_text(source.get("source_doc_name"), MAX_TITLE_LENGTH)
    return _clean_title(source_doc or f"RAG experience · {rule_id}")


def _clean_record_id(value: Any) -> str:
    record_id = _safe_text(value, MAX_IDENTIFIER_LENGTH)
    if not record_id:
        raise ValueError("record_id must not be empty")
    return record_id


def _clean_identifier(value: Any, field_name: str) -> str:
    identifier = _safe_text(value, MAX_IDENTIFIER_LENGTH)
    if not identifier:
        raise ValueError(f"{field_name} must not be empty")
    return identifier


def _clean_title(value: Any) -> str:
    title = _safe_text(value, MAX_TITLE_LENGTH)
    if not title:
        raise ValueError("title must not be empty")
    return title


def _clean_content(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("content must be a string")
    if len(value) > MAX_CONTENT_LENGTH:
        raise ValueError(f"content exceeds {MAX_CONTENT_LENGTH} characters")
    return value


def _safe_text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:limit]


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        raise ValueError("page and page_size must be integers")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("page and page_size must be integers") from exc
    if result < 1:
        raise ValueError("page and page_size must be at least 1")
    return result


def _positive_int_or_default(value: Any, default: int) -> int:
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


def _now(clock: Callable[[], float]) -> int:
    try:
        return max(0, int(clock()))
    except (TypeError, ValueError, OverflowError):
        return 0


def _preview(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…"
