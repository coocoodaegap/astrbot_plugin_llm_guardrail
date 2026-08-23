"""Evaluators for policy-local electronic components."""

from __future__ import annotations

try:
    from .config import NormalizedNode
    from .core import (
        NodeSignal,
        RailContext,
        logic_gate_input_specs,
        logic_input_value,
        make_node_result,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedNode
    from core import (
        NodeSignal,
        RailContext,
        logic_gate_input_specs,
        logic_input_value,
        make_node_result,
    )


def evaluate_logic_gate(node: NormalizedNode, context: RailContext):
    """Evaluate the P1 boolean logic-gate component."""

    specs = logic_gate_input_specs(node)
    values = [
        logic_input_value(spec, context.results[spec.target])
        for spec in specs
    ]
    gate = str(node.config.get("gate", "all"))
    matched = all(values) if gate == "all" else any(values)
    if bool(node.config.get("invert", False)):
        matched = not matched
    payload = {
        "inputs": {
            spec.raw or spec.target: value
            for spec, value in zip(specs, values, strict=False)
        }
    }
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "default")),
        metadata=payload,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )
