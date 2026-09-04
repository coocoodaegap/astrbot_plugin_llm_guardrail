"""Action planning for runtime node hits."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .config import NormalizedRail
    from .core import NodeResult
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedRail
    from core import NodeResult


@dataclass(frozen=True)
class HitActionPlan:
    node_id: str
    rail: str
    action: str
    target: str
    stop_rail: bool
    block: bool

    @property
    def rule_id(self) -> str:
        return self.node_id

@dataclass(frozen=True)
class ErrorActionPlan:
    node_id: str
    rail: str
    action: str
    target: str
    discard: bool
    record: bool
    block: bool

    @property
    def rule_id(self) -> str:
        return self.node_id


def resolve_hit_action_plan(rail: NormalizedRail, result: NodeResult) -> HitActionPlan:
    action = _resolved_hit_action(rail, result)
    target = _hit_action_target(rail.rail, action)
    return HitActionPlan(
        node_id=result.node_id,
        rail=rail.rail,
        action=action,
        target=target,
        stop_rail=action in {"block", "retry_generation"},
        block=action == "block",
    )


def resolve_error_action_plan(rail: NormalizedRail, node_id: str, action: str) -> ErrorActionPlan:
    resolved_action = _resolved_error_action(rail, action)
    target = _error_action_target(rail.rail, resolved_action)
    return ErrorActionPlan(
        node_id=node_id,
        rail=rail.rail,
        action=resolved_action,
        target=target,
        discard=resolved_action == "discard",
        record=resolved_action == "record",
        block=resolved_action == "block",
    )


def _resolved_hit_action(rail: NormalizedRail, result: NodeResult) -> str:
    if not result.matched:
        return "none"
    if result.action_on_hit != "default":
        action = result.action_on_hit
        if action in {"observe", "block"}:
            return action
        if action == "retry_generation" and rail.rail == "output_rail":
            return action
        if action != "retry_generation":
            return "observe"
    return _default_hit_action(rail)


def _default_hit_action(rail: NormalizedRail) -> str:
    if rail.rail in {"input_rail", "routing_rail", "request_rail", "prompt_rail"}:
        action = str(rail.settings.get("default_action_on_hit", "observe"))
        return action if action in {"observe", "block"} else "observe"
    if rail.rail == "output_rail":
        action = str(rail.settings.get("default_action_on_hit", "observe"))
        return action if action in {"observe", "block", "retry_generation"} else "observe"
    return "observe"


def _resolved_error_action(rail: NormalizedRail, action: str) -> str:
    if action and action != "default":
        return action if action in {"discard", "record", "block"} else "discard"
    default_action = str(rail.settings.get("default_action_on_error", "discard") or "discard")
    return default_action if default_action in {"discard", "record", "block"} else "discard"


def _hit_action_target(rail_name: str, action: str) -> str:
    if action not in {"block", "retry_generation"}:
        return "none"
    if rail_name in {"input_rail", "routing_rail", "request_rail", "prompt_rail"}:
        return "input"
    if rail_name == "output_rail":
        return "output"
    return "none"


def _error_action_target(rail_name: str, action: str) -> str:
    if action != "block":
        return "none"
    if rail_name in {"input_rail", "routing_rail", "request_rail", "prompt_rail"}:
        return "input"
    if rail_name == "output_rail":
        return "output"
    return "none"
