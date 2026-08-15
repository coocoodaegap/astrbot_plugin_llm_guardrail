"""Runtime dataclasses and rule scheduling."""

from __future__ import annotations

import time
import inspect
import heapq
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

try:
    from .config import (
        NormalizedConfig,
        NormalizedRail,
        NormalizedRule,
        SessionScopeDecision,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import (
        NormalizedConfig,
        NormalizedRail,
        NormalizedRule,
        SessionScopeDecision,
    )


RAIL_STEPS = {
    "input_rail": 1,
    "routing_rail": 2,
    "request_rail": 3,
    "prompt_rail": 4,
    "output_rail": 5,
}


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
    session_scope_decision: SessionScopeDecision | None = None


@dataclass(frozen=True)
class RuleNode:
    rule_id: str
    user_rule_id: str
    anonymous: bool
    step: int
    rail: str
    template_key: str
    priority: int
    index: int


@dataclass(frozen=True)
class RuleEdge:
    source: str
    target: str
    kind: str
    mode: str


@dataclass(frozen=True)
class GraphMetrics:
    node_count: int
    edge_count: int
    max_depth: int
    has_cross_step_edges: bool
    has_cycle_suspect: bool


@dataclass(frozen=True)
class GraphIndex:
    nodes: Mapping[str, RuleNode]
    by_rail: Mapping[str, tuple[str, ...]]
    by_step: Mapping[int, tuple[str, ...]]
    incoming: Mapping[str, Mapping[str, tuple[RuleEdge, ...]]]
    outgoing: Mapping[str, Mapping[str, tuple[RuleEdge, ...]]]
    metrics: GraphMetrics


RuleExecutor = Callable[[NormalizedRule, RailContext], RuleResult]
AsyncRuleExecutor = Callable[[NormalizedRule, RailContext], Any]
RuleErrorHandler = Callable[[NormalizedRule, RailContext, Exception], RuleResult | None]
StopPredicate = Callable[[RailContext], bool]


class RuleScheduler:
    """Dependency-aware scheduler for one rail."""

    def __init__(
        self,
        graph: GraphIndex | None = None,
        strategy: str = "graph",
    ) -> None:
        self.graph = graph
        self.strategy = strategy if strategy in {"auto", "bruteforce", "graph"} else "graph"

    def run(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: RuleExecutor,
        should_stop: StopPredicate | None = None,
        error_handler: RuleErrorHandler | None = None,
    ) -> None:
        if self.strategy == "bruteforce":
            self._run_bruteforce(rail, context, executor, should_stop, error_handler)
            return
        self._run_graph(rail, context, executor, should_stop, error_handler)

    async def run_async(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: AsyncRuleExecutor,
        should_stop: StopPredicate | None = None,
        error_handler: RuleErrorHandler | None = None,
    ) -> None:
        if self.strategy == "bruteforce":
            await self._run_bruteforce_async(
                rail, context, executor, should_stop, error_handler
            )
            return
        await self._run_graph_async(rail, context, executor, should_stop, error_handler)

    def _run_graph(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: RuleExecutor,
        should_stop: StopPredicate | None,
        error_handler: RuleErrorHandler | None,
    ) -> None:
        graph = self.graph or build_graph_index(rail)
        active_rules = self._collect_active_rules(rail, context)
        pending = set(active_rules)
        queued: set[str] = set()
        ready_heap: list[tuple[int, int, str]] = []

        self._refresh_ready(graph, active_rules, pending, queued, ready_heap, context)

        while ready_heap:
            _, _, rule_id = heapq.heappop(ready_heap)
            queued.discard(rule_id)
            if rule_id not in pending:
                continue
            rule = active_rules[rule_id]
            result = self._execute_rule(rule, context, executor, error_handler)
            if result is not None:
                context.results[rule_id] = result
            pending.remove(rule_id)

            if should_stop is not None and should_stop(context):
                self._stop_pending(active_rules, pending, context)
                return

            self._refresh_ready(
                graph,
                active_rules,
                pending,
                queued,
                ready_heap,
                context,
                changed_sources=[rule_id] if result is not None else [],
            )

        self._expire_pending(graph, active_rules, pending, context)

    async def _run_graph_async(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: AsyncRuleExecutor,
        should_stop: StopPredicate | None,
        error_handler: RuleErrorHandler | None,
    ) -> None:
        graph = self.graph or build_graph_index(rail)
        active_rules = self._collect_active_rules(rail, context)
        pending = set(active_rules)
        queued: set[str] = set()
        ready_heap: list[tuple[int, int, str]] = []

        self._refresh_ready(graph, active_rules, pending, queued, ready_heap, context)

        while ready_heap:
            _, _, rule_id = heapq.heappop(ready_heap)
            queued.discard(rule_id)
            if rule_id not in pending:
                continue
            rule = active_rules[rule_id]
            result = await self._execute_rule_async(rule, context, executor, error_handler)
            if result is not None:
                context.results[rule_id] = result
            pending.remove(rule_id)

            if should_stop is not None and should_stop(context):
                self._stop_pending(active_rules, pending, context)
                return

            self._refresh_ready(
                graph,
                active_rules,
                pending,
                queued,
                ready_heap,
                context,
                changed_sources=[rule_id] if result is not None else [],
            )

        self._expire_pending(graph, active_rules, pending, context)

    def _run_bruteforce(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: RuleExecutor,
        should_stop: StopPredicate | None,
        error_handler: RuleErrorHandler | None,
    ) -> None:
        pending: dict[str, NormalizedRule] = {}
        expired_sources: set[str] = set()
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
                state, reason = self._dependency_state(
                    rule, context, pending, expired_sources
                )
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
                    reason = self._blocked_reason(rule, pending, expired_sources)
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
                    result = self._handle_rule_error(rule, context, exc, error_handler)
                if result is not None:
                    result.latency_ms = int((time.perf_counter() - started) * 1000)
                    context.results[rule.rule_id] = result
                else:
                    expired_sources.add(rule.rule_id)
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

    async def _run_bruteforce_async(
        self,
        rail: NormalizedRail,
        context: RailContext,
        executor: AsyncRuleExecutor,
        should_stop: StopPredicate | None,
        error_handler: RuleErrorHandler | None,
    ) -> None:
        pending: dict[str, NormalizedRule] = {}
        expired_sources: set[str] = set()
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
                state, reason = self._dependency_state(
                    rule, context, pending, expired_sources
                )
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
                    reason = self._blocked_reason(rule, pending, expired_sources)
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
                    result = self._handle_rule_error(rule, context, exc, error_handler)
                if result is not None:
                    result.latency_ms = int((time.perf_counter() - started) * 1000)
                    context.results[rule.rule_id] = result
                else:
                    expired_sources.add(rule.rule_id)
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

    def _collect_active_rules(
        self, rail: NormalizedRail, context: RailContext
    ) -> dict[str, NormalizedRule]:
        active: dict[str, NormalizedRule] = {}
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
            active[rule.rule_id] = rule
        return active

    def _execute_rule(
        self,
        rule: NormalizedRule,
        context: RailContext,
        executor: RuleExecutor,
        error_handler: RuleErrorHandler | None,
    ) -> RuleResult | None:
        started = time.perf_counter()
        try:
            result = executor(rule, context)
        except Exception as exc:  # Defensive boundary for user rules/config.
            result = self._handle_rule_error(rule, context, exc, error_handler)
        if result is not None:
            result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    async def _execute_rule_async(
        self,
        rule: NormalizedRule,
        context: RailContext,
        executor: AsyncRuleExecutor,
        error_handler: RuleErrorHandler | None,
    ) -> RuleResult | None:
        started = time.perf_counter()
        try:
            maybe_result = executor(rule, context)
            result = await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
        except Exception as exc:  # Defensive boundary for user rules/config.
            result = self._handle_rule_error(rule, context, exc, error_handler)
        if result is not None:
            result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    @staticmethod
    def _handle_rule_error(
        rule: NormalizedRule,
        context: RailContext,
        exc: Exception,
        error_handler: RuleErrorHandler | None,
    ) -> RuleResult | None:
        if error_handler is not None:
            return error_handler(rule, context, exc)
        error_text = f"{type(exc).__name__}: {exc}"
        context.warnings.append(f"{rule.rule_id} failed: {error_text}")
        return make_result(
            rule,
            matched=False,
            executed=True,
            skipped_reason="",
            metadata={"error": error_text},
        )

    def _refresh_ready(
        self,
        graph: GraphIndex,
        active_rules: dict[str, NormalizedRule],
        pending: set[str],
        queued: set[str],
        ready_heap: list[tuple[int, int, str]],
        context: RailContext,
        changed_sources: list[str] | None = None,
    ) -> None:
        if changed_sources is None:
            candidates = set(pending)
        else:
            candidates = self._active_targets(graph, active_rules, pending, changed_sources)

        while candidates:
            next_changed: list[str] = []
            for rule_id in sorted(
                candidates,
                key=lambda item: (
                    active_rules[item].priority,
                    active_rules[item].index,
                    item,
                ),
            ):
                if rule_id not in pending or rule_id in queued:
                    continue
                state, reason = self._node_state(graph, rule_id, pending, context)
                if state == "ready":
                    rule = active_rules[rule_id]
                    heapq.heappush(ready_heap, (rule.priority, rule.index, rule_id))
                    queued.add(rule_id)
                elif state == "impossible":
                    self._skip_rule(active_rules[rule_id], reason, context)
                    pending.remove(rule_id)
                    next_changed.append(rule_id)
            candidates = self._active_targets(
                graph, active_rules, pending, next_changed
            )

    @staticmethod
    def _active_targets(
        graph: GraphIndex,
        active_rules: dict[str, NormalizedRule],
        pending: set[str],
        changed_sources: list[str],
    ) -> set[str]:
        candidates: set[str] = set()
        for source in changed_sources:
            for target in graph.outgoing.get(source, {}):
                if target in pending and target in active_rules:
                    candidates.add(target)
        return candidates

    def _node_state(
        self,
        graph: GraphIndex,
        rule_id: str,
        pending: set[str],
        context: RailContext,
    ) -> tuple[str, str]:
        waiting = False
        for edges_by_source in graph.incoming.get(rule_id, {}).values():
            for edge in edges_by_source:
                state, reason = self._edge_state(graph, edge, pending, context)
                if state == "impossible":
                    return "impossible", reason
                if state == "waiting":
                    waiting = True
        if waiting:
            return "waiting", ""
        return "ready", ""

    def _edge_state(
        self,
        graph: GraphIndex,
        edge: RuleEdge,
        pending: set[str],
        context: RailContext,
    ) -> tuple[str, str]:
        result = context.results.get(edge.source)
        if result is None:
            if edge.source in pending or edge.source in graph.nodes:
                return "waiting", ""
            return "impossible", self._missing_reason(edge)
        if not result.executed:
            return "impossible", self._not_executed_reason(edge)
        if edge.kind == "logic_input":
            return "satisfied", ""
        if _depend_result_matches(edge.mode, result):
            return "satisfied", ""
        return "impossible", "dependency_not_satisfied"

    @staticmethod
    def _missing_reason(edge: RuleEdge) -> str:
        return "logic_input_missing" if edge.kind == "logic_input" else "dependency_missing"

    @staticmethod
    def _not_executed_reason(edge: RuleEdge) -> str:
        if edge.kind == "logic_input":
            return "logic_input_not_executed"
        return "dependency_not_executed"

    def _skip_rule(
        self, rule: NormalizedRule, reason: str, context: RailContext
    ) -> None:
        context.results[rule.rule_id] = skipped_result(rule, reason)
        if _skip_reason_is_warning(reason):
            context.warnings.append(f"{rule.rule_id} skipped: {reason}")

    def _stop_pending(
        self,
        active_rules: dict[str, NormalizedRule],
        pending: set[str],
        context: RailContext,
    ) -> None:
        for rule_id in sorted(
            pending,
            key=lambda item: (active_rules[item].priority, active_rules[item].index),
        ):
            context.results[rule_id] = skipped_result(active_rules[rule_id], "rail_stopped")
        pending.clear()

    def _expire_pending(
        self,
        graph: GraphIndex,
        active_rules: dict[str, NormalizedRule],
        pending: set[str],
        context: RailContext,
    ) -> None:
        for rule_id in sorted(
            pending,
            key=lambda item: (active_rules[item].priority, active_rules[item].index),
        ):
            reason = self._blocked_reason_graph(graph, rule_id, pending)
            self._skip_rule(active_rules[rule_id], reason, context)
        pending.clear()

    @staticmethod
    def _blocked_reason_graph(
        graph: GraphIndex, rule_id: str, pending: set[str]
    ) -> str:
        dependencies = [
            edge.source
            for edges_by_source in graph.incoming.get(rule_id, {}).values()
            for edge in edges_by_source
        ]
        if any(item in pending for item in dependencies):
            return "cyclic_dependency"
        if any(item not in graph.nodes for item in dependencies):
            return "dependency_unresolved"
        return "expired"

    def _dependency_state(
        self,
        rule: NormalizedRule,
        context: RailContext,
        pending: dict[str, NormalizedRule],
        expired_sources: set[str] | None = None,
    ) -> tuple[str, str]:
        expired_sources = expired_sources or set()
        dep = parse_depend_on(rule.depend_on)
        if dep.target:
            result = context.results.get(dep.target)
            if result is None:
                if dep.target in pending:
                    return "waiting", ""
                if dep.target in expired_sources:
                    return "impossible", "expired"
                return "impossible", "dependency_missing"
            if not result.executed:
                return "impossible", "dependency_not_executed"
            if not dep.matches(result):
                return "impossible", "dependency_not_satisfied"

        for input_spec in logic_gate_input_specs(rule):
            result = context.results.get(input_spec.target)
            if result is None:
                if input_spec.target in pending:
                    return "waiting", ""
                if input_spec.target in expired_sources:
                    return "impossible", "expired"
                return "impossible", "logic_input_missing"
            if not result.executed:
                return "impossible", "logic_input_not_executed"

        return "ready", ""

    @staticmethod
    def _blocked_reason(
        rule: NormalizedRule,
        pending: dict[str, NormalizedRule],
        expired_sources: set[str] | None = None,
    ) -> str:
        expired_sources = expired_sources or set()
        dependencies = []
        dep = parse_depend_on(rule.depend_on)
        if dep.target:
            dependencies.append(dep.target)
        dependencies.extend(input_spec.target for input_spec in logic_gate_input_specs(rule))
        if any(item in pending for item in dependencies):
            return "cyclic_dependency"
        if any(item in expired_sources for item in dependencies):
            return "expired"
        return "dependency_unresolved"


@dataclass
class DependSpec:
    target: str
    mode: str
    raw: str = ""

    def matches(self, result: RuleResult) -> bool:
        return _depend_result_matches(self.mode, result)


def parse_depend_on(value: str) -> DependSpec:
    return parse_rule_ref(value)


def parse_rule_ref(value: str) -> DependSpec:
    stripped = (value or "").strip()
    if not stripped:
        return DependSpec(target="", mode="none", raw="")
    if stripped.startswith("!"):
        return DependSpec(
            target=stripped[1:].strip(), mode="not_matched", raw=stripped
        )
    if stripped.startswith("?"):
        return DependSpec(target=stripped[1:].strip(), mode="executed", raw=stripped)
    return DependSpec(target=stripped, mode="matched", raw=stripped)


def logic_gate_inputs(rule: NormalizedRule) -> list[str]:
    return [item.target for item in logic_gate_input_specs(rule)]


def logic_gate_input_specs(rule: NormalizedRule) -> list[DependSpec]:
    if rule.template_key != "logic_gate":
        return []
    inputs = rule.config.get("inputs", [])
    if not isinstance(inputs, list):
        return []
    result: list[DependSpec] = []
    for item in inputs:
        spec = parse_rule_ref(str(item).strip())
        if spec.target:
            result.append(spec)
    return result


def logic_input_value(spec: DependSpec, result: RuleResult) -> bool:
    if spec.mode == "not_matched":
        return not result.matched
    if spec.mode == "executed":
        return result.executed
    return result.matched


def _depend_result_matches(mode: str, result: RuleResult) -> bool:
    if mode == "matched":
        return result.matched
    if mode == "not_matched":
        return not result.matched
    return True


def build_graph_index(source: NormalizedConfig | NormalizedRail) -> GraphIndex:
    rails = _iter_graph_rails(source)
    nodes: dict[str, RuleNode] = {}
    by_rail: dict[str, list[str]] = {}
    by_step: dict[int, list[str]] = {}
    incoming: dict[str, dict[str, list[RuleEdge]]] = {}
    outgoing: dict[str, dict[str, list[RuleEdge]]] = {}

    for rail in rails:
        step = RAIL_STEPS.get(rail.rail, 0)
        by_rail.setdefault(rail.rail, [])
        by_step.setdefault(step, [])
        for rule in rail.rules:
            if rule.rule_id not in nodes:
                nodes[rule.rule_id] = RuleNode(
                    rule_id=rule.rule_id,
                    user_rule_id=rule.user_rule_id,
                    anonymous=rule.anonymous,
                    step=step,
                    rail=rule.rail,
                    template_key=rule.template_key,
                    priority=rule.priority,
                    index=rule.index,
                )
            by_rail[rail.rail].append(rule.rule_id)
            by_step[step].append(rule.rule_id)

            dep = parse_depend_on(rule.depend_on)
            if dep.target:
                _add_edge(
                    incoming,
                    outgoing,
                    RuleEdge(
                        source=dep.target,
                        target=rule.rule_id,
                        kind="depend_on",
                        mode=dep.mode,
                    ),
                )
            for spec in logic_gate_input_specs(rule):
                _add_edge(
                    incoming,
                    outgoing,
                    RuleEdge(
                        source=spec.target,
                        target=rule.rule_id,
                        kind="logic_input",
                        mode=spec.mode,
                    ),
                )

    frozen_incoming = _freeze_edge_map(incoming)
    frozen_outgoing = _freeze_edge_map(outgoing)
    frozen_by_rail = {
        key: tuple(value)
        for key, value in by_rail.items()
    }
    frozen_by_step = {
        key: tuple(value)
        for key, value in by_step.items()
    }
    metrics = _build_graph_metrics(nodes, frozen_outgoing)
    return GraphIndex(
        nodes=dict(nodes),
        by_rail=frozen_by_rail,
        by_step=frozen_by_step,
        incoming=frozen_incoming,
        outgoing=frozen_outgoing,
        metrics=metrics,
    )


def _iter_graph_rails(source: NormalizedConfig | NormalizedRail) -> list[NormalizedRail]:
    if isinstance(source, NormalizedRail):
        return [source]
    rails = getattr(source, "rails", {})
    return [
        rails[name]
        for name in sorted(rails, key=lambda item: RAIL_STEPS.get(item, 999))
        if name in rails
    ]


def _add_edge(
    incoming: dict[str, dict[str, list[RuleEdge]]],
    outgoing: dict[str, dict[str, list[RuleEdge]]],
    edge: RuleEdge,
) -> None:
    incoming.setdefault(edge.target, {}).setdefault(edge.source, []).append(edge)
    outgoing.setdefault(edge.source, {}).setdefault(edge.target, []).append(edge)


def _freeze_edge_map(
    value: dict[str, dict[str, list[RuleEdge]]]
) -> dict[str, dict[str, tuple[RuleEdge, ...]]]:
    return {
        outer_key: {
            inner_key: tuple(edges)
            for inner_key, edges in inner_value.items()
        }
        for outer_key, inner_value in value.items()
    }


def _build_graph_metrics(
    nodes: dict[str, RuleNode],
    outgoing: Mapping[str, Mapping[str, tuple[RuleEdge, ...]]],
) -> GraphMetrics:
    state: dict[str, str] = {}
    depth_cache: dict[str, int] = {}
    has_cycle = False

    def depth(rule_id: str) -> int:
        nonlocal has_cycle
        mark = state.get(rule_id)
        if mark == "visiting":
            has_cycle = True
            return 0
        if mark == "visited":
            return depth_cache[rule_id]
        state[rule_id] = "visiting"
        max_child_depth = 0
        for target in outgoing.get(rule_id, {}):
            if target in nodes:
                max_child_depth = max(max_child_depth, depth(target))
        state[rule_id] = "visited"
        depth_cache[rule_id] = max_child_depth + 1
        return depth_cache[rule_id]

    max_depth = 0
    for rule_id in nodes:
        max_depth = max(max_depth, depth(rule_id))

    edge_count = sum(
        len(edges)
        for targets in outgoing.values()
        for edges in targets.values()
    )
    has_cross_step_edges = any(
        source in nodes
        and target in nodes
        and nodes[source].step != nodes[target].step
        for source, targets in outgoing.items()
        for target in targets
    )
    return GraphMetrics(
        node_count=len(nodes),
        edge_count=edge_count,
        max_depth=max_depth,
        has_cross_step_edges=has_cross_step_edges,
        has_cycle_suspect=has_cycle,
    )


def _skip_reason_is_warning(reason: str) -> bool:
    return reason in {
        "dependency_missing",
        "dependency_not_executed",
        "logic_input_missing",
        "logic_input_not_executed",
        "cyclic_dependency",
        "dependency_unresolved",
        "expired",
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
