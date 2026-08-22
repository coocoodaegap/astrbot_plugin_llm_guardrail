"""Action planning for rule hits."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .config import NormalizedRail
    from .core import RuleResult
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedRail
    from core import RuleResult


@dataclass(frozen=True)
class HitActionPlan:
    rule_id: str
    rail: str
    action: str
    target: str
    stop_rail: bool
    mutate_text: bool
    block: bool


@dataclass(frozen=True)
class ErrorActionPlan:
    rule_id: str
    rail: str
    action: str
    target: str
    discard: bool
    record: bool
    block: bool


def resolve_hit_action_plan(rail: NormalizedRail, result: RuleResult) -> HitActionPlan:
    action = _resolved_hit_action(rail, result)
    target = _hit_action_target(rail.rail, action)
    return HitActionPlan(
        rule_id=result.rule_id,
        rail=rail.rail,
        action=action,
        target=target,
        stop_rail=action == "block",
        mutate_text=action == "sanitize",
        block=action == "block",
    )


def resolve_error_action_plan(rail: NormalizedRail, rule_id: str, action: str) -> ErrorActionPlan:
    resolved_action = _resolved_error_action(rail, action)
    target = _error_action_target(rail.rail, resolved_action)
    return ErrorActionPlan(
        rule_id=rule_id,
        rail=rail.rail,
        action=resolved_action,
        target=target,
        discard=resolved_action == "discard",
        record=resolved_action == "record",
        block=resolved_action == "block",
    )


def _resolved_hit_action(rail: NormalizedRail, result: RuleResult) -> str:
    if not result.matched:
        return "none"
    if result.action_on_hit != "default":
        action = result.action_on_hit
        if action != "retry_generation":
            return action
    return _default_hit_action(rail)


def _default_hit_action(rail: NormalizedRail) -> str:
    if rail.rail in {"input_rail", "request_rail"}:
        return str(rail.settings.get("default_action_on_hit", "block"))
    if rail.rail == "output_rail":
        return str(rail.settings.get("default_action_on_hit", "block"))
    return "observe"


def _resolved_error_action(rail: NormalizedRail, action: str) -> str:
    if action and action != "default":
        if action != "retry_generation":
            return action
    return str(rail.settings.get("default_action_on_error", "discard") or "discard")


def _hit_action_target(rail_name: str, action: str) -> str:
    if action not in {"block", "sanitize"}:
        return "none"
    if rail_name in {"input_rail", "request_rail"}:
        return "input"
    if rail_name == "output_rail":
        return "output"
    return "none"


def _error_action_target(rail_name: str, action: str) -> str:
    if action != "block":
        return "none"
    if rail_name in {"input_rail", "request_rail"}:
        return "input"
    if rail_name == "output_rail":
        return "output"
    return "none"
