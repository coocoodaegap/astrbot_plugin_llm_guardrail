"""Normalization and bounded rendering for P4 conversation context."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


CONTEXT_EXTRACTOR_SCHEMA = "guardrail.context_extractor/v1"
CONTEXT_EXTRACTOR_MAX_CHARS = 12_000


@dataclass(frozen=True)
class ContextExtraction:
    """One consumer-ready snapshot of the shared conversation history."""

    value: str
    requested_turns: int
    actual_turns: int
    user_only: bool
    truncated: bool
    diagnostic: str

    def payload(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "schema": CONTEXT_EXTRACTOR_SCHEMA,
            "requested_turns": self.requested_turns,
            "actual_turns": self.actual_turns,
            "user_only": self.user_only,
            "truncated": self.truncated,
            "diagnostic": self.diagnostic,
        }


def build_context_extraction(
    history: Any,
    *,
    turns: int,
    user_only: bool,
    current_input: str = "",
    current_request: str = "",
    current_output: str = "",
    max_chars: int = CONTEXT_EXTRACTOR_MAX_CHARS,
) -> ContextExtraction:
    """Convert an AstrBot/OpenAI-style history list to bounded neutral text.

    The caller owns the history read and may reuse one raw list for multiple
    nodes.  This function never mutates that source list.
    """

    requested_turns = max(int(turns), 0)
    if requested_turns == 0:
        return ContextExtraction(
            value="",
            requested_turns=0,
            actual_turns=0,
            user_only=bool(user_only),
            truncated=False,
            diagnostic="turns_disabled",
        )
    if not isinstance(history, list):
        return _empty_extraction(requested_turns, user_only, "history_malformed")

    items = _normalize_history_items(history)
    _exclude_current_turn(
        items,
        current_input=current_input,
        current_request=current_request,
        current_output=current_output,
    )
    selected = _select_recent_turns(items, requested_turns, bool(user_only))
    if not selected:
        return _empty_extraction(requested_turns, user_only, "history_empty")

    bounded_items, truncated = _bound_items(selected, max(max_chars, 256))
    if not bounded_items:
        return _empty_extraction(requested_turns, user_only, "history_empty")
    return ContextExtraction(
        value=_render_items(bounded_items),
        requested_turns=requested_turns,
        actual_turns=sum(1 for item in bounded_items if "user_text" in item),
        user_only=bool(user_only),
        truncated=truncated,
        diagnostic="ok",
    )


def _empty_extraction(
    requested_turns: int, user_only: bool, diagnostic: str
) -> ContextExtraction:
    return ContextExtraction(
        value="",
        requested_turns=requested_turns,
        actual_turns=0,
        user_only=bool(user_only),
        truncated=False,
        diagnostic=diagnostic,
    )


def _normalize_history_items(history: list[Any]) -> list[dict[str, str]]:
    """Keep only user/assistant text while preserving unusable records as notes."""

    items: list[dict[str, str]] = []
    pending_user_index: int | None = None
    for entry in history:
        role, text, notice = _normalize_history_entry(entry)
        if notice:
            items.append({"notice_text": notice})
            continue
        if role == "user":
            items.append({"user_text": text})
            pending_user_index = len(items) - 1
            continue
        if role == "assistant" and pending_user_index is not None:
            items[pending_user_index]["bot_text"] = text
            pending_user_index = None
            continue
        items.append({"notice_text": "此条记录为损坏条目。"})
    return items


def _normalize_history_entry(entry: Any) -> tuple[str, str, str]:
    if not isinstance(entry, Mapping):
        return "", "", "此条记录为损坏条目。"
    raw_role = entry.get("role")
    role = raw_role.strip().lower() if isinstance(raw_role, str) else ""
    if role == "system":
        return "", "", "此条记录为 system 条目。"
    if role == "tool":
        return "", "", "此条记录为 tool 条目。"
    if role not in {"user", "assistant"}:
        return "", "", "此条记录为损坏条目。"
    text, content_notice = _extract_text_content(entry.get("content"))
    if content_notice:
        return "", "", content_notice
    if not text.strip():
        return "", "", "此条记录为空条目。"
    return role, text, ""


def _extract_text_content(content: Any) -> tuple[str, str]:
    """Read AstrBot's string or ``list[ContentPart]`` history representation."""

    if isinstance(content, str):
        return content, ""
    if content is None:
        return "", ""
    if not isinstance(content, list):
        return "", "此条记录为损坏条目。"

    text_parts: list[str] = []
    saw_nontext_part = False
    for part in content:
        if not isinstance(part, Mapping):
            return "", "此条记录为损坏条目。"
        part_type = str(part.get("type") or "").strip().lower()
        part_text = part.get("text")
        if part_type == "text" and isinstance(part_text, str):
            text_parts.append(part_text)
            continue
        saw_nontext_part = True
    text = "".join(text_parts)
    if text.strip():
        return text, ""
    if saw_nontext_part:
        return "", "此条记录为非文本条目。"
    return "", ""


def _exclude_current_turn(
    items: list[dict[str, str]],
    *,
    current_input: str,
    current_request: str,
    current_output: str,
) -> None:
    """Remove the latest persisted copy of this event, if AstrBot already has it."""

    current_inputs = {
        value.strip()
        for value in (current_input, current_request)
        if isinstance(value, str) and value.strip()
    }
    if current_inputs:
        for index in range(len(items) - 1, -1, -1):
            if items[index].get("user_text", "").strip() in current_inputs:
                items.pop(index)
                return

    current = current_output.strip() if isinstance(current_output, str) else ""
    if not current:
        return
    for item in reversed(items):
        if item.get("bot_text", "").strip() == current:
            item.pop("bot_text", None)
            return


def _select_recent_turns(
    items: list[dict[str, str]], turns: int, user_only: bool
) -> list[dict[str, str]]:
    user_indices = [index for index, item in enumerate(items) if "user_text" in item]
    if user_indices:
        start = user_indices[max(len(user_indices) - turns, 0)]
        selected = copy.deepcopy(items[start:])
    else:
        selected = copy.deepcopy(items)
    if user_only:
        for item in selected:
            item.pop("bot_text", None)
    return selected


def _bound_items(
    items: list[dict[str, str]], max_chars: int
) -> tuple[list[dict[str, str]], bool]:
    bounded = copy.deepcopy(items)
    truncated = False
    while len(bounded) > 1 and len(_render_items(bounded)) > max_chars:
        bounded.pop(0)
        truncated = True
    if not bounded:
        return [], truncated
    for field in ("user_text", "bot_text", "notice_text"):
        if len(_render_items(bounded)) <= max_chars:
            break
        text = bounded[0].get(field)
        if not text:
            continue
        bounded[0][field] = _truncate_prefix_to_fit(
            bounded, field, text, max_chars
        )
        truncated = True
    return bounded, truncated


def _truncate_prefix_to_fit(
    items: list[dict[str, str]], field: str, text: str, max_chars: int
) -> str:
    """Drop the oldest prefix, retaining as much newest text as fits."""

    low, high = 0, len(text)
    while low < high:
        removed = (low + high) // 2
        items[0][field] = text[removed:]
        if len(_render_items(items)) <= max_chars:
            high = removed
        else:
            low = removed + 1
    items[0][field] = text[low:]
    return items[0][field]


def _render_items(items: list[dict[str, str]]) -> str:
    """Render neutral, line-oriented text with every body JSON-escaped."""

    lines: list[str] = []
    turn = 0
    for item in items:
        if "user_text" in item:
            turn += 1
            lines.append(
                "[guardrail-context/v1 "
                f"turn={turn} source=previous_message] "
                + _quote_text(item["user_text"])
            )
        if "bot_text" in item:
            lines.append(
                "[guardrail-context/v1 "
                f"turn={turn} source=previous_reply] "
                + _quote_text(item["bot_text"])
            )
        if "notice_text" in item:
            lines.append(
                "[guardrail-context/v1 source=notice] "
                + _quote_text(item["notice_text"])
            )
    return "\n".join(lines)


def _quote_text(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
