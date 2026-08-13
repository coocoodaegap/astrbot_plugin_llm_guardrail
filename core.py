"""Runtime dataclasses and rule scheduling."""

from __future__ import annotations

import time
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

try:
    from .config import NormalizedRail, NormalizedRule
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedRail, NormalizedRule


@dataclass
class RuleSignal:
    value: Any
    truthy: bool
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleResult:
    rail: str
    template_key: str
    rule_id: str
    user_rule_id: str
    anonymous: bool
    enabled: bool
    executed: bool
    matched: bool
    signal: RuleSignal | None = None
    skipped_reason: str = ""
    action_on_hit: str = "default"
    hits: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0


@dataclass
class RouteDecision:
    provider_id: str
    source_rule_id: str
    applied: bool
    reason: str = ""


@dataclass
class RailContext:
    event: Any
    request: Any | None
    response: Any | None
    umo: str
    original_input: str
    current_input: str
    current_output: str
    results: dict[str, RuleResult] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    input_blocked: bool = False
    output_blocked: bool = False
    prompt_mutations: list[dict[str, Any]] = field(default_factory=list)
    route_decision: RouteDecision | None = None


RuleExecutor = Callable[[NormalizedRule, RailContext], RuleResult]
AsyncRuleExecutor = Callable[[NormalizedRule, RailContext], Any]
StopPredicate = Callable[[RailContext], bool]


class RuleScheduler:
    """Serial dependency-aware scheduler for one rail."""

    def run(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: RuleExecutor,
        should_stop: StopPredicate | None = None,
    ) -> None:
        pending: dict[str, NormalizedRule] = {}
        for rule in sorted(rail.rules, key=lambda item: (item.priority, item.index)):
            if not rule.enabled or not rule.valid:
                result = skipped_result(
                    rule,
                    "disabled" if not rule.enabled else "invalid",
                    warnings=rule.warnings,
                )
                context.results[rule.rule_id] = result
                context.warnings.extend(rule.warnings)
                continue
            pending[rule.rule_id] = rule

        while pending:
            ready: list[NormalizedRule] = []
            skipped_now: list[tuple[str, NormalizedRule]] = []

            for rule in sorted(pending.values(), key=lambda item: (item.priority, item.index)):
                state, reason = self._dependency_state(rule, context, pending)
                if state == "ready":
                    ready.append(rule)
                elif state == "impossible":
                    skipped_now.append((reason, rule))

            for reason, rule in skipped_now:
                context.results[rule.rule_id] = skipped_result(rule, reason)
                if _skip_reason_is_warning(reason):
                    context.warnings.append(f"{rule.rule_id} skipped: {reason}")
                pending.pop(rule.rule_id, None)

            if not ready:
                for rule in sorted(pending.values(), key=lambda item: (item.priority, item.index)):
                    reason = self._blocked_reason(rule, pending)
                    context.results[rule.rule_id] = skipped_result(rule, reason)
                    if _skip_reason_is_warning(reason):
                        context.warnings.append(f"{rule.rule_id} skipped: {reason}")
                pending.clear()
                return

            for rule in ready:
                if rule.rule_id not in pending:
                    continue
                started = time.perf_counter()
                try:
                    result = executor(rule, context)
                except Exception as exc:  # Defensive boundary for user rules/config.
                    result = make_result(
                        rule,
                        matched=False,
                        executed=True,
                        skipped_reason="",
                        metadata={"error": f"{type(exc).__name__}: {exc}"},
                    )
                    context.warnings.append(
                        f"{rule.rule_id} failed: {type(exc).__name__}: {exc}"
                    )
                result.latency_ms = int((time.perf_counter() - started) * 1000)
                context.results[rule.rule_id] = result
                pending.pop(rule.rule_id, None)
                if should_stop is not None and should_stop(context):
                    for remaining in sorted(
                        pending.values(), key=lambda item: (item.priority, item.index)
                    ):
                        context.results[remaining.rule_id] = skipped_result(
                            remaining, "rail_stopped"
                        )
                    pending.clear()
                    return

    async def run_async(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: AsyncRuleExecutor,
        should_stop: StopPredicate | None = None,
    ) -> None:
        pending: dict[str, NormalizedRule] = {}
        for rule in sorted(rail.rules, key=lambda item: (item.priority, item.index)):
            if not rule.enabled or not rule.valid:
                result = skipped_result(
                    rule,
                    "disabled" if not rule.enabled else "invalid",
                    warnings=rule.warnings,
                )
                context.results[rule.rule_id] = result
                context.warnings.extend(rule.warnings)
                continue
            pending[rule.rule_id] = rule

        while pending:
            ready: list[NormalizedRule] = []
            skipped_now: list[tuple[str, NormalizedRule]] = []

            for rule in sorted(pending.values(), key=lambda item: (item.priority, item.index)):
                state, reason = self._dependency_state(rule, context, pending)
                if state == "ready":
                    ready.append(rule)
                elif state == "impossible":
                    skipped_now.append((reason, rule))

            for reason, rule in skipped_now:
                context.results[rule.rule_id] = skipped_result(rule, reason)
                if _skip_reason_is_warning(reason):
                    context.warnings.append(f"{rule.rule_id} skipped: {reason}")
                pending.pop(rule.rule_id, None)

            if not ready:
                for rule in sorted(pending.values(), key=lambda item: (item.priority, item.index)):
                    reason = self._blocked_reason(rule, pending)
                    context.results[rule.rule_id] = skipped_result(rule, reason)
                    if _skip_reason_is_warning(reason):
                        context.warnings.append(f"{rule.rule_id} skipped: {reason}")
                pending.clear()
                return

            for rule in ready:
                if rule.rule_id not in pending:
                    continue
                started = time.perf_counter()
                try:
                    maybe_result = executor(rule, context)
                    result = (
                        await maybe_result
                        if inspect.isawaitable(maybe_result)
                        else maybe_result
                    )
                except Exception as exc:  # Defensive boundary for user rules/config.
                    result = make_result(
                        rule,
                        matched=False,
                        executed=True,
                        skipped_reason="",
                        metadata={"error": f"{type(exc).__name__}: {exc}"},
                    )
                    context.warnings.append(
                        f"{rule.rule_id} failed: {type(exc).__name__}: {exc}"
                    )
                result.latency_ms = int((time.perf_counter() - started) * 1000)
                context.results[rule.rule_id] = result
                pending.pop(rule.rule_id, None)
                if should_stop is not None and should_stop(context):
                    for remaining in sorted(
                        pending.values(), key=lambda item: (item.priority, item.index)
                    ):
                        context.results[remaining.rule_id] = skipped_result(
                            remaining, "rail_stopped"
                        )
                    pending.clear()
                    return

    def _dependency_state(
        self,
        rule: NormalizedRule,
        context: RailContext,
        pending: dict[str, NormalizedRule],
    ) -> tuple[str, str]:
        dep = parse_depend_on(rule.depend_on)
        if dep.target:
            result = context.results.get(dep.target)
            if result is None:
                if dep.target in pending:
                    return "waiting", ""
                return "impossible", "dependency_missing"
            if not result.executed:
                return "impossible", "dependency_not_executed"
            if not dep.matches(result):
                return "impossible", "dependency_not_satisfied"

        for input_id in logic_gate_inputs(rule):
            result = context.results.get(input_id)
            if result is None:
                if input_id in pending:
                    return "waiting", ""
                return "impossible", "logic_input_missing"
            if not result.executed:
                return "impossible", "logic_input_not_executed"

        return "ready", ""

    @staticmethod
    def _blocked_reason(
        rule: NormalizedRule, pending: dict[str, NormalizedRule]
    ) -> str:
        dependencies = []
        dep = parse_depend_on(rule.depend_on)
        if dep.target:
            dependencies.append(dep.target)
        dependencies.extend(logic_gate_inputs(rule))
        if any(item in pending for item in dependencies):
            return "cyclic_dependency"
        return "dependency_unresolved"


@dataclass
class DependSpec:
    target: str
    mode: str

    def matches(self, result: RuleResult) -> bool:
        if self.mode == "matched":
            return result.matched
        if self.mode == "not_matched":
            return not result.matched
        return True


def parse_depend_on(value: str) -> DependSpec:
    stripped = (value or "").strip()
    if not stripped:
        return DependSpec(target="", mode="none")
    if stripped.startswith("!"):
        return DependSpec(target=stripped[1:].strip(), mode="not_matched")
    if stripped.startswith("?"):
        return DependSpec(target=stripped[1:].strip(), mode="executed")
    return DependSpec(target=stripped, mode="matched")


def logic_gate_inputs(rule: NormalizedRule) -> list[str]:
    if rule.template_key != "logic_gate":
        return []
    inputs = rule.config.get("inputs", [])
    if not isinstance(inputs, list):
        return []
    return [str(item).strip() for item in inputs if str(item).strip()]


def _skip_reason_is_warning(reason: str) -> bool:
    return reason in {
        "dependency_missing",
        "dependency_not_executed",
        "logic_input_missing",
        "logic_input_not_executed",
        "cyclic_dependency",
        "dependency_unresolved",
    }


def make_result(
    rule: NormalizedRule,
    matched: bool,
    executed: bool = True,
    skipped_reason: str = "",
    action_on_hit: str | None = None,
    hits: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    signal: RuleSignal | None = None,
) -> RuleResult:
    if signal is None:
        signal = RuleSignal(value=matched, truthy=matched, payload={})
    return RuleResult(
        rail=rule.rail,
        template_key=rule.template_key,
        rule_id=rule.rule_id,
        user_rule_id=rule.user_rule_id,
        anonymous=rule.anonymous,
        enabled=rule.enabled,
        executed=executed,
        matched=matched,
        signal=signal,
        skipped_reason=skipped_reason,
        action_on_hit=action_on_hit
        if action_on_hit is not None
        else str(rule.config.get("action_on_hit", "default")),
        hits=hits or [],
        metadata=metadata or {},
    )


def skipped_result(
    rule: NormalizedRule, reason: str, warnings: list[str] | None = None
) -> RuleResult:
    metadata = {"warnings": list(warnings or [])} if warnings else {}
    return make_result(
        rule,
        matched=False,
        executed=False,
        skipped_reason=reason,
        metadata=metadata,
    )
