"""Build the non-persistent system fallback runtime graph.

The fallback graph is deliberately not a :class:`PolicyDefinition`: it must
remain available when the policy library cannot supply a usable graph.  Its
topology is code-owned while ``fallback_policy_settings`` supplies its runtime
parameters and feature switches.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

try:
    from .config import NormalizedConfig, normalize_config
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedConfig, normalize_config


FALLBACK_INPUT_OR_ID = "__fallback_input_or"
FALLBACK_LLM_REVIEW_ID = "__fallback_llm_review"
FALLBACK_LLM_REVIEW_PROMPT = (
    "Review the supplied text for safety risks indicated by the preceding "
    "detectors. Return whether the text should be treated as unsafe."
)


@dataclass(frozen=True)
class FallbackDetectorSpec:
    """A future built-in detector's placement and controlling system switch.

    No detector template is registered in P1 yet.  The catalogue records the
    stable system-setting contract now; a detector joins the runtime graph only
    after its template/evaluator is implemented and registered here.
    """

    setting_key: str
    node_id: str
    rail: str
    template_key: str
    config: Mapping[str, Any] = field(default_factory=dict)


# P2 implementations will replace the placeholder template keys with actual
# supported component templates.  Keeping them out of ``implemented`` avoids
# emitting invalid nodes while still making the intended fallback composition
# explicit and testable.
FALLBACK_DETECTOR_CATALOGUE: tuple[FallbackDetectorSpec, ...] = (
    FallbackDetectorSpec("enable_encoded_payload_detector", "__fallback_encoded_payload", "input_rail", "encoded_payload_detector"),
    FallbackDetectorSpec("enable_length_anomaly_detector", "__fallback_length_anomaly", "input_rail", "length_anomaly_detector"),
    FallbackDetectorSpec("enable_role_marker_spoofing_detector", "__fallback_role_marker_spoofing", "input_rail", "role_marker_spoofing_detector"),
    FallbackDetectorSpec("enable_external_fetch_detector", "__fallback_external_fetch", "input_rail", "external_fetch_detector"),
    FallbackDetectorSpec("enable_instruction_override_detector", "__fallback_instruction_override", "input_rail", "instruction_override_detector"),
    FallbackDetectorSpec("enable_multi_turn_escalation_detector", "__fallback_multi_turn_escalation", "input_rail", "multi_turn_escalation_detector"),
    FallbackDetectorSpec("enable_prompt_injection_combo_detector", "__fallback_prompt_injection_combo", "input_rail", "prompt_injection_combo_detector"),
    FallbackDetectorSpec("enable_format_violation_detector", "__fallback_format_violation", "output_rail", "format_violation_detector"),
    FallbackDetectorSpec("enable_poor_quality_detector", "__fallback_poor_quality", "output_rail", "poor_quality_detector"),
    FallbackDetectorSpec("enable_metadata_leakage_detector", "__fallback_metadata_leakage", "output_rail", "metadata_leakage_detector"),
    FallbackDetectorSpec("enable_sensitive_echo_detector", "__fallback_sensitive_echo", "output_rail", "sensitive_echo_detector"),
    FallbackDetectorSpec("enable_language_drift_detector", "__fallback_language_drift", "output_rail", "language_drift_detector"),
    FallbackDetectorSpec("enable_prompt_leakage_detector", "__fallback_prompt_leakage", "output_rail", "prompt_leakage_detector"),
)

# This deliberately remains empty until a detector has both a supported runtime
# template and an evaluator.  Adding a detector here activates its catalogue
# entry for all fallback snapshots subject to its system switch.
IMPLEMENTED_FALLBACK_DETECTORS: tuple[FallbackDetectorSpec, ...] = ()


def build_fallback_runtime_config(
    fallback_policy_settings: Mapping[str, Any],
    *,
    implemented_detectors: tuple[FallbackDetectorSpec, ...] = IMPLEMENTED_FALLBACK_DETECTORS,
) -> NormalizedConfig:
    """Create the immutable fallback graph's normalized runtime configuration.

    ``implemented_detectors`` is intentionally empty in P1.  An implementation
    adds supported detector specs here; disabled system switches then keep that
    detector node out of the graph.
    """

    settings = dict(fallback_policy_settings)
    detector_nodes = [
        _detector_node(spec, settings)
        for spec in implemented_detectors
        if settings.get(spec.setting_key, True)
    ]
    input_detector_ids = [
        node["rule_id"] for node in detector_nodes if node["__rail"] == "input_rail"
    ]
    input_nodes = [node for node in detector_nodes if node["__rail"] == "input_rail"]
    output_nodes = [node for node in detector_nodes if node["__rail"] == "output_rail"]
    for node in (*input_nodes, *output_nodes):
        node.pop("__rail", None)

    input_nodes.append(
        {
            "__template_key": "logic_gate",
            "rule_id": FALLBACK_INPUT_OR_ID,
            "enabled": True,
            "priority": 900,
            "gate": "any",
            "inputs": input_detector_ids,
            "__allow_empty_inputs": True,
            "action_on_hit": "default",
            "action_on_error": "default",
        }
    )
    if settings.get("enable_llm_review_in_fallback_policy", False):
        input_nodes.append(
            {
                "__template_key": "llm_review",
                "rule_id": FALLBACK_LLM_REVIEW_ID,
                "enabled": True,
                "priority": 1000,
                "depend_on": FALLBACK_INPUT_OR_ID,
                "provider_id": str(settings.get("default_llm_provider", "") or ""),
                "audit_prompt": FALLBACK_LLM_REVIEW_PROMPT,
                "action_on_hit": "default",
                "action_on_error": "default",
            }
        )

    raw_config = {
        "fallback_policy_settings": settings,
        "input_rail": {
            "__policy_step_settings": {"enabled": True},
            "rule_list": input_nodes,
        },
        "routing_rail": {
            "__policy_step_settings": {"enabled": False},
            "rule_list": [],
        },
        "request_rail": {
            "__policy_step_settings": {"enabled": False},
            "rule_list": [],
        },
        "prompt_rail": {
            "__policy_step_settings": {"enabled": False},
            "rule_list": [],
        },
        "output_rail": {
            "__policy_step_settings": {"enabled": True},
            "rule_list": output_nodes,
        },
    }
    return normalize_config(raw_config)


def _detector_node(spec: FallbackDetectorSpec, settings: Mapping[str, Any]) -> dict[str, Any]:
    node = dict(spec.config)
    node.update({
        "__rail": spec.rail,
        "__template_key": spec.template_key,
        "rule_id": spec.node_id,
        "enabled": True,
        "priority": 100,
        "action_on_hit": "default",
        "action_on_error": "default",
    })
    return node
