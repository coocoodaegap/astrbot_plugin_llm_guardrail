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

SUPPORTED_TEMPLATES: dict[str, set[str]] = {
    "input_rail": {
        "plain_keywords",
        "regex_pattern",
        "logic_gate",
        "rag_judge",
        "llm_review",
    },
    "request_rail": {
        "plain_keywords",
        "regex_pattern",
        "logic_gate",
        "rag_judge",
        "llm_review",
    },
    "prompt_rail": {"replace_input", "strengthen_prompt", "logic_gate"},
    "routing_rail": {"route_policy", "logic_gate"},
    "output_rail": {
        "plain_keywords",
        "regex_pattern",
        "logic_gate",
        "rag_judge",
        "llm_review",
    },
}

INPUT_ACTIONS = {
    "default",
    "observe",
    "retry_generation",
    "block",
    "sanitize",
    "block_input",
    "sanitize_input",
}
OUTPUT_ACTIONS = {
    "default",
    "observe",
    "retry_generation",
    "block",
    "sanitize",
    "block_output",
    "sanitize_output",
}
ERROR_ACTIONS = {"default", "discard", "record", "retry_generation", "block"}
DEFAULT_ERROR_ACTIONS = {"discard", "record", "block"}
LOGIC_GATES = {"all", "any"}
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
class NormalizedRule:
    rail: str
    template_key: str
    index: int
    enabled: bool
    rule_id: str
    user_rule_id: str
    anonymous: bool
    depend_on: str
    priority: int
    config: dict[str, Any]
    valid: bool = True
    warnings: list[str] = field(default_factory=list)


@dataclass
class NormalizedRail:
    rail: str
    enabled: bool
    settings: dict[str, Any]
    rules: list[NormalizedRule] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class NormalizedConfig:
    schema_version: str
    fallback_policy_settings: dict[str, Any]
    session_control: dict[str, Any]
    debug_settings: dict[str, Any]
    rails: dict[str, NormalizedRail]
    warnings: list[str] = field(default_factory=list)


def normalize_config(raw_config: Any) -> NormalizedConfig:
    """Normalize AstrBotConfig or a dict into runtime-only dataclasses."""

    warnings: list[str] = []
    schema_version = "0.2.0"
    fallback_policy_settings = _normalize_fallback_policy_settings(
        _as_dict(_config_get(raw_config, "fallback_policy_settings", {})),
        warnings,
    )

    raw_session_control = _as_dict(_config_get(raw_config, "session_control", {}))
    session_control = _normalize_session_control(
        raw_session_control,
        warnings=warnings,
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
        session_control=session_control,
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

    settings = _rail_defaults(rail_name, fallback_policy_settings)

    raw_rules = rail_dict.get("rule_list", [])
    if raw_rules is None:
        raw_rules = []
    if not isinstance(raw_rules, list):
        warnings.append(f"{rail_name}.rule_list is not a list; no rules loaded")
        raw_rules = []

    rules: list[NormalizedRule] = []
    for index, raw_rule in enumerate(raw_rules):
        rule = _normalize_rule(rail_name, index, raw_rule, seen_rule_ids)
        rules.append(rule)
        warnings.extend(rule.warnings)

    return NormalizedRail(
        rail=rail_name,
        enabled=_as_bool(settings.get("enabled"), True),
        settings=settings,
        rules=rules,
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


def _normalize_rule(
    rail_name: str, index: int, raw_rule: Any, seen_rule_ids: set[str]
) -> NormalizedRule:
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
    elif template_key == "replace_input":
        config["replacement_text"] = _as_str(config.get("replacement_text", ""))
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
    }:
        raw_action = raw_action_on_hit
        action = _normalize_action_alias(raw_action)
        config["action_on_hit"] = action
        if action == "sanitize" and template_key not in {"plain_keywords", "regex_pattern"}:
            warnings.append(
                f"{rule_id}.action_on_hit=sanitize is only supported by plain_keywords and regex_pattern; fallback to default"
            )
            config["action_on_hit"] = "default"
        if rail_name in {"input_rail", "request_rail"} and action not in INPUT_ACTIONS:
            warnings.append(f"{rule_id}.action_on_hit is invalid; fallback to default")
            config["action_on_hit"] = "default"
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

    return NormalizedRule(
        rail=rail_name,
        template_key=template_key,
        index=index,
        enabled=enabled,
        rule_id=rule_id,
        user_rule_id=user_rule_id,
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
    config["action_on_hit"] = _normalize_action_alias(
        _as_str(config.get("action_on_hit", "default")) or "default"
    )


def _normalize_regex_pattern(
    rule_id: str, config: dict[str, Any], warnings: list[str]
) -> None:
    pattern = _as_str(config.get("pattern", ""))
    config["pattern"] = pattern
    config["sanitizer"] = _as_str(config.get("sanitizer", ""))
    config["action_on_hit"] = _normalize_action_alias(
        _as_str(config.get("action_on_hit", "default")) or "default"
    )
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
    config["inputs"] = _clean_string_list(config.get("inputs", []))
    config["invert"] = _as_bool(config.get("invert", False), False)
    config["action_on_hit"] = _normalize_action_alias(
        _as_str(config.get("action_on_hit", "default")) or "default"
    )


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
    config["action_on_hit"] = _normalize_action_alias(
        _as_str(config.get("action_on_hit", "default")) or "default"
    )


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
    config["action_on_hit"] = _normalize_action_alias(
        _as_str(config.get("action_on_hit", "default")) or "default"
    )


def _validate_cross_references(
    rails: dict[str, NormalizedRail], warnings: list[str]
) -> None:
    rule_index: dict[str, list[NormalizedRule]] = {}
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
                message = f"{rule.rule_id}.inputs is empty; logic gate skipped"
                rule.valid = False
                rule.enabled = False
                rule.warnings.append(message)
                rail.warnings.append(message)
                warnings.append(message)
                continue
            unavailable = [
                f"{item} ({_reference_problem(_dependency_target(item), rule_index)})"
                for item in inputs
                if _dependency_target(item) not in stable_ids
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
    rule_id: str, rule_index: dict[str, list[NormalizedRule]]
) -> str:
    if not rule_id:
        return "empty rule id"
    candidates = rule_index.get(rule_id, [])
    if not candidates:
        return "rule id was not found in configured rules"
    return "; ".join(_rule_availability_problem(rule) for rule in candidates)


def _rule_availability_problem(rule: NormalizedRule) -> str:
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
        "default_llm_provider": _as_str(raw_settings.get("default_llm_provider", "")).strip(),
        "enable_llm_review_in_fallback_policy": _as_bool(
            raw_settings.get("enable_llm_review_in_fallback_policy"), False
        ),
        "default_action_on_hit": _normalize_action_alias(
            _as_str(raw_settings.get("default_action_on_hit", "block"))
        ),
        "default_action_on_error": _as_str(
            raw_settings.get("default_action_on_error", "discard")
        ).strip(),
        "reply_placeholder_on_block": _as_bool(
            raw_settings.get("reply_placeholder_on_block"), True
        ),
        "block_message": _as_str(raw_settings.get("block_message", "")),
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
    for key in (
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
    ):
        settings[key] = _as_bool(raw_settings.get(key), True)
    return settings


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
            }
        )
    if rail_name == "output_rail":
        settings["max_retries"] = 0
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
        action = _normalize_action_alias(raw_action)
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
    elif rail_name == "request_rail":
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        settings["default_llm_provider"] = _as_str(
            settings.get("default_llm_provider", "")
        )
        raw_action = _as_str(settings.get("default_action_on_hit", "observe"))
        action = _normalize_action_alias(raw_action)
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
    elif rail_name == "output_rail":
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        settings["default_llm_provider"] = _as_str(
            settings.get("default_llm_provider", "")
        )
        settings["max_retries"] = max(_as_int(settings.get("max_retries"), 0), 0)
        raw_action = _as_str(settings.get("default_action_on_hit", "block"))
        action = _normalize_action_alias(raw_action)
        if action != "block":
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
    return settings


def _normalize_action_alias(action: str) -> str:
    if action in {"block_input", "block_output"}:
        return "block"
    if action in {"sanitize_input", "sanitize_output"}:
        return "sanitize"
    return action


def _dependency_target(value: str) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped[0] in {"!", "?"}:
        return stripped[1:].strip()
    return stripped


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
