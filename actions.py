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
class ActionPlan:
    rule_id: str
    rail: str
    action: str
    target: str
    stop_rail: bool
    mutate_text: bool
    block: bool


def resolve_action_plan(rail: NormalizedRail, result: RuleResult) -> ActionPlan:
    action = _resolved_action(rail, result)
    target = _action_target(rail.rail, action)
    return ActionPlan(
        rule_id=result.rule_id,
        rail=rail.rail,
        action=action,
        target=target,
        stop_rail=action == "block",
        mutate_text=action == "sanitize",
        block=action == "block",
    )


def _resolved_action(rail: NormalizedRail, result: RuleResult) -> str:
    if not result.matched:
        return "none"
    if result.action_on_hit != "default":
        return _normalize_action_alias(result.action_on_hit)
    if rail.rail in {"input_rail", "request_rail"}:
        return _normalize_action_alias(
            str(rail.settings.get("default_action_on_hit", "block"))
        )
    if rail.rail == "output_rail":
        return _normalize_action_alias(
            str(rail.settings.get("default_action_on_hit", "block"))
        )
    return "observe"


def _normalize_action_alias(action: str) -> str:
    if action in {"block_input", "sanitize_input"}:
        return action.removesuffix("_input")
    if action in {"block_output", "sanitize_output"}:
        return action.removesuffix("_output")
    return action


def _action_target(rail_name: str, action: str) -> str:
    if action not in {"block", "sanitize"}:
        return "none"
    if rail_name in {"input_rail", "request_rail"}:
        return "input"
    if rail_name == "output_rail":
        return "output"
    return "none"
