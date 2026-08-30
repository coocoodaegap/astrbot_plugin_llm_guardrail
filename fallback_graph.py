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
FALLBACK_ENFORCEMENT_ID = "__fallback_input_enforcement"
FALLBACK_OUTPUT_OR_ID = "__fallback_output_or"
FALLBACK_OUTPUT_LLM_REVIEW_ID = "__fallback_output_llm_review"
FALLBACK_OUTPUT_ENFORCEMENT_ID = "__fallback_output_enforcement"
FALLBACK_LLM_REVIEW_PROMPT = (
    "Review the supplied text for safety risks indicated by the preceding "
    "detectors. Return whether the text should be treated as unsafe."
)
FALLBACK_OUTPUT_LLM_REVIEW_PROMPT = (
    "Review the candidate reply in the context of the user's request. The "
    "preceding output detectors found a possible safety or reliability issue. "
    "Return whether this reply should be treated as unsafe or unsuitable to send."
)
FALLBACK_OUTPUT_LLM_REVIEW_TEMPLATE = (
    "User message:\n${event_origin}\n\nFinal request:\n${req_origin}\n\n"
    "Candidate reply:\n${res_origin}"
)


@dataclass(frozen=True)
class FallbackDetectorSpec:
    """A future built-in detector's code-owned placement.

    The catalogue records the code-owned fallback composition; a detector joins
    the runtime graph only after its template/evaluator is implemented and
    registered here.  P1 starts with the three local input detectors; all
    remaining catalogue entries stay dormant until their later implementation.
    """

    node_id: str
    rail: str
    template_key: str
    config: Mapping[str, Any] = field(default_factory=dict)


# The catalogue preserves the intended fallback composition before every
# detector is implemented.  Only completed, independently tested detectors
# are listed in ``IMPLEMENTED_FALLBACK_DETECTORS``.
FALLBACK_DETECTOR_CATALOGUE: tuple[FallbackDetectorSpec, ...] = (
    FallbackDetectorSpec("__fallback_encoded_payload", "input_rail", "encoded_payload_detector"),
    FallbackDetectorSpec("__fallback_length_anomaly", "input_rail", "length_anomaly_detector"),
    FallbackDetectorSpec("__fallback_role_marker_spoofing", "input_rail", "role_marker_spoofing_detector"),
    FallbackDetectorSpec("__fallback_external_fetch", "input_rail", "external_fetch_detector"),
    FallbackDetectorSpec("__fallback_instruction_override", "input_rail", "instruction_override_detector"),
    FallbackDetectorSpec("__fallback_multi_turn_escalation", "input_rail", "multi_turn_escalation_detector"),
    FallbackDetectorSpec("__fallback_prompt_injection_combo", "input_rail", "prompt_injection_combo_detector"),
    FallbackDetectorSpec("__fallback_format_violation", "output_rail", "format_violation_detector"),
    FallbackDetectorSpec("__fallback_poor_quality", "output_rail", "poor_quality_detector"),
    FallbackDetectorSpec("__fallback_metadata_leakage", "output_rail", "metadata_leakage_detector"),
    FallbackDetectorSpec("__fallback_sensitive_echo", "output_rail", "sensitive_echo_detector"),
    FallbackDetectorSpec("__fallback_language_drift", "output_rail", "language_drift_detector"),
    FallbackDetectorSpec("__fallback_prompt_leakage", "output_rail", "prompt_leakage_detector"),
)

# A registered detector is only an observation node in fallback.  The terminal
# LLM review or enforcement gate owns the default block/observe action.
IMPLEMENTED_FALLBACK_DETECTORS: tuple[FallbackDetectorSpec, ...] = (
    FALLBACK_DETECTOR_CATALOGUE[0],
    FALLBACK_DETECTOR_CATALOGUE[1],
    FALLBACK_DETECTOR_CATALOGUE[2],
    FALLBACK_DETECTOR_CATALOGUE[3],
    FALLBACK_DETECTOR_CATALOGUE[4],
    FALLBACK_DETECTOR_CATALOGUE[8],
)


def build_fallback_runtime_config(
    fallback_policy_settings: Mapping[str, Any],
    *,
    access_control: Mapping[str, Any] | None = None,
    system_constants: Mapping[str, str] | None = None,
    implemented_detectors: tuple[FallbackDetectorSpec, ...] = IMPLEMENTED_FALLBACK_DETECTORS,
) -> NormalizedConfig:
    """Create the immutable fallback graph's normalized runtime configuration.

    ``implemented_detectors`` contains only completed detector implementations.
    The input/output system switches include or remove each rail's complete
    fallback graph; individual detector selection is code-owned.
    """

    settings = dict(fallback_policy_settings)
    input_checks_enabled = bool(settings.get("enable_fallback_input_checks", True))
    output_checks_enabled = bool(settings.get("enable_fallback_output_checks", True))
    detector_nodes = [
        _detector_node(spec, settings)
        for spec in implemented_detectors
        if (spec.rail == "input_rail" and input_checks_enabled)
        or (spec.rail == "output_rail" and output_checks_enabled)
    ]
    input_detector_ids = [
        node["rule_id"] for node in detector_nodes if node["__rail"] == "input_rail"
    ]
    input_nodes = [node for node in detector_nodes if node["__rail"] == "input_rail"]
    output_nodes = [node for node in detector_nodes if node["__rail"] == "output_rail"]
    for node in (*input_nodes, *output_nodes):
        node.pop("__rail", None)

    if input_detector_ids:
        input_nodes.append(
            {
            "__template_key": "logic_gate",
            "rule_id": FALLBACK_INPUT_OR_ID,
            "enabled": True,
            "priority": 900,
            "gate": "any",
            "inputs": input_detector_ids,
            "__allow_empty_inputs": True,
            "action_on_hit": "observe",
            "action_on_error": "default",
            }
        )
    if input_detector_ids and settings.get("enable_llm_review_in_fallback_policy", False):
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
    elif input_detector_ids:
        input_nodes.append(
            {
                "__template_key": "logic_gate",
                "rule_id": FALLBACK_ENFORCEMENT_ID,
                "enabled": True,
                "priority": 1000,
                "gate": "all",
                "inputs": [FALLBACK_INPUT_OR_ID],
                "action_on_hit": "default",
                "action_on_error": "default",
            }
        )

    output_detector_ids = [node["rule_id"] for node in output_nodes]
    if output_detector_ids:
        output_nodes.append(
            {
                "__template_key": "logic_gate",
                "rule_id": FALLBACK_OUTPUT_OR_ID,
                "enabled": True,
                "priority": 900,
                "gate": "any",
                "inputs": output_detector_ids,
                "action_on_hit": "observe",
                "action_on_error": "default",
            }
        )
        if settings.get("enable_output_llm_review_in_fallback_policy", False):
            output_nodes.append(
                {
                    "__template_key": "llm_review",
                    "rule_id": FALLBACK_OUTPUT_LLM_REVIEW_ID,
                    "enabled": True,
                    "priority": 1000,
                    "depend_on": FALLBACK_OUTPUT_OR_ID,
                    "provider_id": str(settings.get("default_llm_provider", "") or ""),
                    "audit_prompt": FALLBACK_OUTPUT_LLM_REVIEW_PROMPT,
                    "inspection_template": FALLBACK_OUTPUT_LLM_REVIEW_TEMPLATE,
                    "action_on_hit": "default",
                    "action_on_error": "default",
                }
            )
        else:
            output_nodes.append(
                {
                    "__template_key": "logic_gate",
                    "rule_id": FALLBACK_OUTPUT_ENFORCEMENT_ID,
                    "enabled": True,
                    "priority": 1000,
                    "gate": "all",
                    "inputs": [FALLBACK_OUTPUT_OR_ID],
                    "action_on_hit": "default",
                    "action_on_error": "default",
                }
            )

    raw_config = {
        "fallback_policy_settings": settings,
        "system_constants": dict(system_constants or {}),
        # Access control is system-owned and must remain active when the
        # policy library falls back to this code-owned graph.
        "access_control": dict(access_control or {}),
        "input_rail": {
            "__policy_step_settings": {"enabled": input_checks_enabled},
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
            "__policy_step_settings": {"enabled": output_checks_enabled},
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
        "action_on_hit": "observe",
        "action_on_error": "default",
    })
    return node
