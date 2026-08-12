"""Configuration normalization for the LLM Guardrail plugin."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


RAIL_NAMES = ("input_rail", "prompt_rail", "routing_rail", "output_rail")

SUPPORTED_TEMPLATES: dict[str, set[str]] = {
    "input_rail": {"plain_keywords", "regex_pattern", "logic_gate"},
    "prompt_rail": {"replace_input", "strengthen_prompt", "logic_gate"},
    "routing_rail": {"route_policy", "logic_gate"},
    "output_rail": {"plain_keywords", "regex_pattern", "logic_gate"},
}

INPUT_ACTIONS = {"default", "observe", "block_input", "sanitize_input"}
OUTPUT_ACTIONS = {
    "default",
    "observe",
    "retry_generation",
    "block_output",
    "sanitize_output",
}
LOGIC_GATES = {"all", "any"}
INSERTION_TARGETS = {
    "system_prefix",
    "system_suffix",
    "temp_user_context",
    "input_wrapper",
}


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
    enabled: bool
    global_default_settings: dict[str, Any]
    session_control: dict[str, Any]
    rails: dict[str, NormalizedRail]
    warnings: list[str] = field(default_factory=list)


def normalize_config(raw_config: Any) -> NormalizedConfig:
    """Normalize AstrBotConfig or a dict into runtime-only dataclasses."""

    warnings: list[str] = []
    schema_version = _as_str(_config_get(raw_config, "schema_version", "0.1.0"))
    enabled = _as_bool(_config_get(raw_config, "enabled", True), True)

    global_default_settings = _merge_defaults(
        {
            "group_only": False,
            "default_llm_provider": "",
            "reply_placeholder_on_block": True,
            "enable_stats": True,
            "stats_max_records": 200,
            "debug": False,
        },
        _config_get(raw_config, "global_default_settings", {}),
    )
    global_default_settings["group_only"] = _as_bool(
        global_default_settings.get("group_only"), False
    )
    global_default_settings["reply_placeholder_on_block"] = _as_bool(
        global_default_settings.get("reply_placeholder_on_block"), True
    )
    global_default_settings["enable_stats"] = _as_bool(
        global_default_settings.get("enable_stats"), True
    )
    global_default_settings["stats_max_records"] = _as_int(
        global_default_settings.get("stats_max_records"), 200
    )
    global_default_settings["debug"] = _as_bool(
        global_default_settings.get("debug"), False
    )
    global_default_settings["default_llm_provider"] = _as_str(
        global_default_settings.get("default_llm_provider")
    )

    session_control = _merge_defaults(
        {"filter_type": "blacklist", "whitelist": [], "blacklist": []},
        _config_get(raw_config, "session_control", {}),
    )
    if session_control.get("filter_type") not in ("blacklist", "whitelist"):
        warnings.append("session_control.filter_type is invalid; fallback to blacklist")
        session_control["filter_type"] = "blacklist"
    session_control["whitelist"] = _clean_string_list(
        session_control.get("whitelist", [])
    )
    session_control["blacklist"] = _clean_string_list(
        session_control.get("blacklist", [])
    )

    rails: dict[str, NormalizedRail] = {}
    seen_rule_ids: set[str] = set()

    for rail_name in RAIL_NAMES:
        rail = _normalize_rail(
            rail_name=rail_name,
            raw_rail=_config_get(raw_config, rail_name, {}),
            seen_rule_ids=seen_rule_ids,
        )
        rails[rail_name] = rail
        warnings.extend(rail.warnings)

    _validate_cross_references(rails, warnings)

    return NormalizedConfig(
        schema_version=schema_version,
        enabled=enabled,
        global_default_settings=global_default_settings,
        session_control=session_control,
        rails=rails,
        warnings=warnings,
    )


def _normalize_rail(
    rail_name: str, raw_rail: Any, seen_rule_ids: set[str]
) -> NormalizedRail:
    warnings: list[str] = []
    rail_dict = _as_dict(raw_rail)
    if not isinstance(raw_rail, dict) and raw_rail is not None:
        warnings.append(f"{rail_name} is not an object; fallback to defaults")

    settings = _rail_defaults(rail_name)
    settings.update(
        {key: value for key, value in rail_dict.items() if key != "rule_list"}
    )
    settings = _coerce_rail_settings(rail_name, settings, warnings)

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

    if template_key in {"plain_keywords", "regex_pattern", "logic_gate"}:
        action = _as_str(config.get("action_on_hit", "default")) or "default"
        if rail_name == "input_rail" and action not in INPUT_ACTIONS:
            warnings.append(f"{rule_id}.action_on_hit is invalid; fallback to default")
            config["action_on_hit"] = "default"
        elif rail_name == "output_rail":
            if action == "retry_generation":
                valid = False
                enabled = False
                warnings.append(
                    f"{rule_id}.action_on_hit=retry_generation is unsupported in P0; skipped"
                )
            elif action not in OUTPUT_ACTIONS:
                warnings.append(
                    f"{rule_id}.action_on_hit is invalid; fallback to default"
                )
                config["action_on_hit"] = "default"
        elif rail_name in {"prompt_rail", "routing_rail"}:
            config["action_on_hit"] = "observe"

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
    config["inputs"] = _clean_string_list(config.get("inputs", []))
    config["invert"] = _as_bool(config.get("invert", False), False)
    config["action_on_hit"] = _as_str(config.get("action_on_hit", "default")) or "default"


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


def _validate_cross_references(
    rails: dict[str, NormalizedRail], warnings: list[str]
) -> None:
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
                message = f"{rule.rule_id}.depend_on references missing rule {dep_id}"
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
            missing = [item for item in inputs if item not in stable_ids]
            if missing:
                message = (
                    f"{rule.rule_id}.inputs references missing rule(s): "
                    + ", ".join(missing)
                )
                rule.valid = False
                rule.enabled = False
                rule.warnings.append(message)
                rail.warnings.append(message)
                warnings.append(message)


def _rail_defaults(rail_name: str) -> dict[str, Any]:
    defaults: dict[str, dict[str, Any]] = {
        "input_rail": {
            "enabled": True,
            "check_original_only": True,
            "max_text_chars": 6000,
            "default_action_on_hit": "block_input",
            "block_message": "",
        },
        "prompt_rail": {"enabled": True},
        "routing_rail": {"enabled": True},
        "output_rail": {
            "enabled": True,
            "max_text_chars": 6000,
            "default_action_on_hit": "block_output",
            "max_retries": 0,
            "block_message": "",
        },
    }
    return dict(defaults[rail_name])


def _coerce_rail_settings(
    rail_name: str, settings: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    settings["enabled"] = _as_bool(settings.get("enabled"), True)
    if rail_name == "input_rail":
        settings["check_original_only"] = _as_bool(
            settings.get("check_original_only"), True
        )
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        action = _as_str(settings.get("default_action_on_hit", "block_input"))
        if action not in {"observe", "block_input"}:
            warnings.append("input_rail.default_action_on_hit is invalid; fallback to block_input")
            action = "block_input"
        settings["default_action_on_hit"] = action
        settings["block_message"] = _as_str(settings.get("block_message", ""))
    elif rail_name == "output_rail":
        settings["max_text_chars"] = max(_as_int(settings.get("max_text_chars"), 6000), 0)
        settings["max_retries"] = max(_as_int(settings.get("max_retries"), 0), 0)
        action = _as_str(settings.get("default_action_on_hit", "block_output"))
        if action != "block_output":
            warnings.append("output_rail.default_action_on_hit is invalid; fallback to block_output")
            action = "block_output"
        settings["default_action_on_hit"] = action
        settings["block_message"] = _as_str(settings.get("block_message", ""))
    return settings


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
