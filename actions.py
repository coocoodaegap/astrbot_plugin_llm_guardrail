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
    target = _action_target(action)
    return ActionPlan(
        rule_id=result.rule_id,
        rail=rail.rail,
        action=action,
        target=target,
        stop_rail=action in {"block_input", "block_output"},
        mutate_text=action in {"sanitize_input", "sanitize_output"},
        block=action in {"block_input", "block_output"},
    )


def _resolved_action(rail: NormalizedRail, result: RuleResult) -> str:
    if not result.matched:
        return "none"
    if result.action_on_hit != "default":
        return result.action_on_hit
    if rail.rail in {"input_rail", "request_rail"}:
        return str(rail.settings.get("default_action_on_hit", "block_input"))
    if rail.rail == "output_rail":
        return str(rail.settings.get("default_action_on_hit", "block_output"))
    return "observe"


def _action_target(action: str) -> str:
    if action in {"block_input", "sanitize_input"}:
        return "input"
    if action in {"block_output", "sanitize_output"}:
        return "output"
    return "none"
