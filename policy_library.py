"""P1 rule library, policy library, and runtime configuration compiler."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

try:
    from .config import (
        COMPONENT_TEMPLATES,
        RAIL_NAMES,
        RULE_TEMPLATES,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import COMPONENT_TEMPLATES, RAIL_NAMES, RULE_TEMPLATES


RULE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
POLICY_ID_PATTERN = re.compile(r"^(?:_default|[a-z][a-z0-9_]{0,63})$")
DEFAULT_POLICY_ID = "_default"
STEP_BY_RAIL = {
    "input_rail": 1,
    "routing_rail": 2,
    "request_rail": 3,
    "prompt_rail": 4,
    "output_rail": 5,
}
KNOWN_RULE_TEMPLATE_KEYS = frozenset().union(*RULE_TEMPLATES.values())
KNOWN_COMPONENT_TYPES = frozenset().union(*COMPONENT_TEMPLATES.values())


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
            default_action_on_hit=str(
                value.get("default_action_on_hit") or "default"
            ).strip(),
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
class PolicyComponent:
    """A policy-local executable graph component.

    Components deliberately carry their own configuration and lifecycle.  They
    are serialized only inside a policy and are never exposed through the rule
    library, which keeps graph primitives such as logic gates from becoming
    accidental reusable business rules.
    """

    component_id: str
    component_type: str
    rail: str
    enabled: bool = True
    priority: int = 100
    action_on_hit: str = "default"
    action_on_error: str = "default"
    depend_on: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "rail": self.rail,
            "enabled": self.enabled,
            "priority": self.priority,
            "action_on_hit": self.action_on_hit,
            "action_on_error": self.action_on_error,
            "depend_on": self.depend_on,
            "config": copy.deepcopy(self.config),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyComponent":
        return cls(
            component_id=str(value.get("component_id") or "").strip(),
            component_type=str(value.get("component_type") or "").strip(),
            rail=str(value.get("rail") or "").strip(),
            enabled=bool(value.get("enabled", True)),
            priority=_as_int(value.get("priority"), 100),
            action_on_hit=str(value.get("action_on_hit") or "default").strip(),
            action_on_error=str(value.get("action_on_error") or "default").strip(),
            depend_on=str(value.get("depend_on") or "").strip(),
            config=_copy_dict(value.get("config")),
        )


@dataclass(frozen=True)
class PolicyDefinition:
    """A concrete rail execution policy made from reusable rule definitions."""

    policy_id: str
    name: str
    description: str = ""
    bindings: tuple[PolicyRuleBinding, ...] = ()
    components: tuple[PolicyComponent, ...] = ()
    node_order: tuple[str, ...] = ()
    umo_list: tuple[str, ...] = ()
    rail_settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    session_scope: dict[str, Any] = field(default_factory=dict)
    builtin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "bindings": [binding.to_dict() for binding in self.bindings],
            "components": [component.to_dict() for component in self.components],
            "node_order": list(self.node_order),
            "umo_list": list(self.umo_list),
            "rail_settings": copy.deepcopy(self.rail_settings),
            "session_scope": copy.deepcopy(self.session_scope),
            "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyDefinition":
        bindings = value.get("bindings")
        components = value.get("components")
        node_order = value.get("node_order")
        umo_list = value.get("umo_list")
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
            components=tuple(
                PolicyComponent.from_dict(item)
                for item in components
                if isinstance(item, Mapping)
            )
            if isinstance(components, list)
            else (),
            node_order=tuple(_clean_string_list(node_order)),
            umo_list=tuple(_clean_string_list(umo_list)),
            rail_settings=_copy_nested_dict(value.get("rail_settings")),
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
    active_policy_id: str = DEFAULT_POLICY_ID

    @classmethod
    def empty(cls) -> "PolicyLibrary":
        return cls(
            policies=(cls.default_policy(),),
            active_policy_id=DEFAULT_POLICY_ID,
        )

    @staticmethod
    def default_policy() -> PolicyDefinition:
        return PolicyDefinition(
            policy_id=DEFAULT_POLICY_ID,
            name="Default",
            description="默认策略，暂不绑定 Guardrail 规则。",
            builtin=True,
        )

    def with_default_policy(self) -> "PolicyLibrary":
        policies = self.policies
        if not any(policy.policy_id == DEFAULT_POLICY_ID for policy in policies):
            policies = (*policies, self.default_policy())
        active_policy_id = self.active_policy_id
        if not any(policy.policy_id == active_policy_id for policy in policies):
            active_policy_id = DEFAULT_POLICY_ID
        library = PolicyLibrary(
            rules=self.rules,
            policies=policies,
            active_policy_id=active_policy_id,
        )
        if active_policy_id not in library._usable_policy_ids():
            return PolicyLibrary(
                rules=library.rules,
                policies=library.policies,
                active_policy_id=DEFAULT_POLICY_ID,
            )
        return library

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
        parsed_rules = [
            RuleDefinition.from_dict(item)
            for item in rules
            if isinstance(item, Mapping)
        ] if isinstance(rules, list) else []
        parsed_policies = [
            PolicyDefinition.from_dict(item)
            for item in policies
            if isinstance(item, Mapping)
        ] if isinstance(policies, list) else []
        active_policy_id = str(value.get("active_policy_id") or DEFAULT_POLICY_ID).strip()
        return cls(
            rules=tuple(parsed_rules),
            policies=tuple(parsed_policies),
            active_policy_id=active_policy_id,
        )

    def get_policy(self, policy_id: str | None = None) -> PolicyDefinition | None:
        target = str(policy_id or self.active_policy_id).strip()
        return next((policy for policy in self.policies if policy.policy_id == target), None)

    def select_policy_for_umo(self, umo: str) -> PolicyDefinition:
        """Select the first usable UMO override, then the configured default."""

        usable_ids = self._usable_policy_ids()
        normalized_umo = str(umo or "").strip()
        if normalized_umo:
            for policy in self.policies:
                if (
                    normalized_umo in policy.umo_list
                    and policy.policy_id in usable_ids
                ):
                    return policy
        default_policy = self.get_policy()
        if default_policy is not None and default_policy.policy_id in usable_ids:
            return default_policy
        builtin_default = self.get_policy(DEFAULT_POLICY_ID)
        if builtin_default is not None:
            return builtin_default
        return self.default_policy()

    def _usable_policy_ids(self) -> set[str]:
        usable: set[str] = set()
        for policy in self.policies:
            candidate = PolicyLibrary(
                rules=self.rules,
                policies=(policy,),
                active_policy_id=policy.policy_id,
            )
            if candidate.validate().valid:
                usable.add(policy.policy_id)
        return usable

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
            elif rule.template_key in KNOWN_COMPONENT_TYPES:
                fatal_errors.append(
                    f"rule {rule.rule_id} uses component type {rule.template_key}; "
                    "components may only be stored inside a policy"
                )
            elif (
                rule.template_key in KNOWN_RULE_TEMPLATE_KEYS
                and _is_sanitize_action(rule.default_action_on_hit)
                and rule.template_key not in {"plain_keywords", "regex_pattern"}
            ):
                fatal_errors.append(
                    f"rule {rule.rule_id} uses sanitize, which is only available "
                    "for plain_keywords and regex_pattern"
                )

        for policy in self.policies:
            if not POLICY_ID_PATTERN.fullmatch(policy.policy_id):
                fatal_errors.append(f"invalid policy_id: {policy.policy_id or '(empty)'}")
            elif policy.policy_id in policy_ids:
                fatal_errors.append(f"duplicate policy_id: {policy.policy_id}")
            else:
                policy_ids.add(policy.policy_id)
            seen_node_ids: set[str] = set()
            for binding in policy.bindings:
                if binding.rule_id not in rule_ids:
                    fatal_errors.append(
                        f"policy {policy.policy_id} references missing rule {binding.rule_id}"
                    )
                if binding.rule_id in seen_node_ids:
                    fatal_errors.append(
                        f"policy {policy.policy_id} uses node id {binding.rule_id} more than once"
                    )
                seen_node_ids.add(binding.rule_id)
                if binding.rail not in RAIL_NAMES:
                    fatal_errors.append(
                        f"policy {policy.policy_id} uses unknown rail {binding.rail}"
                    )
            for component in policy.components:
                if not RULE_ID_PATTERN.fullmatch(component.component_id):
                    fatal_errors.append(
                        f"invalid component_id: {component.component_id or '(empty)'}"
                    )
                elif component.component_id in seen_node_ids:
                    fatal_errors.append(
                        f"policy {policy.policy_id} uses node id {component.component_id} more than once"
                    )
                seen_node_ids.add(component.component_id)
                if component.rail not in RAIL_NAMES:
                    fatal_errors.append(
                        f"policy {policy.policy_id} uses unknown rail {component.rail}"
                    )
                elif component.component_type not in COMPONENT_TEMPLATES[component.rail]:
                    fatal_errors.append(
                        f"policy {policy.policy_id} cannot place component {component.component_id} "
                        f"({component.component_type or 'unknown'}) in Step {STEP_BY_RAIL[component.rail]}"
                    )
            known_node_ids = {
                *(binding.rule_id for binding in policy.bindings),
                *(component.component_id for component in policy.components),
            }
            seen_order_ids: set[str] = set()
            for node_id in policy.node_order:
                if node_id not in known_node_ids:
                    fatal_errors.append(
                        f"policy {policy.policy_id} node_order references missing node {node_id}"
                    )
                elif node_id in seen_order_ids:
                    fatal_errors.append(
                        f"policy {policy.policy_id} node_order repeats node {node_id}"
                    )
                seen_order_ids.add(node_id)

        for policy in self.policies:
            for binding in policy.bindings:
                rule = next((item for item in self.rules if item.rule_id == binding.rule_id), None)
                if rule is None or binding.rail not in RAIL_NAMES:
                    continue
                if rule.template_key in KNOWN_RULE_TEMPLATE_KEYS:
                    if rule.template_key not in RULE_TEMPLATES[binding.rail]:
                        fatal_errors.append(
                            f"policy {policy.policy_id} cannot bind {rule.rule_id} "
                            f"({rule.template_key}) to Step {STEP_BY_RAIL[binding.rail]}"
                        )
                    action_on_hit = (
                        binding.action_on_hit
                        if binding.action_on_hit is not None
                        else rule.default_action_on_hit
                    )
                    if (
                        _is_sanitize_action(action_on_hit)
                        and rule.template_key not in {"plain_keywords", "regex_pattern"}
                    ):
                        fatal_errors.append(
                            f"rule {rule.rule_id} uses sanitize, which is only available "
                            "for plain_keywords and regex_pattern"
                        )
                    if (
                        _is_retry_generation_action(action_on_hit)
                        and binding.rail != "output_rail"
                    ):
                        warnings.append(
                            f"rule {rule.rule_id} uses retry_generation as its hit action outside Step 5; "
                            "it will fall back to the Step default"
                        )
                    action_on_error = (
                        binding.action_on_error
                        if binding.action_on_error is not None
                        else rule.default_action_on_error
                    )
                    if (
                        _is_retry_generation_action(action_on_error)
                        and binding.rail != "output_rail"
                    ):
                        warnings.append(
                            f"rule {rule.rule_id} uses retry_generation as its error action outside Step 5; "
                            "it will fall back to the Step default"
                        )
                else:
                    warnings.append(
                        f"policy {policy.policy_id} binds {rule.rule_id} to unsupported "
                        f"template {rule.template_key} in {binding.rail}"
                    )

            for component in policy.components:
                if component.rail not in RAIL_NAMES:
                    continue
                if component.component_type not in COMPONENT_TEMPLATES[component.rail]:
                    continue
                if component.component_type == "logic_gate":
                    component_config = (
                        component.config if isinstance(component.config, Mapping) else {}
                    )
                    gate = str(component_config.get("gate") or "all").strip().lower()
                    if gate not in {"all", "any"}:
                        fatal_errors.append(
                            f"component {component.component_id} has invalid logic gate mode {gate}"
                        )
                    if not _clean_string_list(component_config.get("inputs")):
                        fatal_errors.append(
                            f"component {component.component_id} has no logic gate inputs"
                        )
                if _is_sanitize_action(component.action_on_hit):
                    fatal_errors.append(
                        f"component {component.component_id} uses sanitize, which is only available "
                        "for plain_keywords and regex_pattern"
                    )
                if (
                    _is_retry_generation_action(component.action_on_hit)
                    and component.rail != "output_rail"
                ):
                    warnings.append(
                        f"component {component.component_id} uses retry_generation as its hit action outside Step 5; "
                        "it will fall back to the Step default"
                    )
                if (
                    _is_retry_generation_action(component.action_on_error)
                    and component.rail != "output_rail"
                ):
                    warnings.append(
                        f"component {component.component_id} uses retry_generation as its error action outside Step 5; "
                        "it will fall back to the Step default"
                    )

        rule_by_id = {rule.rule_id: rule for rule in self.rules}
        for policy in self.policies:
            fatal_errors.extend(_validate_policy_dependency_graph(policy, rule_by_id))

        if self.active_policy_id not in policy_ids:
            fatal_errors.append(f"active policy does not exist: {self.active_policy_id}")
        return LibraryValidation(tuple(fatal_errors), tuple(warnings))


def compile_policy_to_runtime_config(
    base_config: Mapping[str, Any] | None,
    library: PolicyLibrary,
    policy_id: str | None = None,
) -> tuple[dict[str, Any], LibraryValidation]:
    """Compile a selected policy into the runtime rail configuration."""

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
        rail["__policy_step_settings"] = _copy_dict(
            policy.rail_settings.get(rail_name)
        )
        rail["rule_list"] = []
        compiled[rail_name] = rail
    if policy.session_scope:
        session_control = _copy_dict(compiled.get("session_control"))
        session_control.update(copy.deepcopy(policy.session_scope))
        compiled["session_control"] = session_control

    for node_kind, node in _ordered_policy_nodes(policy):
        if node_kind == "rule":
            rule = rule_by_id[node.rule_id]
            compiled[node.rail]["rule_list"].append(_compile_binding(rule, node))
        else:
            compiled[node.rail]["rule_list"].append(_compile_component(node))
    return compiled, validation


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


def _compile_component(component: PolicyComponent) -> dict[str, Any]:
    item = copy.deepcopy(component.config)
    item.update(
        {
            "__template_key": component.component_type,
            "rule_id": component.component_id,
            "enabled": component.enabled,
            "priority": component.priority,
            "depend_on": component.depend_on,
            "action_on_hit": component.action_on_hit,
            "action_on_error": component.action_on_error,
        }
    )
    return item


def _ordered_policy_nodes(
    policy: PolicyDefinition,
) -> list[tuple[str, PolicyRuleBinding | PolicyComponent]]:
    """Return policy nodes in persisted order, with safe legacy fallbacks."""

    by_id: dict[str, tuple[str, PolicyRuleBinding | PolicyComponent]] = {}
    for binding in policy.bindings:
        by_id[binding.rule_id] = ("rule", binding)
    for component in policy.components:
        by_id[component.component_id] = ("component", component)
    ordered: list[tuple[str, PolicyRuleBinding | PolicyComponent]] = []
    emitted: set[str] = set()
    for node_id in policy.node_order:
        node = by_id.get(node_id)
        if node is not None and node_id not in emitted:
            ordered.append(node)
            emitted.add(node_id)
    for binding in policy.bindings:
        if binding.rule_id not in emitted:
            ordered.append(("rule", binding))
            emitted.add(binding.rule_id)
    for component in policy.components:
        if component.component_id not in emitted:
            ordered.append(("component", component))
            emitted.add(component.component_id)
    return ordered


def _copy_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    return {}


def _copy_nested_dict(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _copy_dict(item)
        for key, item in value.items()
        if isinstance(item, Mapping)
    }


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


def _as_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _dependency_target(value: Any) -> str:
    """Return the referenced rule ID from the public dependency syntax."""

    text = str(value or "").strip()
    if text[:1] in {"!", "?"}:
        text = text[1:].strip()
    return text


def _policy_dependency_references(
    policy: PolicyDefinition,
    rule_by_id: Mapping[str, RuleDefinition],
) -> list[tuple[str, str, str]]:
    """Return (dependent node ID, raw reference, source kind) tuples."""

    references: list[tuple[str, str, str]] = []
    for binding in policy.bindings:
        if binding.depend_on:
            references.append((binding.rule_id, binding.depend_on, "depend_on"))
    for component in policy.components:
        if component.depend_on:
            references.append((component.component_id, component.depend_on, "depend_on"))
        if component.component_type != "logic_gate":
            continue
        config = component.config if isinstance(component.config, Mapping) else {}
        for value in _clean_string_list(config.get("inputs")):
            references.append((component.component_id, value, "logic input"))
    return references


def _validate_policy_dependency_graph(
    policy: PolicyDefinition,
    rule_by_id: Mapping[str, RuleDefinition],
) -> list[str]:
    """Validate references that must be safe before a policy can be published.

    Runtime Rails run from Step 1 through Step 5.  A dependency can therefore
    point to a rule in the same or an earlier Step, but never to a later Step.
    These checks intentionally operate on policy bindings, rather than the
    reusable rule definitions, because rail placement and enabled state belong
    to the policy.
    """

    errors: list[str] = []
    nodes_by_id: dict[str, PolicyRuleBinding | PolicyComponent] = {
        binding.rule_id: binding for binding in policy.bindings
    }
    nodes_by_id.update(
        {component.component_id: component for component in policy.components}
    )
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes_by_id}

    for dependent_id, raw_reference, source_kind in _policy_dependency_references(
        policy, rule_by_id
    ):
        target_id = _dependency_target(raw_reference)
        if not target_id:
            errors.append(
                f"policy {policy.policy_id} node {dependent_id} has an empty {source_kind} reference"
            )
            continue
        dependent = nodes_by_id.get(dependent_id)
        target = nodes_by_id.get(target_id)
        if dependent is None or target is None:
            errors.append(
                f"policy {policy.policy_id} node {dependent_id} {source_kind} references "
                f"{target_id}, which is not present in this policy"
            )
            continue
        adjacency.setdefault(dependent_id, set()).add(target_id)
        if not target.enabled:
            errors.append(
                f"policy {policy.policy_id} node {dependent_id} {source_kind} references "
                f"disabled node {target_id}"
            )
        if dependent.rail in STEP_BY_RAIL and target.rail in STEP_BY_RAIL:
            dependent_step = STEP_BY_RAIL[dependent.rail]
            target_step = STEP_BY_RAIL[target.rail]
            if target_step > dependent_step:
                errors.append(
                    f"policy {policy.policy_id} node {dependent_id} in Step {dependent_step} "
                    f"cannot depend on {target_id} in later Step {target_step}"
                )

    errors.extend(_find_dependency_cycles(policy.policy_id, adjacency))
    return errors


def _find_dependency_cycles(
    policy_id: str,
    adjacency: Mapping[str, set[str]],
) -> list[str]:
    """Return one deterministic error for each directed dependency cycle."""

    errors: list[str] = []
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()
    reported: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        visited.add(node)
        active.append(node)
        active_set.add(node)
        for target in sorted(adjacency.get(node, ())):
            if target not in visited:
                visit(target)
            elif target in active_set:
                start = active.index(target)
                cycle = tuple(active[start:] + [target])
                canonical = tuple(sorted(cycle[:-1]))
                if canonical not in reported:
                    reported.add(canonical)
                    errors.append(
                        f"policy {policy_id} has cyclic dependency: {' -> '.join(cycle)}"
                    )
        active.pop()
        active_set.remove(node)

    for node in sorted(adjacency):
        if node not in visited:
            visit(node)
    return errors


def _is_sanitize_action(action: str | None) -> bool:
    return str(action or "").strip() == "sanitize"


def _is_retry_generation_action(action: str | None) -> bool:
    return str(action or "").strip() == "retry_generation"
