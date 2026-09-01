"""Configuration normalization for the LLM Guardrail plugin."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


RAIL_NAMES = (
    "input_rail",
    "routing_rail",
    "request_rail",
    "prompt_rail",
    "output_rail",
)

RULE_TEMPLATES: dict[str, set[str]] = {
    "input_rail": {
        "plain_keywords",
        "regex_pattern",
        "contains_request_user_id",
        "rag_judge",
        "llm_review",
    },
    "request_rail": {
        "plain_keywords",
        "regex_pattern",
        "rag_judge",
        "llm_review",
    },
    "prompt_rail": {"strengthen_prompt"},
    "routing_rail": {"route_policy"},
    "output_rail": {
        "plain_keywords",
        "regex_pattern",
        "rag_judge",
        "llm_review",
    },
}

# Components are local policy graph nodes, not reusable rule-library templates.
# They remain supported by the runtime normalizer because compiled policies emit
# them into a rail's rule_list alongside reusable rules.
COMPONENT_TEMPLATES: dict[str, set[str]] = {
    rail_name: {"logic_gate"} for rail_name in RAIL_NAMES
}
COMPONENT_TEMPLATES["input_rail"].update(
    {
        "encoded_payload_detector",
        "length_anomaly_detector",
        "role_marker_spoofing_detector",
        "external_fetch_detector",
        "instruction_override_detector",
        "context_extractor",
        "contains_forward",
        "contains_file",
        "contains_image",
        "contains_record",
        "contains_video",
    }
)
STAGE_ORIGIN_TEMPLATES = {
    "input_rail": "${event_origin}",
    "request_rail": "${req_origin}",
    "output_rail": "${res_origin}",
}
COMPONENT_TEMPLATES["request_rail"].update(
    {
        "encoded_payload_detector",
        "length_anomaly_detector",
        "role_marker_spoofing_detector",
        "external_fetch_detector",
        "instruction_override_detector",
        "context_extractor",
    }
)
COMPONENT_TEMPLATES["output_rail"].update(
    {
        "format_violation_detector",
        "poor_quality_detector",
        "metadata_leakage_detector",
        "refusal_leakage_detector",
        "sensitive_echo_detector",
        "language_drift_detector",
        "context_extractor",
    }
)
SUPPORTED_TEMPLATES: dict[str, set[str]] = {
    rail_name: RULE_TEMPLATES[rail_name] | COMPONENT_TEMPLATES[rail_name]
    for rail_name in RAIL_NAMES
}

INPUT_ACTIONS = {
    "default",
    "observe",
    "retry_generation",
    "block",
    "sanitize",
}
OUTPUT_ACTIONS = {
    "default",
    "observe",
    "retry_generation",
    "block",
    "sanitize",
}
DEFAULT_OBSERVE_OUTPUT_COMPONENT_TEMPLATES = {
    "format_violation_detector",
    "metadata_leakage_detector",
    "refusal_leakage_detector",
    "sensitive_echo_detector",
    "language_drift_detector",
}
FIXED_OBSERVE_COMPONENT_TEMPLATES = {"context_extractor"}
ERROR_ACTIONS = {"default", "discard", "record", "block"}
DEFAULT_ERROR_ACTIONS = {"discard", "record", "block"}
LEGACY_FALLBACK_DETECTOR_SWITCHES = (
    "enable_encoded_payload_detector",
    "enable_length_anomaly_detector",
    "enable_role_marker_spoofing_detector",
    "enable_external_fetch_detector",
    "enable_instruction_override_detector",
    "enable_multi_turn_escalation_detector",
    "enable_prompt_injection_combo_detector",
    "enable_format_violation_detector",
    "enable_poor_quality_detector",
    "enable_metadata_leakage_detector",
    "enable_sensitive_echo_detector",
    "enable_language_drift_detector",
    "enable_prompt_leakage_detector",
)
DEFAULT_REQUEST_BLOCK_MESSAGE = "用户 ${user_id} 的请求在 Step ${step_number} 被阻断。"
DEFAULT_BLACKLIST_MESSAGE = (
    "用户 ${user_id} 已因多次触发风险规则被临时限制使用，请稍后再试。"
)
LOGIC_GATES = {"all", "any"}
LOGIC_GATE_INPUT_PATTERN = re.compile(
    r"^[!?~]?(?:[a-z][a-z0-9_]{0,63}|__[a-z][a-z0-9_]{0,63})"
    r"(?:\.[a-z][a-z0-9_]{0,63}\??)?$"
)
LOGIC_GATE_VALUE_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]*)\}")
SYSTEM_CONSTANT_NAME_PATTERN = re.compile(r"^[A-Z0-9_]{1,64}$")
INSERTION_TARGETS = {
    "system_prefix",
    "system_suffix",
    "temp_user_context",
    "input_wrapper",
}
SESSION_SCOPE_MODES = {
    "all_run",
    "all_pass",
    "all_block",
    "enabled_or_pass",
    "enabled_or_block",
}


@dataclass(frozen=True)
class SessionScopeDecision:
    action: str
    reason: str
    chat_type: str
    mode: str


@dataclass
class NormalizedNode:
    rail: str
    template_key: str
    index: int
    enabled: bool
    node_id: str
    user_node_id: str
    anonymous: bool
    depend_on: str
    priority: int
    config: dict[str, Any]
    valid: bool = True
    warnings: list[str] = field(default_factory=list)

    # ``rule_id`` remains the raw compatibility field in ``rule_list``.  The
    # runtime model is node-based, so consumers should use ``node_id``.
    @property
    def rule_id(self) -> str:
        return self.node_id

    @property
    def user_rule_id(self) -> str:
        return self.user_node_id


@dataclass
class NormalizedRail:
    rail: str
    enabled: bool
    settings: dict[str, Any]
    nodes: list[NormalizedNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def rules(self) -> list[NormalizedNode]:
        """Compatibility view for code reading the legacy ``rule_list`` input."""

        return self.nodes


# Kept for third-party callers during the P1 compatibility window.  New code
# must use NormalizedNode and NormalizedRail.nodes.
NormalizedRule = NormalizedNode


@dataclass
class NormalizedConfig:
    schema_version: str
    fallback_policy_settings: dict[str, Any]
    system_constants: dict[str, str]
    session_control: dict[str, Any]
    access_control: dict[str, Any]
    session_policy_state: dict[str, Any]
    debug_settings: dict[str, Any]
    rails: dict[str, NormalizedRail]
    warnings: list[str] = field(default_factory=list)


def normalize_config(raw_config: Any) -> NormalizedConfig:
    """Normalize AstrBotConfig or a dict into runtime-only dataclasses."""

    warnings: list[str] = []
    schema_version = "0.5.0"
    fallback_policy_settings = _normalize_fallback_policy_settings(
        _as_dict(_config_get(raw_config, "fallback_policy_settings", {})),
        warnings,
    )
    system_constants = _normalize_system_constants(
        _config_get(raw_config, "system_constants", {}),
        warnings,
    )

    raw_session_control = _as_dict(_config_get(raw_config, "session_control", {}))
    session_control = _normalize_session_control(
        raw_session_control,
        warnings=warnings,
    )
    access_control = _normalize_access_control(
        _as_dict(_config_get(raw_config, "access_control", {})),
        warnings,
    )
    session_policy_state = _normalize_session_policy_state(
        _as_dict(_config_get(raw_config, "session_policy_state", {})),
        warnings,
    )
    debug_settings = _normalize_debug_settings(
        _as_dict(_config_get(raw_config, "debug_settings", {})),
        warnings,
    )

    rails: dict[str, NormalizedRail] = {}
    seen_rule_ids: set[str] = set()

    for rail_name in RAIL_NAMES:
        rail = _normalize_rail(
            rail_name=rail_name,
            raw_rail=_config_get(raw_config, rail_name, {}),
            seen_rule_ids=seen_rule_ids,
            fallback_policy_settings=fallback_policy_settings,
        )
        rails[rail_name] = rail
        warnings.extend(rail.warnings)

    _validate_cross_references(rails, warnings)

    return NormalizedConfig(
        schema_version=schema_version,
        fallback_policy_settings=fallback_policy_settings,
        system_constants=system_constants,
        session_control=session_control,
        access_control=access_control,
        session_policy_state=session_policy_state,
        debug_settings=debug_settings,
        rails=rails,
        warnings=warnings,
    )


def _normalize_rail(
    rail_name: str,
    raw_rail: Any,
    seen_rule_ids: set[str],
    fallback_policy_settings: dict[str, Any],
) -> NormalizedRail:
    warnings: list[str] = []
    rail_dict = _as_dict(raw_rail)
    if not isinstance(raw_rail, dict) and raw_rail is not None:
        warnings.append(f"{rail_name} is not an object; fallback to defaults")

    settings = _coerce_rail_settings(
        rail_name,
        _merge_defaults(
            _rail_defaults(rail_name, fallback_policy_settings),
            rail_dict.get("__policy_step_settings", {}),
        ),
        warnings,
    )

    raw_rules = rail_dict.get("rule_list", [])
    if raw_rules is None:
        raw_rules = []
    if not isinstance(raw_rules, list):
        warnings.append(f"{rail_name}.rule_list is not a list; no rules loaded")
        raw_rules = []

    nodes: list[NormalizedNode] = []
    for index, raw_rule in enumerate(raw_rules):
        node = _normalize_node(rail_name, index, raw_rule, seen_rule_ids)
        nodes.append(node)
        warnings.extend(node.warnings)

    return NormalizedRail(
        rail=rail_name,
        enabled=_as_bool(settings.get("enabled"), True),
        settings=settings,
        nodes=nodes,
        warnings=warnings,
    )


def _normalize_session_control(
    raw_session_control: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    group_mode = _normalize_session_mode(
        "session_control.group_chat_mode",
        raw_session_control.get("group_chat_mode", "all_run"),
        warnings,
    )
    private_mode = _normalize_session_mode(
        "session_control.private_chat_mode",
        raw_session_control.get("private_chat_mode", "all_run"),
        warnings,
    )
    group_enabled = _clean_string_list(raw_session_control.get("group_chat_enabled", []))
    private_enabled = _clean_string_list(
        raw_session_control.get("private_chat_enabled", [])
    )

    return {
        "group_chat_mode": group_mode,
        "group_chat_enabled": group_enabled,
        "private_chat_mode": private_mode,
        "private_chat_enabled": private_enabled,
    }


def _normalize_session_mode(
    label: str,
    value: Any,
    warnings: list[str],
) -> str:
    mode = _as_str(value, "all_run").strip()
    if mode not in SESSION_SCOPE_MODES:
        warnings.append(f"{label} is invalid; fallback to all_run")
        return "all_run"
    return mode


def _normalize_access_control(
    raw_settings: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Normalize P2 automatic input access-control settings.

    ``-1`` is intentionally the only permanent-duration sentinel.  Keeping
    ``0`` invalid prevents a zero-minute decision from silently becoming a
    permanent one after configuration is saved through a different surface.
    """

    duration = _as_int(raw_settings.get("blacklist_duration_minutes"), 60)
    if duration == 0 or duration < -1:
        warnings.append(
            "access_control.blacklist_duration_minutes must be -1 or positive; fallback to 60"
        )
        duration = 60

    threshold = _as_int(raw_settings.get("blacklist_max_violations"), 3)
    if threshold < 1:
        warnings.append(
            "access_control.blacklist_max_violations must be positive; fallback to 3"
        )
        threshold = 3

    notice_interval = _as_int(
        raw_settings.get("blacklist_message_interval_minutes"), 5
    )
    if notice_interval < -1:
        warnings.append(
            "access_control.blacklist_message_interval_minutes must be -1, 0, or positive; fallback to 5"
        )
        notice_interval = 5

    return {
        "auto_blacklist_enabled": _as_bool(
            raw_settings.get("auto_blacklist_enabled"), False
        ),
        "blacklist_duration_minutes": duration,
        "blacklist_max_violations": threshold,
        "blacklist_message_interval_minutes": notice_interval,
        "blacklist_message": _as_str(
            raw_settings.get(
                "blacklist_message",
                DEFAULT_BLACKLIST_MESSAGE,
            )
        ),
    }


def _normalize_session_policy_state(
    raw_settings: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Normalize P2-A UMO state-monitoring retention settings.

    The former ``ttl_seconds`` field is accepted as a migration alias only.
    It is no longer a route-cache TTL: it controls inactivity retention of the
    whole UMO state record until P2-C introduces a separate route-cache policy.
    """

    ttl_source = raw_settings.get(
        "state_ttl_seconds", raw_settings.get("ttl_seconds", 604800)
    )
    state_ttl_seconds = _as_int(ttl_source, 604800)
    if state_ttl_seconds < 0 or (0 < state_ttl_seconds < 60):
        warnings.append(
            "session_policy_state.state_ttl_seconds must be 0 or at least 60; fallback to 604800"
        )
        state_ttl_seconds = 604800

    max_entries = _as_int(raw_settings.get("max_entries"), 500)
    if max_entries < 1:
        warnings.append(
            "session_policy_state.max_entries must be positive; fallback to 500"
        )
        max_entries = 500

    activity_log_limit = _as_int(raw_settings.get("activity_log_limit"), 50)
    if activity_log_limit < 1:
        warnings.append(
            "session_policy_state.activity_log_limit must be positive; fallback to 50"
        )
        activity_log_limit = 50

    return {
        "enabled": _as_bool(raw_settings.get("enabled"), True),
        "state_ttl_seconds": state_ttl_seconds,
        "max_entries": max_entries,
        "activity_log_limit": activity_log_limit,
    }


def resolve_session_scope(
    session_control: dict[str, Any],
    umo: str,
    is_private_chat: bool,
) -> SessionScopeDecision:
    chat_type = "private" if is_private_chat else "group"
    mode_key = "private_chat_mode" if is_private_chat else "group_chat_mode"
    enabled_key = "private_chat_enabled" if is_private_chat else "group_chat_enabled"
    mode = str(session_control.get(mode_key, "all_run"))
    enabled = set(_clean_string_list(session_control.get(enabled_key, [])))

    if mode == "all_run":
        return SessionScopeDecision("run", f"{chat_type}_all_run", chat_type, mode)
    if mode == "all_pass":
        return SessionScopeDecision("pass", f"{chat_type}_all_pass", chat_type, mode)
    if mode == "all_block":
        return SessionScopeDecision("block", f"{chat_type}_all_block", chat_type, mode)
    if umo and umo in enabled:
        return SessionScopeDecision("run", f"{chat_type}_enabled", chat_type, mode)
    if mode == "enabled_or_block":
        return SessionScopeDecision(
            "block", f"{chat_type}_not_enabled", chat_type, mode
        )
    return SessionScopeDecision("pass", f"{chat_type}_not_enabled", chat_type, mode)


def _normalize_node(
    rail_name: str, index: int, raw_rule: Any, seen_rule_ids: set[str]
) -> NormalizedNode:
    warnings: list[str] = []
    rule_dict = _as_dict(raw_rule)
    if not isinstance(raw_rule, dict):
        warnings.append(f"{rail_name}[{index}] is not an object; skipped")

    template_key = _as_str(rule_dict.get("__template_key") or rule_dict.get("template_key"))
    enabled = _as_bool(rule_dict.get("enabled", True), True)
    user_rule_id = _as_str(rule_dict.get("rule_id", "")).strip()
    anonymous = not user_rule_id
    rule_id = (
        f"_auto.{rail_name}.{template_key or 'unknown'}.{index}"
        if anonymous
        else user_rule_id
    )
    depend_on = _as_str(rule_dict.get("depend_on", "")).strip()
    priority = _as_int(rule_dict.get("priority", 100), 100)
    config = dict(rule_dict)
    raw_action_on_hit = _as_str(config.get("action_on_hit", "default")) or "default"
    raw_action_on_error = _as_str(config.get("action_on_error", "default")) or "default"
    valid = True

    if not template_key:
        template_key = "unknown"
        valid = False
        enabled = False
        warnings.append(f"{rail_name}[{index}] has no __template_key; skipped")
    elif template_key not in SUPPORTED_TEMPLATES[rail_name]:
        valid = False
        enabled = False
        warnings.append(
            f"{rail_name}.{rule_id} uses unsupported template {template_key}; skipped"
        )

    if user_rule_id:
        if user_rule_id in seen_rule_ids:
            valid = False
            enabled = False
            warnings.append(f"duplicate rule_id {user_rule_id}; later rule skipped")
        else:
            seen_rule_ids.add(user_rule_id)

    if template_key == "plain_keywords":
        _normalize_plain_keywords(rule_id, config, warnings)
    elif template_key == "regex_pattern":
        _normalize_regex_pattern(rule_id, config, warnings)
        if config.get("_compiled_pattern") is None:
            valid = False
            enabled = False
    elif template_key == "logic_gate":
        _normalize_logic_gate(rule_id, config, warnings)
    elif template_key in {
        "encoded_payload_detector",
        "length_anomaly_detector",
        "role_marker_spoofing_detector",
        "external_fetch_detector",
        "instruction_override_detector",
    }:
        _normalize_input_detector(rule_id, template_key, config, warnings)
    elif template_key == "context_extractor":
        _normalize_context_extractor(rule_id, config, warnings)
    elif template_key == "poor_quality_detector":
        _normalize_poor_quality_detector(rule_id, config, warnings)
    elif template_key == "metadata_leakage_detector":
        _normalize_metadata_leakage_detector(rule_id, config, warnings)
    elif template_key == "format_violation_detector":
        _normalize_format_violation_detector(rule_id, config, warnings)
    elif template_key == "refusal_leakage_detector":
        _normalize_refusal_leakage_detector(rule_id, config, warnings)
    elif template_key == "language_drift_detector":
        _normalize_language_drift_detector(rule_id, config, warnings)
    elif template_key == "sensitive_echo_detector":
        _normalize_sensitive_echo_detector(rule_id, config, warnings)
    elif template_key in MESSAGE_FACT_TEMPLATES:
        _normalize_message_fact_component(rule_id, template_key, config, warnings)
        if template_key == "contains_request_user_id" and not config["user_ids"]:
            valid = False
            enabled = False
    elif template_key == "strengthen_prompt":
        _normalize_strengthen_prompt(rule_id, config, warnings)
    elif template_key == "route_policy":
        config["provider_id"] = _as_str(config.get("provider_id", "")).strip()
    elif template_key == "rag_judge":
        _normalize_rag_judge(rule_id, config, warnings)
        if not config.get("knowledge_bases"):
            valid = False
            enabled = False
    elif template_key == "llm_review":
        _normalize_llm_review(rule_id, config, warnings)
        if not config.get("audit_prompt"):
            valid = False
            enabled = False

    if template_key in {
        "plain_keywords",
        "regex_pattern",
        "logic_gate",
        "rag_judge",
        "llm_review",
        "encoded_payload_detector",
        "length_anomaly_detector",
        "role_marker_spoofing_detector",
        "external_fetch_detector",
        "instruction_override_detector",
        "context_extractor",
        "poor_quality_detector",
        "metadata_leakage_detector",
        "format_violation_detector",
        "refusal_leakage_detector",
        "language_drift_detector",
        "sensitive_echo_detector",
        *MESSAGE_FACT_TEMPLATES,
    }:
        raw_action = "observe" if (
            raw_action_on_hit == "default"
            and (
                template_key in MESSAGE_FACT_COMPONENT_TEMPLATES
                or template_key in FIXED_OBSERVE_COMPONENT_TEMPLATES
                or template_key in DEFAULT_OBSERVE_OUTPUT_COMPONENT_TEMPLATES
            )
        ) else raw_action_on_hit
        action = raw_action
        config["action_on_hit"] = action
        if action == "sanitize" and template_key not in {"plain_keywords", "regex_pattern"}:
            warnings.append(
                f"{rule_id}.action_on_hit=sanitize is only supported by plain_keywords and regex_pattern; fallback to default"
            )
            config["action_on_hit"] = (
                "observe"
                if (
                    template_key in MESSAGE_FACT_COMPONENT_TEMPLATES
                    or template_key in FIXED_OBSERVE_COMPONENT_TEMPLATES
                )
                else "default"
            )
        if rail_name in {"input_rail", "request_rail"} and action not in INPUT_ACTIONS:
            warnings.append(f"{rule_id}.action_on_hit is invalid; fallback to default")
            config["action_on_hit"] = (
                "observe"
                if (
                    template_key in MESSAGE_FACT_COMPONENT_TEMPLATES
                    or template_key in FIXED_OBSERVE_COMPONENT_TEMPLATES
                )
                else "default"
            )
        elif rail_name == "output_rail":
            if action not in OUTPUT_ACTIONS:
                warnings.append(
                    f"{rule_id}.action_on_hit is invalid; fallback to default"
                )
                config["action_on_hit"] = "default"
        elif rail_name in {"prompt_rail", "routing_rail"}:
            config["action_on_hit"] = "observe"

    if rail_name in {"input_rail", "request_rail", "output_rail"}:
        action_on_error = raw_action_on_error.strip()
        if action_on_error not in ERROR_ACTIONS:
            warnings.append(f"{rule_id}.action_on_error is invalid; fallback to default")
            action_on_error = "default"
        config["action_on_error"] = action_on_error

    if template_key in FIXED_OBSERVE_COMPONENT_TEMPLATES:
        if raw_action_on_hit not in {"default", "observe"}:
            warnings.append(f"{rule_id}.action_on_hit is fixed to observe")
        if raw_action_on_error != "default":
            warnings.append(f"{rule_id}.action_on_error is fixed to discard")
        config["action_on_hit"] = "observe"
        config["action_on_error"] = "discard"

    return NormalizedNode(
        rail=rail_name,
        template_key=template_key,
        index=index,
        enabled=enabled,
        node_id=rule_id,
        user_node_id=user_rule_id,
        anonymous=anonymous,
        depend_on=depend_on,
        priority=priority,
        config=config,
        valid=valid,
        warnings=warnings,
    )


def _normalize_plain_keywords(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    keywords = _clean_string_list(config.get("keywords", []))
    config["keywords"] = keywords
    config["threshold"] = _as_float(config.get("threshold", 1), 1.0)
    if config["threshold"] <= 0:
        warnings.append(f"{rule_id}.threshold must be positive; fallback to 1")
        config["threshold"] = 1.0

    keyword_keys = {item.casefold(): item for item in keywords}
    weight_map: dict[str, float] = {}
    for item in _clean_string_list(config.get("keyword_weights", [])):
        name, sep, raw_weight = item.partition(":")
        if not sep:
            warnings.append(f"{rule_id}.keyword_weights item {item!r} is invalid")
            continue
        keyword = name.strip()
        key = keyword.casefold()
        if key not in keyword_keys:
            warnings.append(
                f"{rule_id}.keyword_weights item {keyword!r} is not in keywords"
            )
            continue
        try:
            weight = float(raw_weight.strip())
        except ValueError:
            warnings.append(f"{rule_id}.keyword_weights item {item!r} has invalid weight")
            continue
        weight_map[key] = weight
    config["_keyword_weight_map"] = weight_map
    config["sanitizer"] = _as_str(config.get("sanitizer", ""))
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


def _normalize_regex_pattern(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    pattern = _as_str(config.get("pattern", ""))
    config["pattern"] = pattern
    config["sanitizer"] = _as_str(config.get("sanitizer", ""))
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"
    if not pattern:
        config["_compiled_pattern"] = None
        warnings.append(f"{rule_id}.pattern is empty; rule skipped")
        return
    try:
        config["_compiled_pattern"] = re.compile(pattern)
    except re.error as exc:
        config["_compiled_pattern"] = None
        warnings.append(f"{rule_id}.pattern failed to compile: {exc}")


def _normalize_logic_gate(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    gate = _as_str(config.get("gate", "all")).strip().lower()
    if gate not in LOGIC_GATES:
        warnings.append(f"{rule_id}.gate is invalid; fallback to all")
        gate = "all"
    config["gate"] = gate
    raw_inputs = config.get("inputs", [])
    config["inputs"] = (
        [str(item).strip() for item in raw_inputs if str(item).strip()]
        if isinstance(raw_inputs, list)
        else []
    )
    invalid_inputs = [
        value for value in config["inputs"]
        if LOGIC_GATE_INPUT_PATTERN.fullmatch(value) is None
    ]
    if invalid_inputs:
        warnings.append(
            f"{rule_id}.inputs has invalid logic-gate reference(s): "
            + ", ".join(invalid_inputs)
        )
        config["__invalid_logic_inputs"] = invalid_inputs
    else:
        config.pop("__invalid_logic_inputs", None)
    value_item_template = _as_str(config.get("value_item_template", "${value}"))
    if not _logic_gate_value_template_is_valid(value_item_template):
        warnings.append(
            f"{rule_id}.value_item_template only supports ${{value}} and ${{source}}; "
            "fallback to ${value}"
        )
        value_item_template = "${value}"
    config["value_item_template"] = value_item_template
    config["value_separator"] = _as_str(config.get("value_separator", "\n"))
    config["invert"] = _as_bool(config.get("invert", False), False)
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


def _logic_gate_value_template_is_valid(value: str) -> bool:
    matches = list(LOGIC_GATE_VALUE_PLACEHOLDER_PATTERN.finditer(value))
    if any(match.group(1) not in {"value", "source"} for match in matches):
        return False
    consumed = LOGIC_GATE_VALUE_PLACEHOLDER_PATTERN.sub("", value)
    return "${" not in consumed


def _normalize_input_detector(
    rule_id: str, template_key: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize policy-local, deterministic input detector parameters."""

    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000, rule_id, "scan_limit_chars", warnings
    )
    if template_key == "encoded_payload_detector":
        config["min_base64_chars"] = _bounded_int(
            config.get("min_base64_chars"), 80, 16, 100000, rule_id, "min_base64_chars", warnings
        )
        config["min_base64_distinct_chars"] = _bounded_int(
            config.get("min_base64_distinct_chars"), 4, 2, 64, rule_id, "min_base64_distinct_chars", warnings
        )
        config["min_percent_escape_count"] = _bounded_int(
            config.get("min_percent_escape_count"), 8, 2, 100000, rule_id, "min_percent_escape_count", warnings
        )
        config["min_unicode_escape_count"] = _bounded_int(
            config.get("min_unicode_escape_count"), 6, 2, 100000, rule_id, "min_unicode_escape_count", warnings
        )
        config["min_hex_bytes"] = _bounded_int(
            config.get("min_hex_bytes"), 24, 4, 100000, rule_id, "min_hex_bytes", warnings
        )
        config["min_rot13_chars"] = _bounded_int(
            config.get("min_rot13_chars"), 32, 8, 100000, rule_id, "min_rot13_chars", warnings
        )
        config["min_encoded_ratio"] = _bounded_float(
            config.get("min_encoded_ratio"), 0.35, 0.01, 1.0, rule_id, "min_encoded_ratio", warnings
        )
        config["min_zero_width_chars"] = _bounded_int(
            config.get("min_zero_width_chars"), 8, 1, 100000, rule_id, "min_zero_width_chars", warnings
        )
        config["min_zero_width_ratio"] = _bounded_float(
            config.get("min_zero_width_ratio"), 0.02, 0.0, 1.0, rule_id, "min_zero_width_ratio", warnings
        )
        config["max_candidate_segments"] = _bounded_int(
            config.get("max_candidate_segments"), 32, 1, 1000, rule_id, "max_candidate_segments", warnings
        )
        config["max_decode_bytes"] = _bounded_int(
            config.get("max_decode_bytes"), 4096, 16, 1000000, rule_id, "max_decode_bytes", warnings
        )
        config["min_signal_families"] = _bounded_int(
            config.get("min_signal_families"), 2, 1, 6, rule_id, "min_signal_families", warnings
        )
        for key, default in {
            "detect_base64": True,
            "detect_percent_encoding": True,
            "detect_unicode_escape": True,
            "detect_hex": True,
            "detect_rot13_wrapper": True,
            "detect_zero_width": True,
        }.items():
            config[key] = _as_bool(config.get(key), default)
    elif template_key == "length_anomaly_detector":
        config["hard_max_chars"] = _bounded_int(
            config.get("hard_max_chars"), 8000, 1, 1000000, rule_id, "hard_max_chars", warnings
        )
        config["max_code_fence_pairs"] = _bounded_int(
            config.get("max_code_fence_pairs"), 6, 1, 1000, rule_id, "max_code_fence_pairs", warnings
        )
        config["max_separator_run"] = _bounded_int(
            config.get("max_separator_run"), 48, 4, 10000, rule_id, "max_separator_run", warnings
        )
        config["max_repeat_run"] = _bounded_int(
            config.get("max_repeat_run"), 80, 4, 10000, rule_id, "max_repeat_run", warnings
        )
        config["duplicate_line_min_chars"] = _bounded_int(
            config.get("duplicate_line_min_chars"), 16, 1, 10000, rule_id, "duplicate_line_min_chars", warnings
        )
        config["duplicate_line_min_count"] = _bounded_int(
            config.get("duplicate_line_min_count"), 4, 2, 10000, rule_id, "duplicate_line_min_count", warnings
        )
        config["duplicate_line_ratio"] = _bounded_float(
            config.get("duplicate_line_ratio"), 0.66, 0.01, 1.0, rule_id, "duplicate_line_ratio", warnings
        )
        config["min_invisible_chars"] = _bounded_int(
            config.get("min_invisible_chars"), 8, 1, 100000, rule_id, "min_invisible_chars", warnings
        )
        config["max_invisible_ratio"] = _bounded_float(
            config.get("max_invisible_ratio"), 0.04, 0.0, 1.0, rule_id, "max_invisible_ratio", warnings
        )
        config["min_structural_signals"] = _bounded_int(
            config.get("min_structural_signals"), 2, 1, 5, rule_id, "min_structural_signals", warnings
        )
    elif template_key == "external_fetch_detector":
        config["max_resources"] = _bounded_int(
            config.get("max_resources"), 24, 1, 1000, rule_id, "max_resources", warnings
        )
        config["max_action_gap_chars"] = _bounded_int(
            config.get("max_action_gap_chars"), 120, 1, 10000, rule_id, "max_action_gap_chars", warnings
        )
        config["min_evidence"] = _bounded_int(
            config.get("min_evidence"), 2, 1, 4, rule_id, "min_evidence", warnings
        )
        for key, default in {
            "detect_http_resources": True,
            "detect_markdown_remote_image": True,
            "detect_command_fetch": True,
            "detect_prompt_import": True,
            "detect_external_transfer": True,
        }.items():
            config[key] = _as_bool(config.get(key), default)
    elif template_key == "role_marker_spoofing_detector":
        config["min_indicators"] = _bounded_int(
            config.get("min_indicators"), 2, 1, 5, rule_id, "min_indicators", warnings
        )
        config["max_lines"] = _bounded_int(
            config.get("max_lines"), 160, 1, 10000, rule_id, "max_lines", warnings
        )
        for key, default in {
            "detect_serialized_message_envelope": True,
            "detect_tool_invocation_envelope": True,
            "detect_reserved_delimiters": True,
            "detect_log_like_headers": True,
        }.items():
            config[key] = _as_bool(config.get(key), default)
    else:
        config["min_evidence"] = _bounded_int(
            config.get("min_evidence"), 2, 1, 4, rule_id, "min_evidence", warnings
        )
        config["max_token_gap"] = _bounded_int(
            config.get("max_token_gap"), 12, 1, 100, rule_id, "max_token_gap", warnings
        )
        for key, default in {
            "detect_instruction_replacement": True,
            "detect_hidden_content_request": True,
            "detect_authority_claim": True,
            "detect_role_reassignment": True,
        }.items():
            config[key] = _as_bool(config.get(key), default)
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


def _normalize_context_extractor(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize the P4 data-only context component without a policy cap."""

    turns = _as_int(config.get("turns"), 3)
    if turns < 0:
        warnings.append(f"{rule_id}.turns must be non-negative; fallback to 3")
        turns = 3
    config["turns"] = turns
    config["user_only"] = _as_bool(config.get("user_only"), False)
    if _as_str(config.get("inspection_template", "")).strip():
        warnings.append(f"{rule_id}.inspection_template is ignored for context_extractor")
    config["inspection_template"] = ""


def _normalize_poor_quality_detector(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize the deterministic, non-semantic Step 5 quality detector."""

    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000,
        rule_id, "scan_limit_chars", warnings,
    )
    config["min_visible_chars"] = _bounded_int(
        config.get("min_visible_chars"), 1, 1, 10000,
        rule_id, "min_visible_chars", warnings,
    )
    config["max_punctuation_ratio"] = _bounded_float(
        config.get("max_punctuation_ratio"), 0.95, 0.5, 1.0,
        rule_id, "max_punctuation_ratio", warnings,
    )
    config["min_repeat_run"] = _bounded_int(
        config.get("min_repeat_run"), 80, 4, 10000,
        rule_id, "min_repeat_run", warnings,
    )
    config["duplicate_line_min_chars"] = _bounded_int(
        config.get("duplicate_line_min_chars"), 16, 1, 10000,
        rule_id, "duplicate_line_min_chars", warnings,
    )
    config["duplicate_line_min_count"] = _bounded_int(
        config.get("duplicate_line_min_count"), 4, 2, 10000,
        rule_id, "duplicate_line_min_count", warnings,
    )
    config["min_signal_families"] = _bounded_int(
        config.get("min_signal_families"), 1, 1, 4,
        rule_id, "min_signal_families", warnings,
    )
    for key, default in {
        "detect_unformatted_error_envelope": True,
        "ignore_fenced_code": True,
    }.items():
        config[key] = _as_bool(config.get(key), default)
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


def _normalize_metadata_leakage_detector(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize the bounded runtime-artefact candidate detector."""

    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000,
        rule_id, "scan_limit_chars", warnings,
    )
    config["max_structures"] = _bounded_int(
        config.get("max_structures"), 24, 1, 256,
        rule_id, "max_structures", warnings,
    )
    config["ignore_fenced_code"] = _as_bool(
        config.get("ignore_fenced_code"), True
    )
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "observe")) or "observe"


def _normalize_format_violation_detector(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize bounded request-format extraction and output verification."""

    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000,
        rule_id, "scan_limit_chars", warnings,
    )
    config["max_contract_candidates"] = _bounded_int(
        config.get("max_contract_candidates"), 8, 1, 64,
        rule_id, "max_contract_candidates", warnings,
    )
    config["allow_surrounding_whitespace"] = _as_bool(
        config.get("allow_surrounding_whitespace"), True
    )
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "observe")) or "observe"


def _normalize_refusal_leakage_detector(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize bounded internal-boundary refusal candidate checks."""

    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000,
        rule_id, "scan_limit_chars", warnings,
    )
    config["max_relation_gap_chars"] = _bounded_int(
        config.get("max_relation_gap_chars"), 160, 8, 2048,
        rule_id, "max_relation_gap_chars", warnings,
    )
    config["min_evidence_families"] = _bounded_int(
        config.get("min_evidence_families"), 2, 2, 3,
        rule_id, "min_evidence_families", warnings,
    )
    config["ignore_fenced_code"] = _as_bool(
        config.get("ignore_fenced_code"), True
    )
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "observe")) or "observe"


def _normalize_language_drift_detector(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize bounded script-drift risk-throttling parameters."""

    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000,
        rule_id, "scan_limit_chars", warnings,
    )
    config["min_analyzable_chars"] = _bounded_int(
        config.get("min_analyzable_chars"), 80, 8, 10000,
        rule_id, "min_analyzable_chars", warnings,
    )
    config["dominant_script_ratio"] = _bounded_float(
        config.get("dominant_script_ratio"), 0.7, 0.5, 1.0,
        rule_id, "dominant_script_ratio", warnings,
    )
    config["max_baseline_script_ratio"] = _bounded_float(
        config.get("max_baseline_script_ratio"), 0.2, 0.0, 0.5,
        rule_id, "max_baseline_script_ratio", warnings,
    )
    config["min_foreign_script_run_chars"] = _bounded_int(
        config.get("min_foreign_script_run_chars"), 4, 2, 256,
        rule_id, "min_foreign_script_run_chars", warnings,
    )
    config["ignore_fenced_code"] = _as_bool(
        config.get("ignore_fenced_code"), True
    )
    config["ignore_inline_code"] = _as_bool(
        config.get("ignore_inline_code"), True
    )
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "observe")) or "observe"


def _normalize_sensitive_echo_detector(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize automatic Step 1/3 replay with optional source skips."""

    if "source_node_ids" in config:
        warnings.append(
            f"{rule_id}.source_node_ids is obsolete; all eligible Step 1/3 sources are rechecked"
        )
        config.pop("source_node_ids", None)
    skip_ids = _clean_string_list(config.get("skip_source_node_ids", []))
    config["skip_source_node_ids"] = list(dict.fromkeys(skip_ids))
    config["scan_limit_chars"] = _bounded_int(
        config.get("scan_limit_chars"), 12000, 256, 100000,
        rule_id, "scan_limit_chars", warnings,
    )
    config["max_rechecked_sources"] = _bounded_int(
        config.get("max_rechecked_sources"), 4, 1, 32,
        rule_id, "max_rechecked_sources", warnings,
    )
    config["min_rechecked_sources"] = _bounded_int(
        config.get("min_rechecked_sources"), 1, 1,
        int(config["max_rechecked_sources"]),
        rule_id, "min_rechecked_sources", warnings,
    )
    config["max_external_rechecks"] = _bounded_int(
        config.get("max_external_rechecks"), 2, 0, 16,
        rule_id, "max_external_rechecks", warnings,
    )
    config["ignore_fenced_code"] = _as_bool(
        config.get("ignore_fenced_code"), True
    )
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


MESSAGE_FACT_TEMPLATES = {
    "contains_request_user_id",
    "contains_forward",
    "contains_file",
    "contains_image",
    "contains_record",
    "contains_video",
}

MESSAGE_FACT_COMPONENT_TEMPLATES = (
    MESSAGE_FACT_TEMPLATES - {"contains_request_user_id"}
)


def _normalize_message_fact_component(
    rule_id: str, template_key: str, config: dict[str, Any], warnings: list[str]
) -> None:
    """Normalize P2 Step 1 message facts without assigning risk semantics."""

    if template_key == "contains_request_user_id":
        config["user_ids"] = _clean_string_list(config.get("user_ids", []))
        if not config["user_ids"]:
            warnings.append(f"{rule_id}.user_ids is empty; component skipped")


def _bounded_int(
    value: Any, default: int, minimum: int, maximum: int, rule_id: str, key: str, warnings: list[str]
) -> int:
    normalized = _as_int(value, default)
    if normalized < minimum or normalized > maximum:
        warnings.append(f"{rule_id}.{key} is outside {minimum}..{maximum}; fallback to {default}")
        return default
    return normalized


def _bounded_float(
    value: Any, default: float, minimum: float, maximum: float, rule_id: str, key: str, warnings: list[str]
) -> float:
    normalized = _as_float(value, default)
    if normalized < minimum or normalized > maximum:
        warnings.append(f"{rule_id}.{key} is outside {minimum}..{maximum}; fallback to {default}")
        return default
    return normalized


def _normalize_strengthen_prompt(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    target = _as_str(config.get("insertion_target", "temp_user_context")).strip()
    if target not in INSERTION_TARGETS:
        warnings.append(
            f"{rule_id}.insertion_target is invalid; fallback to temp_user_context"
        )
        target = "temp_user_context"
    config["insertion_target"] = target
    config["insertion_text"] = _as_str(config.get("insertion_text", ""))


def _normalize_llm_review(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    config["provider_id"] = _as_str(config.get("provider_id", "")).strip()
    config["timeout_seconds"] = max(
        _as_float(config.get("timeout_seconds", 8), 8.0), 0.0
    )
    config["audit_prompt"] = _as_str(config.get("audit_prompt", "")).strip()
    if not config["audit_prompt"]:
        warnings.append(f"{rule_id}.audit_prompt is empty; rule skipped")
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


def _normalize_rag_judge(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    knowledge_bases = _clean_string_list(config.get("knowledge_bases", []))
    config["knowledge_bases"] = knowledge_bases
    if not knowledge_bases:
        warnings.append(f"{rule_id}.knowledge_bases is empty; rule skipped")
    config["top_k"] = max(_as_int(config.get("top_k", 5), 5), 1)
    config["min_score"] = max(_as_float(config.get("min_score", 0.72), 0.72), 0.0)
    config["timeout_seconds"] = max(
        _as_float(config.get("timeout_seconds", 8), 8.0), 0.0
    )
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


def _validate_cross_references(
    rails: dict[str, NormalizedRail], warnings: list[str]
) -> None:
    rule_index: dict[str, list[NormalizedNode]] = {}
    for rail in rails.values():
        for rule in rail.rules:
            if rule.user_rule_id:
                rule_index.setdefault(rule.user_rule_id, []).append(rule)

    stable_ids = {
        rule.user_rule_id
        for rail in rails.values()
        for rule in rail.rules
        if rule.user_rule_id and rule.valid and rule.enabled
    }
    for rail in rails.values():
        for rule in rail.rules:
            dep_id = _dependency_target(rule.depend_on)
            if dep_id and dep_id not in stable_ids:
                message = (
                    f"{rule.rule_id}.depend_on references unavailable rule "
                    f"{dep_id}: {_reference_problem(dep_id, rule_index)}"
                )
                rule.warnings.append(message)
                rail.warnings.append(message)
                warnings.append(message)
            if rule.template_key != "logic_gate" or not rule.valid or not rule.enabled:
                continue
            inputs = _clean_string_list(rule.config.get("inputs", []))
            if not inputs:
                # Reserved runtime marker used only by the code-owned system
                # fallback OR gate.  ``any([])`` is intentionally false, so
                # its dependent LLM review never runs until a detector exists.
                if bool(rule.config.get("__allow_empty_inputs", False)):
                    continue
                message = f"{rule.rule_id}.inputs is empty; logic gate skipped"
                rule.valid = False
                rule.enabled = False
                rule.warnings.append(message)
                rail.warnings.append(message)
                warnings.append(message)
                continue
            invalid_inputs = rule.config.get("__invalid_logic_inputs", [])
            if invalid_inputs:
                message = (
                    f"{rule.rule_id}.inputs has invalid logic-gate reference(s): "
                    + ", ".join(str(item) for item in invalid_inputs)
                )
                rule.valid = False
                rule.enabled = False
                rule.warnings.append(message)
                rail.warnings.append(message)
                warnings.append(message)
                continue
            unavailable = [
                f"{item} ({_reference_problem(_logic_gate_input_target(item), rule_index)})"
                for item in inputs
                if _logic_gate_input_target(item) not in stable_ids
            ]
            if unavailable:
                message = (
                    f"{rule.rule_id}.inputs references unavailable rule(s): "
                    + ", ".join(unavailable)
                )
                rule.valid = False
                rule.enabled = False
                rule.warnings.append(message)
                rail.warnings.append(message)
                warnings.append(message)


def _reference_problem(
    rule_id: str, rule_index: dict[str, list[NormalizedNode]]
) -> str:
    if not rule_id:
        return "empty rule id"
    candidates = rule_index.get(rule_id, [])
    if not candidates:
        return "rule id was not found in configured rules"
    return "; ".join(_rule_availability_problem(rule) for rule in candidates)


def _rule_availability_problem(rule: NormalizedNode) -> str:
    state = []
    if not rule.enabled:
        state.append("disabled")
    if not rule.valid:
        state.append("invalid")
    if not state:
        state.append("unavailable")
    detail = f"{rule.rail}.{rule.rule_id} is {'/'.join(state)}"
    if rule.warnings:
        detail += f" ({rule.warnings[-1]})"
    return detail


def _normalize_fallback_policy_settings(
    raw_settings: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    """Normalize the only active system-wide guardrail settings in P1."""

    settings = {
        "max_text_chars": max(_as_int(raw_settings.get("max_text_chars"), 6000), 0),
        "max_retries": max(_as_int(raw_settings.get("max_retries"), 0), 0),
        "default_llm_provider": _as_str(raw_settings.get("default_llm_provider", "")).strip(),
        "enable_llm_review_in_fallback_policy": _as_bool(
            raw_settings.get("enable_llm_review_in_fallback_policy"), False
        ),
        "enable_output_llm_review_in_fallback_policy": _as_bool(
            raw_settings.get("enable_output_llm_review_in_fallback_policy"), False
        ),
        "enable_fallback_input_checks": _as_bool(
            raw_settings.get("enable_fallback_input_checks"), True
        ),
        "enable_fallback_output_checks": _as_bool(
            raw_settings.get("enable_fallback_output_checks"), True
        ),
        "default_action_on_hit": _as_str(
            raw_settings.get("default_action_on_hit", "block")
        ),
        "default_action_on_error": _as_str(
            raw_settings.get("default_action_on_error", "discard")
        ).strip(),
        "reply_placeholder_on_block": _as_bool(
            raw_settings.get("reply_placeholder_on_block"), True
        ),
        "block_message": _as_str(
            raw_settings.get("block_message", DEFAULT_REQUEST_BLOCK_MESSAGE)
        ),
    }


    if settings["default_action_on_hit"] not in {"observe", "block"}:
        warnings.append(
            "fallback_policy_settings.default_action_on_hit is invalid; fallback to block"
        )
        settings["default_action_on_hit"] = "block"
    if settings["default_action_on_error"] not in DEFAULT_ERROR_ACTIONS:
        warnings.append(
            "fallback_policy_settings.default_action_on_error is invalid; fallback to discard"
        )
        settings["default_action_on_error"] = "discard"
    legacy_switches = [
        key for key in LEGACY_FALLBACK_DETECTOR_SWITCHES if key in raw_settings
    ]
    if legacy_switches:
        warnings.append(
            "per-detector fallback switches are deprecated and ignored; use "
            "enable_fallback_input_checks or enable_fallback_output_checks"
        )
    return settings


def _normalize_system_constants(raw_constants: Any, warnings: list[str]) -> dict[str, str]:
    """Accept the global static-text table shared by every policy snapshot."""

    if raw_constants is None:
        return {}
    if not isinstance(raw_constants, dict):
        warnings.append("system_constants is not an object; no constants loaded")
        return {}

    constants: dict[str, str] = {}
    for name, value in raw_constants.items():
        if not isinstance(name, str) or SYSTEM_CONSTANT_NAME_PATTERN.fullmatch(name) is None:
            warnings.append(
                f"system_constants.{name!r} has an invalid name; entry skipped"
            )
            continue
        if not isinstance(value, str):
            warnings.append(
                f"system_constants.{name} must be a string; entry skipped"
            )
            continue
        constants[name] = value
    return constants


def _normalize_debug_settings(
    raw_settings: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    """Normalize P1 diagnostic switches without starting a stats service."""

    stats_max_records = _as_int(raw_settings.get("stats_max_records"), 200)
    if stats_max_records < 1:
        warnings.append(
            "debug_settings.stats_max_records must be positive; fallback to 200"
        )
        stats_max_records = 200
    return {
        "enable_stats": _as_bool(raw_settings.get("enable_stats"), True),
        "stats_max_records": stats_max_records,
        "logging": _as_bool(raw_settings.get("logging"), False),
    }


def _rail_defaults(
    rail_name: str, fallback_policy_settings: dict[str, Any]
) -> dict[str, Any]:
    settings = {"enabled": True}
    if rail_name in {"input_rail", "request_rail", "output_rail"}:
        settings.update(
            {
                "max_text_chars": fallback_policy_settings["max_text_chars"],
                "default_llm_provider": fallback_policy_settings["default_llm_provider"],
                "default_action_on_hit": fallback_policy_settings["default_action_on_hit"],
                "default_action_on_error": fallback_policy_settings["default_action_on_error"],
                "block_message": fallback_policy_settings["block_message"],
                # Sanitizers only create NodeSignal payloads.  A policy must
                # explicitly choose a payload as stage output before any host
                # text is changed.
                "output_redirect_template": STAGE_ORIGIN_TEMPLATES[rail_name],
            }
        )
    if rail_name == "output_rail":
        settings["max_retries"] = fallback_policy_settings["max_retries"]
    return settings


def _coerce_rail_settings(
    rail_name: str, settings: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    settings["enabled"] = _as_bool(settings.get("enabled"), True)
    if rail_name == "input_rail":
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        settings["default_llm_provider"] = _as_str(
            settings.get("default_llm_provider", "")
        )
        raw_action = _as_str(settings.get("default_action_on_hit", "block"))
        action = raw_action
        if action not in {"observe", "block"}:
            warnings.append("input_rail.default_action_on_hit is invalid; fallback to block")
            action = "block"
        settings["default_action_on_hit"] = action
        error_action = _as_str(
            settings.get("default_action_on_error", "discard")
        ).strip()
        if error_action not in DEFAULT_ERROR_ACTIONS:
            warnings.append(
                "input_rail.default_action_on_error is invalid; fallback to discard"
            )
            error_action = "discard"
        settings["default_action_on_error"] = error_action
        settings["block_message"] = _as_str(settings.get("block_message", ""))
        settings["output_redirect_template"] = _as_str(
            settings.get("output_redirect_template", STAGE_ORIGIN_TEMPLATES[rail_name])
        ) or STAGE_ORIGIN_TEMPLATES[rail_name]
    elif rail_name == "request_rail":
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        settings["default_llm_provider"] = _as_str(
            settings.get("default_llm_provider", "")
        )
        raw_action = _as_str(settings.get("default_action_on_hit", "observe"))
        action = raw_action
        if action not in {"observe", "block"}:
            warnings.append("request_rail.default_action_on_hit is invalid; fallback to observe")
            action = "observe"
        settings["default_action_on_hit"] = action
        error_action = _as_str(
            settings.get("default_action_on_error", "discard")
        ).strip()
        if error_action not in DEFAULT_ERROR_ACTIONS:
            warnings.append(
                "request_rail.default_action_on_error is invalid; fallback to discard"
            )
            error_action = "discard"
        settings["default_action_on_error"] = error_action
        settings["block_message"] = _as_str(settings.get("block_message", ""))
        settings["output_redirect_template"] = _as_str(
            settings.get("output_redirect_template", STAGE_ORIGIN_TEMPLATES[rail_name])
        ) or STAGE_ORIGIN_TEMPLATES[rail_name]
    elif rail_name == "output_rail":
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        settings["default_llm_provider"] = _as_str(
            settings.get("default_llm_provider", "")
        )
        settings["max_retries"] = max(_as_int(settings.get("max_retries"), 0), 0)
        raw_action = _as_str(settings.get("default_action_on_hit", "block"))
        action = raw_action
        if action not in {"block", "retry_generation"}:
            warnings.append("output_rail.default_action_on_hit is invalid; fallback to block")
            action = "block"
        settings["default_action_on_hit"] = action
        error_action = _as_str(
            settings.get("default_action_on_error", "discard")
        ).strip()
        if error_action not in DEFAULT_ERROR_ACTIONS:
            warnings.append(
                "output_rail.default_action_on_error is invalid; fallback to discard"
            )
            error_action = "discard"
        settings["default_action_on_error"] = error_action
        settings["block_message"] = _as_str(settings.get("block_message", ""))
        settings["output_redirect_template"] = _as_str(
            settings.get("output_redirect_template", STAGE_ORIGIN_TEMPLATES[rail_name])
        ) or STAGE_ORIGIN_TEMPLATES[rail_name]
    return settings


def _dependency_target(value: str) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped[0] in {"!", "?", "~"}:
        return stripped[1:].strip()
    return stripped


def _logic_gate_input_target(value: str) -> str:
    """Extract the source node ID from a validated logic-gate input."""

    stripped = value.strip()
    if stripped[:1] in {"!", "?", "~"}:
        stripped = stripped[1:]
    if stripped.endswith("?"):
        stripped = stripped[:-1]
    return stripped.partition(".")[0]


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    getter = getattr(config, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except TypeError:
            return getter(key)
    return default


def _merge_defaults(defaults: dict[str, Any], value: Any) -> dict[str, Any]:
    merged = dict(defaults)
    merged.update(_as_dict(value))
    return merged


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _as_str(item).strip()
        if text:
            result.append(text)
    return result
