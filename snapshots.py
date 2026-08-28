"""Immutable-at-publication configuration snapshots for P1 Pages."""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

try:
    from .config import COMPONENT_TEMPLATES, NormalizedConfig, normalize_config
    from .core import GraphIndex, build_graph_index
    from .fallback_graph import build_fallback_runtime_config
    from .policy_library import (
        LibraryValidation,
        PolicyDefinition,
        PolicyLibrary,
        RuleDefinition,
        compile_policy_to_runtime_config,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import COMPONENT_TEMPLATES, NormalizedConfig, normalize_config
    from core import GraphIndex, build_graph_index
    from fallback_graph import build_fallback_runtime_config
    from policy_library import (
        LibraryValidation,
        PolicyDefinition,
        PolicyLibrary,
        RuleDefinition,
        compile_policy_to_runtime_config,
    )


SNAPSHOT_EVENT_EXTRA = "_llm_guardrail_config_snapshot"
SNAPSHOT_FILE_VERSION = 1
POLICY_COMPONENT_TYPES = frozenset().union(*COMPONENT_TEMPLATES.values())
SYSTEM_FALLBACK_POLICY_ID = "__system_fallback__"


@dataclass(frozen=True)
class ConfigSnapshot:
    """One request-safe view of the guardrail configuration."""

    revision: int
    saved_at: float
    source_config: dict[str, Any]
    policy_library: PolicyLibrary
    library_validation: LibraryValidation
    runtime_config: NormalizedConfig
    policy_runtime_configs: Mapping[str, NormalizedConfig]
    fallback_runtime_config: NormalizedConfig
    fallback_graph: GraphIndex
    graph: GraphIndex
    diagnostics: tuple[str, ...]

    def runtime_config_for_umo(self, umo: str) -> tuple[str, NormalizedConfig]:
        """Resolve a usable policy graph, or the snapshot's system fallback.

        A missing/invalid policy graph must never silently select an unrelated
        normal runtime config; the terminal fallback is system-owned.
        """

        policy = self.policy_library.select_usable_policy_for_umo(umo)
        if policy is not None:
            runtime_config = self.policy_runtime_configs.get(policy.policy_id)
            if runtime_config is not None:
                return policy.policy_id, runtime_config
        return SYSTEM_FALLBACK_POLICY_ID, self.fallback_runtime_config


@dataclass(frozen=True)
class SnapshotPublishResult:
    """The outcome of a candidate snapshot publication attempt."""

    success: bool
    snapshot: ConfigSnapshot | None = None
    conflict: bool = False
    diagnostics: tuple[str, ...] = ()


class ConfigSnapshotManager:
    """Build, persist, publish, and bind request-level config snapshots."""

    def __init__(self, raw_config: Any, persistence_path: str | Path | None = None):
        self._path = Path(persistence_path) if persistence_path else None
        self._publish_lock = asyncio.Lock()
        self._startup_diagnostics: list[str] = []
        persisted = self._load_persisted_config()
        system_config = _copy_config(raw_config)
        if persisted is not None and isinstance(persisted.get("policy_library"), Mapping):
            system_config["policy_library"] = copy.deepcopy(persisted["policy_library"])
        if persisted is not None and isinstance(persisted.get("system_constants"), Mapping):
            system_config["system_constants"] = copy.deepcopy(
                persisted["system_constants"]
            )
        self._current = self._build_snapshot(
            system_config,
            revision=self._load_persisted_revision() if persisted is not None else 0,
        )

    @property
    def current(self) -> ConfigSnapshot:
        return self._current

    def bind_event(self, adapter: Any, event: Any) -> ConfigSnapshot:
        """Return the existing event snapshot or bind the current one once."""

        existing = adapter.get_event_extra(event, SNAPSHOT_EVENT_EXTRA, None)
        if isinstance(existing, ConfigSnapshot):
            return existing
        snapshot = self._current
        adapter.set_event_extra(event, SNAPSHOT_EVENT_EXTRA, snapshot)
        return snapshot

    async def publish(
        self,
        raw_config: Any,
        expected_revision: int | None,
    ) -> SnapshotPublishResult:
        """Persist and atomically publish a valid next snapshot."""

        async with self._publish_lock:
            current = self._current
            if expected_revision is not None and expected_revision != current.revision:
                return SnapshotPublishResult(
                    success=False,
                    conflict=True,
                    diagnostics=(
                        f"configuration revision conflict: expected {expected_revision}, "
                        f"current {current.revision}",
                    ),
                )

            if not isinstance(raw_config, Mapping) and not hasattr(raw_config, "items"):
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=("configuration payload must be an object",),
                )

            candidate = self._build_snapshot(raw_config, revision=current.revision + 1)
            if not candidate.library_validation.valid:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=candidate.library_validation.fatal_errors,
                )
            try:
                await asyncio.to_thread(self._persist_snapshot, candidate)
            except (OSError, TypeError, ValueError) as exc:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=(f"failed to persist configuration snapshot: {exc}",),
                )

            self._current = candidate
            return SnapshotPublishResult(success=True, snapshot=candidate)

    async def publish_policy_library(
        self,
        policy_library: PolicyLibrary,
        expected_revision: int | None,
    ) -> SnapshotPublishResult:
        """Publish a policy-library edit while retaining non-library settings."""

        raw_config = copy.deepcopy(self._current.source_config)
        raw_config["policy_library"] = policy_library.to_dict()
        return await self.publish(raw_config, expected_revision)

    async def publish_rule_library(
        self,
        rules: tuple[RuleDefinition, ...],
        expected_revision: int | None,
    ) -> SnapshotPublishResult:
        """Publish only reusable rules, retaining all current policies."""

        component_rules = [
            rule.rule_id or "(empty)"
            for rule in rules
            if rule.template_key in POLICY_COMPONENT_TYPES
        ]
        if component_rules:
            return SnapshotPublishResult(
                success=False,
                diagnostics=(
                    "policy component types may not be saved in the rule library: "
                    + ", ".join(component_rules),
                ),
            )
        current_library = self._current.policy_library
        existing_templates = {
            rule.rule_id: rule.template_key for rule in current_library.rules
        }
        for rule in rules:
            previous_template = existing_templates.get(rule.rule_id)
            if previous_template is not None and previous_template != rule.template_key:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=(
                        f"rule {rule.rule_id} template cannot change after creation",
                    ),
                )
        library = PolicyLibrary(
            rules=tuple(rules),
            policies=current_library.policies,
            active_policy_id=current_library.active_policy_id,
            umo_policy_selections=current_library.umo_policy_selections,
        )
        return await self.publish_policy_library(library, expected_revision)

    async def publish_policy_collection(
        self,
        policies: tuple[PolicyDefinition, ...],
        active_policy_id: str,
        expected_revision: int | None,
    ) -> SnapshotPublishResult:
        """Publish policy composition, retaining all current reusable rules."""

        current_library = self._current.policy_library
        library = PolicyLibrary(
            rules=current_library.rules,
            policies=tuple(policies),
            active_policy_id=active_policy_id,
            umo_policy_selections=current_library.umo_policy_selections,
        )
        return await self.publish_policy_library(library, expected_revision)

    async def publish_umo_policy_selection(
        self,
        umo: str,
        policy_id: str | None,
        expected_revision: int | None,
    ) -> SnapshotPublishResult:
        """Persist one UMO's explicit policy selection through snapshot CAS.

        A non-empty policy ID must be usable at the moment it is selected.
        Existing stale selections are still retained by policy-library edits so
        they can resume automatically after the referenced policy is repaired.
        """

        normalized_umo = str(umo or "").strip()
        normalized_policy_id = str(policy_id or "").strip()
        if not normalized_umo:
            return SnapshotPublishResult(
                success=False,
                diagnostics=("umo is required",),
            )
        current_library = self._current.policy_library
        if normalized_policy_id and not current_library.is_policy_usable(
            normalized_policy_id
        ):
            return SnapshotPublishResult(
                success=False,
                diagnostics=(
                    f"policy is unavailable or does not exist: {normalized_policy_id}",
                ),
            )
        library = current_library.with_umo_policy_selection(
            normalized_umo,
            normalized_policy_id or None,
        )
        return await self.publish_policy_library(library, expected_revision)

    async def publish_system_settings(
        self,
        settings: Mapping[str, Any],
        expected_revision: int | None,
        persist_settings: Callable[[dict[str, Any]], None],
    ) -> SnapshotPublishResult:
        """Persist system settings and publish their runtime snapshot.

        Pages-owned policy libraries intentionally remain in the plugin JSON snapshot.
        Dynamic system constants likewise use that plugin-owned snapshot because
        AstrBot's schema persistence cannot safely represent an open-ended map.
        """

        async with self._publish_lock:
            current = self._current
            if expected_revision is not None and expected_revision != current.revision:
                return SnapshotPublishResult(
                    success=False,
                    conflict=True,
                    diagnostics=(
                        f"configuration revision conflict: expected {expected_revision}, "
                        f"current {current.revision}",
                    ),
                )

            candidate_source = copy.deepcopy(current.source_config)
            for key in (
                "fallback_policy_settings",
                "system_constants",
                "session_control",
                "access_control",
                "session_policy_state",
                "debug_settings",
            ):
                value = settings.get(key)
                if not isinstance(value, Mapping):
                    return SnapshotPublishResult(
                        success=False,
                        diagnostics=(f"system setting {key} must be an object",),
                    )
                candidate_source[key] = copy.deepcopy(dict(value))

            candidate = self._build_snapshot(
                candidate_source,
                revision=current.revision + 1,
            )
            if not candidate.library_validation.valid:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=candidate.library_validation.fatal_errors,
                )
            try:
                await asyncio.to_thread(
                    persist_settings,
                    {
                        "fallback_policy_settings": copy.deepcopy(
                            candidate.source_config["fallback_policy_settings"]
                        ),
                        "system_constants": copy.deepcopy(
                            candidate.source_config["system_constants"]
                        ),
                        "session_control": copy.deepcopy(
                            candidate.source_config["session_control"]
                        ),
                        "access_control": copy.deepcopy(
                            candidate.source_config["access_control"]
                        ),
                        "session_policy_state": copy.deepcopy(
                            candidate.source_config["session_policy_state"]
                        ),
                        "debug_settings": copy.deepcopy(
                            candidate.source_config["debug_settings"]
                        ),
                    },
                )
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=(f"failed to save AstrBot system settings: {exc}",),
                )
            try:
                await asyncio.to_thread(self._persist_snapshot, candidate)
            except (OSError, TypeError, ValueError) as exc:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=(f"failed to save plugin system constants: {exc}",),
                )

            self._current = candidate
            return SnapshotPublishResult(success=True, snapshot=candidate)

    def overview(self) -> dict[str, Any]:
        """Return a safe, small Pages overview without raw user configuration."""

        snapshot = self._current
        config = snapshot.runtime_config
        rails = {}
        for name, rail in config.rails.items():
            enabled_nodes = sum(1 for node in rail.nodes if node.enabled and node.valid)
            rails[name] = {
                "enabled": rail.enabled,
                "enabled_nodes": enabled_nodes,
                "total_nodes": len(rail.nodes),
                # Legacy dashboard keys; retained until the Pages API moves
                # to the node-oriented names above.
                "enabled_rules": enabled_nodes,
                "total_rules": len(rail.nodes),
            }
        return {
            "revision": snapshot.revision,
            "saved_at": snapshot.saved_at,
            "schema_version": config.schema_version,
            "warning_count": len(snapshot.diagnostics),
            "rule_library_count": len(snapshot.policy_library.rules),
            "policy_library_count": len(snapshot.policy_library.policies),
            "active_policy_id": snapshot.policy_library.active_policy_id,
            "rails": rails,
            "graph": {
                "node_count": snapshot.graph.metrics.node_count,
                "edge_count": snapshot.graph.metrics.edge_count,
                "max_depth": snapshot.graph.metrics.max_depth,
                "has_cross_step_edges": snapshot.graph.metrics.has_cross_step_edges,
                "has_cycle_suspect": snapshot.graph.metrics.has_cycle_suspect,
            },
        }

    def diagnostics(self) -> list[str]:
        return list(self._current.diagnostics)

    def _build_snapshot(self, raw_config: Any, revision: int) -> ConfigSnapshot:
        source_config = _copy_config(raw_config)
        library = _load_policy_library(source_config).without_legacy_default_policy()
        source_config["policy_library"] = library.to_dict()
        compiled_config, library_validation = compile_policy_to_runtime_config(
            source_config,
            library,
        )
        runtime_config = normalize_config(compiled_config)
        fallback_runtime_config = build_fallback_runtime_config(
            runtime_config.fallback_policy_settings,
            access_control=runtime_config.access_control,
            system_constants=runtime_config.system_constants,
        )
        policy_runtime_configs = {
            policy.policy_id: normalize_config(
                compile_policy_to_runtime_config(
                    source_config,
                    library,
                    policy.policy_id,
                )[0]
            )
            for policy in library.policies
        }
        if library_validation.valid:
            dependency_errors = _runtime_dependency_errors(
                library,
                policy_runtime_configs,
            )
            if dependency_errors:
                library_validation = LibraryValidation(
                    fatal_errors=(*library_validation.fatal_errors, *dependency_errors),
                    warnings=library_validation.warnings,
                )
        graph = build_graph_index(runtime_config)
        fallback_graph = build_graph_index(fallback_runtime_config)
        diagnostics = list(self._startup_diagnostics)
        diagnostics.extend(library_validation.fatal_errors)
        diagnostics.extend(library_validation.warnings)
        diagnostics.extend(runtime_config.warnings)
        diagnostics.extend(fallback_runtime_config.warnings)
        if graph.metrics.has_cycle_suspect:
            diagnostics.append("dependency graph contains a cycle suspect")
        return ConfigSnapshot(
            revision=max(0, int(revision)),
            saved_at=time.time(),
            source_config=source_config,
            policy_library=library,
            library_validation=library_validation,
            runtime_config=runtime_config,
            policy_runtime_configs=policy_runtime_configs,
            fallback_runtime_config=fallback_runtime_config,
            fallback_graph=fallback_graph,
            graph=graph,
            diagnostics=tuple(diagnostics),
        )

    def _load_persisted_config(self) -> dict[str, Any] | None:
        path = self._path
        if path is None or not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            config = None
            if isinstance(payload, dict):
                config = payload.get("config_source", payload.get("runtime_config"))
            if not isinstance(config, dict):
                raise ValueError("runtime_config is missing or invalid")
            return config
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._startup_diagnostics.append(f"failed to load config snapshot: {exc}")
            return None

    def _load_persisted_revision(self) -> int:
        path = self._path
        if path is None or not path.is_file():
            return 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return max(0, int(payload.get("revision", 0)))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return 0

    def _persist_snapshot(self, snapshot: ConfigSnapshot) -> None:
        path = self._path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        backup = path.with_suffix(path.suffix + ".bak")
        payload = {
            "version": SNAPSHOT_FILE_VERSION,
            "revision": snapshot.revision,
            "saved_at": snapshot.saved_at,
            "config_source": {
                "policy_library": snapshot.policy_library.to_dict(),
                "system_constants": copy.deepcopy(
                    snapshot.runtime_config.system_constants
                ),
            },
        }
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if path.is_file():
                shutil.copyfile(path, backup)
            temporary.replace(path)
        except (OSError, TypeError, ValueError):
            temporary.unlink(missing_ok=True)
            raise


def _runtime_dependency_target(value: Any) -> str:
    text = str(value or "").strip()
    if text[:1] in {"!", "?", "~"}:
        text = text[1:].strip()
    return text


def _runtime_logic_gate_input_target(value: Any) -> str:
    text = str(value or "").strip()
    if text[:1] in {"!", "?", "~"}:
        text = text[1:].strip()
    if text.endswith("?"):
        text = text[:-1]
    return text.partition(".")[0]


def _runtime_dependency_references(
    policy: PolicyDefinition,
    rule_by_id: Mapping[str, RuleDefinition],
) -> list[tuple[str, str, str]]:
    references: list[tuple[str, str, str]] = []
    for binding in policy.bindings:
        if binding.depend_on:
            references.append((binding.rule_id, binding.depend_on, "depend_on"))
    for component in policy.components:
        if component.depend_on:
            references.append((component.component_id, component.depend_on, "depend_on"))
        if component.component_type != "logic_gate":
            continue
        inputs = component.config.get("inputs")
        if isinstance(inputs, list):
            references.extend(
                (component.component_id, str(item), "logic_input")
                for item in inputs
                if str(item).strip()
            )
    return references


def _runtime_dependency_errors(
    library: PolicyLibrary,
    policy_runtime_configs: Mapping[str, NormalizedConfig],
) -> tuple[str, ...]:
    """Reject policies whose structurally valid dependency target cannot run.

    Template validity is intentionally read from ``normalize_config`` rather
    than duplicated here.  This keeps regex, RAG, LLM, and future template
    validation aligned with the runtime compiler.
    """

    errors: list[str] = []
    rule_by_id = {rule.rule_id: rule for rule in library.rules}
    emitted: set[tuple[str, str, str, str]] = set()
    for policy in library.policies:
        config = policy_runtime_configs.get(policy.policy_id)
        if config is None:
            continue
        normalized_by_id = {
            rule.user_rule_id: rule
            for rail in config.rails.values()
            for rule in rail.nodes
            if rule.user_rule_id
        }
        for dependent_id, raw_reference, source_kind in _runtime_dependency_references(policy, rule_by_id):
            target_id = (
                _runtime_logic_gate_input_target(raw_reference)
                if source_kind == "logic_input"
                else _runtime_dependency_target(raw_reference)
            )
            target = normalized_by_id.get(target_id)
            if target is None:
                # Structural validation reports references outside this policy.
                continue
            target_rail = config.rails.get(target.rail)
            if target_rail is not None and not target_rail.enabled:
                key = (policy.policy_id, dependent_id, target_id, "step_disabled")
                message = (
                    f"policy {policy.policy_id} rule {dependent_id} depends on {target_id}, "
                    f"but Step {target.rail} is disabled"
                )
            elif not target.enabled or not target.valid:
                key = (policy.policy_id, dependent_id, target_id, "target_unavailable")
                message = (
                    f"policy {policy.policy_id} rule {dependent_id} depends on unavailable "
                    f"rule {target_id}"
                )
            else:
                continue
            if key not in emitted:
                emitted.add(key)
                errors.append(message)
    return tuple(errors)


def _copy_config(raw_config: Any) -> dict[str, Any]:
    """Copy an AstrBotConfig-like object into a JSON-safe plain dict."""

    if isinstance(raw_config, Mapping):
        value: Any = dict(raw_config)
    elif hasattr(raw_config, "items"):
        value = dict(raw_config.items())
    else:
        value = {}
    return copy.deepcopy(value)


def _load_policy_library(source_config: dict[str, Any]) -> PolicyLibrary:
    """Load the Pages-owned policy library or an empty user-policy collection."""

    raw_library = source_config.get("policy_library")
    if isinstance(raw_library, Mapping):
        return PolicyLibrary.from_dict(raw_library)
    return PolicyLibrary.empty()
