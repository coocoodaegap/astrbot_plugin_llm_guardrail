"""P1 rule library, policy library, and legacy rule-list compiler."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

try:
    from .config import RAIL_NAMES, SUPPORTED_TEMPLATES
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import RAIL_NAMES, SUPPORTED_TEMPLATES


RULE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
RULE_METADATA_KEYS = {
    "__template_key",
    "template_key",
    "rule_id",
    "enabled",
    "depend_on",
    "priority",
    "action_on_hit",
    "action_on_error",
}


@dataclass(frozen=True)
class RuleDefinition:
    """Reusable rule content without rail or policy-specific behavior."""

    rule_id: str
    template_key: str
    template_config: dict[str, Any] = field(default_factory=dict)
    default_priority: int = 100
    default_action_on_hit: str = "default"
    default_action_on_error: str = "default"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "template_key": self.template_key,
            "description": self.description,
            "template_config": copy.deepcopy(self.template_config),
            "default_priority": self.default_priority,
            "default_action_on_hit": self.default_action_on_hit,
            "default_action_on_error": self.default_action_on_error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RuleDefinition":
        return cls(
            rule_id=str(value.get("rule_id") or "").strip(),
            template_key=str(value.get("template_key") or "").strip(),
            description=str(value.get("description") or "").strip(),
            template_config=_copy_dict(value.get("template_config")),
            default_priority=_as_int(value.get("default_priority"), 100),
            default_action_on_hit=str(value.get("default_action_on_hit") or "default"),
            default_action_on_error=str(value.get("default_action_on_error") or "default"),
        )


@dataclass(frozen=True)
class PolicyRuleBinding:
    """One rule's rail placement and policy-level overrides."""

    rule_id: str
    rail: str
    enabled: bool = True
    priority: int | None = None
    action_on_hit: str | None = None
    action_on_error: str | None = None
    depend_on: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rail": self.rail,
            "enabled": self.enabled,
            "priority": self.priority,
            "action_on_hit": self.action_on_hit,
            "action_on_error": self.action_on_error,
            "depend_on": self.depend_on,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyRuleBinding":
        return cls(
            rule_id=str(value.get("rule_id") or "").strip(),
            rail=str(value.get("rail") or "").strip(),
            enabled=bool(value.get("enabled", True)),
            priority=_as_optional_int(value.get("priority")),
            action_on_hit=_as_optional_string(value.get("action_on_hit")),
            action_on_error=_as_optional_string(value.get("action_on_error")),
            depend_on=str(value.get("depend_on") or "").strip(),
        )


@dataclass(frozen=True)
class PolicyDefinition:
    """A concrete rail execution policy made from reusable rule definitions."""

    policy_id: str
    name: str
    description: str = ""
    bindings: tuple[PolicyRuleBinding, ...] = ()
    session_scope: dict[str, Any] = field(default_factory=dict)
    builtin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "bindings": [binding.to_dict() for binding in self.bindings],
            "session_scope": copy.deepcopy(self.session_scope),
            "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyDefinition":
        bindings = value.get("bindings")
        return cls(
            policy_id=str(value.get("policy_id") or "").strip(),
            name=str(value.get("name") or "").strip(),
            description=str(value.get("description") or ""),
            bindings=tuple(
                PolicyRuleBinding.from_dict(item)
                for item in bindings
                if isinstance(item, Mapping)
            )
            if isinstance(bindings, list)
            else (),
            session_scope=_copy_dict(value.get("session_scope")),
            builtin=bool(value.get("builtin", False)),
        )


@dataclass(frozen=True)
class LibraryValidation:
    fatal_errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.fatal_errors


@dataclass(frozen=True)
class PolicyLibrary:
    """Serializable P1 rule/policy storage model."""

    rules: tuple[RuleDefinition, ...] = ()
    policies: tuple[PolicyDefinition, ...] = ()
    active_policy_id: str = "none"

    @classmethod
    def empty(cls) -> "PolicyLibrary":
        return cls(
            policies=(
                PolicyDefinition(
                    policy_id="none",
                    name="None",
                    description="不启用任何 Guardrail 规则。",
                    builtin=True,
                ),
            ),
            active_policy_id="none",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules": [rule.to_dict() for rule in self.rules],
            "policies": [policy.to_dict() for policy in self.policies],
            "active_policy_id": self.active_policy_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyLibrary":
        rules = value.get("rules")
        policies = value.get("policies")
        return cls(
            rules=tuple(
                RuleDefinition.from_dict(item)
                for item in rules
                if isinstance(item, Mapping)
            )
            if isinstance(rules, list)
            else (),
            policies=tuple(
                PolicyDefinition.from_dict(item)
                for item in policies
                if isinstance(item, Mapping)
            )
            if isinstance(policies, list)
            else (),
            active_policy_id=str(value.get("active_policy_id") or "none").strip(),
        )

    def get_policy(self, policy_id: str | None = None) -> PolicyDefinition | None:
        target = str(policy_id or self.active_policy_id).strip()
        return next((policy for policy in self.policies if policy.policy_id == target), None)

    def validate(self) -> LibraryValidation:
        fatal_errors: list[str] = []
        warnings: list[str] = []
        rule_ids: set[str] = set()
        policy_ids: set[str] = set()

        for rule in self.rules:
            if not RULE_ID_PATTERN.fullmatch(rule.rule_id):
                fatal_errors.append(f"invalid rule_id: {rule.rule_id or '(empty)'}")
            elif rule.rule_id in rule_ids:
                fatal_errors.append(f"duplicate rule_id: {rule.rule_id}")
            else:
                rule_ids.add(rule.rule_id)
            if not rule.template_key:
                fatal_errors.append(f"rule {rule.rule_id or '(empty)'} has no template_key")

        for policy in self.policies:
            if not RULE_ID_PATTERN.fullmatch(policy.policy_id):
                fatal_errors.append(f"invalid policy_id: {policy.policy_id or '(empty)'}")
            elif policy.policy_id in policy_ids:
                fatal_errors.append(f"duplicate policy_id: {policy.policy_id}")
            else:
                policy_ids.add(policy.policy_id)
            seen_bindings: set[str] = set()
            for binding in policy.bindings:
                if binding.rule_id not in rule_ids:
                    fatal_errors.append(
                        f"policy {policy.policy_id} references missing rule {binding.rule_id}"
                    )
                if binding.rule_id in seen_bindings:
                    fatal_errors.append(
                        f"policy {policy.policy_id} binds rule {binding.rule_id} more than once"
                    )
                seen_bindings.add(binding.rule_id)
                if binding.rail not in RAIL_NAMES:
                    fatal_errors.append(
                        f"policy {policy.policy_id} uses unknown rail {binding.rail}"
                    )

        for policy in self.policies:
            for binding in policy.bindings:
                rule = next((item for item in self.rules if item.rule_id == binding.rule_id), None)
                if rule and binding.rail in RAIL_NAMES and rule.template_key not in SUPPORTED_TEMPLATES[binding.rail]:
                    warnings.append(
                        f"policy {policy.policy_id} binds {rule.rule_id} to unsupported "
                        f"template {rule.template_key} in {binding.rail}"
                    )

        if self.active_policy_id not in policy_ids:
            fatal_errors.append(f"active policy does not exist: {self.active_policy_id}")
        return LibraryValidation(tuple(fatal_errors), tuple(warnings))


def compile_policy_to_legacy_config(
    base_config: Mapping[str, Any] | None,
    library: PolicyLibrary,
    policy_id: str | None = None,
) -> tuple[dict[str, Any], LibraryValidation]:
    """Compile P1 libraries to the existing ``_conf_schema`` rule-list shape."""

    validation = library.validate()
    if not validation.valid:
        return _copy_dict(base_config), validation
    policy = library.get_policy(policy_id)
    if policy is None:
        return _copy_dict(base_config), LibraryValidation(
            fatal_errors=(f"policy does not exist: {policy_id}",),
            warnings=validation.warnings,
        )

    compiled = _copy_dict(base_config)
    rule_by_id = {rule.rule_id: rule for rule in library.rules}
    for rail_name in RAIL_NAMES:
        rail = _copy_dict(compiled.get(rail_name))
        rail["rule_list"] = []
        compiled[rail_name] = rail
    if policy.session_scope:
        session_control = _copy_dict(compiled.get("session_control"))
        session_control.update(copy.deepcopy(policy.session_scope))
        compiled["session_control"] = session_control

    for binding in policy.bindings:
        rule = rule_by_id[binding.rule_id]
        compiled[binding.rail]["rule_list"].append(
            _compile_binding(rule, binding)
        )
    return compiled, validation


def import_legacy_rule_list(raw_config: Mapping[str, Any] | None) -> tuple[PolicyLibrary, list[str]]:
    """Create a read-only import candidate from the existing per-rail rule lists."""

    source = _copy_dict(raw_config)
    rules: list[RuleDefinition] = []
    bindings: list[PolicyRuleBinding] = []
    diagnostics: list[str] = []
    seen: set[str] = set()
    for rail_name in RAIL_NAMES:
        rail = source.get(rail_name)
        raw_rules = rail.get("rule_list") if isinstance(rail, Mapping) else []
        if not isinstance(raw_rules, list):
            continue
        for index, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, Mapping):
                diagnostics.append(f"{rail_name}[{index}] is not an object; skipped")
                continue
            rule_id = str(raw_rule.get("rule_id") or "").strip()
            template_key = str(raw_rule.get("__template_key") or raw_rule.get("template_key") or "").strip()
            if not rule_id or not RULE_ID_PATTERN.fullmatch(rule_id):
                diagnostics.append(f"{rail_name}[{index}] has no usable stable rule_id; skipped")
                continue
            if rule_id in seen:
                diagnostics.append(f"duplicate legacy rule_id {rule_id}; later rule skipped")
                continue
            seen.add(rule_id)
            template_config = {
                key: copy.deepcopy(value)
                for key, value in raw_rule.items()
                if key not in RULE_METADATA_KEYS and not str(key).startswith("_")
            }
            rules.append(
                RuleDefinition(
                    rule_id=rule_id,
                    template_key=template_key,
                    template_config=template_config,
                    default_priority=_as_int(raw_rule.get("priority"), 100),
                    default_action_on_hit=str(raw_rule.get("action_on_hit") or "default"),
                    default_action_on_error=str(raw_rule.get("action_on_error") or "default"),
                )
            )
            bindings.append(
                PolicyRuleBinding(
                    rule_id=rule_id,
                    rail=rail_name,
                    enabled=bool(raw_rule.get("enabled", True)),
                    priority=_as_optional_int(raw_rule.get("priority")),
                    action_on_hit=_as_optional_string(raw_rule.get("action_on_hit")),
                    action_on_error=_as_optional_string(raw_rule.get("action_on_error")),
                    depend_on=str(raw_rule.get("depend_on") or "").strip(),
                )
            )
    legacy_policy = PolicyDefinition(
        policy_id="legacy_import",
        name="Legacy Import",
        description="从旧 _conf_schema rule_list 导入的只读候选策略。",
        bindings=tuple(bindings),
    )
    return PolicyLibrary(
        rules=tuple(rules),
        policies=(PolicyLibrary.empty().policies[0], legacy_policy),
        active_policy_id="legacy_import" if bindings else "none",
    ), diagnostics


def _compile_binding(rule: RuleDefinition, binding: PolicyRuleBinding) -> dict[str, Any]:
    item = copy.deepcopy(rule.template_config)
    item.update(
        {
            "__template_key": rule.template_key,
            "rule_id": rule.rule_id,
            "enabled": binding.enabled,
            "priority": rule.default_priority if binding.priority is None else binding.priority,
            "depend_on": binding.depend_on,
            "action_on_hit": (
                rule.default_action_on_hit
                if binding.action_on_hit is None
                else binding.action_on_hit
            ),
            "action_on_error": (
                rule.default_action_on_error
                if binding.action_on_error is None
                else binding.action_on_error
            ),
        }
    )
    return item


def _copy_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    return {}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
