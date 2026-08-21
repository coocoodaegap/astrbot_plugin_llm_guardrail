"""Immutable-at-publication configuration snapshots for P1 Pages."""

from __future__ import annotations

import asyncio
import copy
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from .config import NormalizedConfig, normalize_config
    from .core import GraphIndex, build_graph_index
    from .policy_library import (
        LibraryValidation,
        PolicyDefinition,
        PolicyLibrary,
        RuleDefinition,
        compile_policy_to_legacy_config,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedConfig, normalize_config
    from core import GraphIndex, build_graph_index
    from policy_library import (
        LibraryValidation,
        PolicyDefinition,
        PolicyLibrary,
        RuleDefinition,
        compile_policy_to_legacy_config,
    )


SNAPSHOT_EVENT_EXTRA = "_llm_guardrail_config_snapshot"
SNAPSHOT_FILE_VERSION = 1


@dataclass(frozen=True)
class ConfigSnapshot:
    """One request-safe view of the guardrail configuration."""

    revision: int
    saved_at: float
    source_config: dict[str, Any]
    policy_library: PolicyLibrary
    library_validation: LibraryValidation
    runtime_config: NormalizedConfig
    graph: GraphIndex
    diagnostics: tuple[str, ...]


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

        current_library = self._current.policy_library
        library = PolicyLibrary(
            rules=tuple(rules),
            policies=current_library.policies,
            active_policy_id=current_library.active_policy_id,
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
        )
        return await self.publish_policy_library(library, expected_revision)

    async def publish_system_settings(
        self,
        settings: Mapping[str, Any],
        expected_revision: int | None,
        persist_settings: Callable[[dict[str, Any]], None],
    ) -> SnapshotPublishResult:
        """Persist AstrBot-owned settings before publishing their runtime snapshot.

        Pages-owned policy libraries intentionally remain in the plugin JSON snapshot.
        System settings instead use AstrBotConfig as their durable source of truth.
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
            for key in ("fallback_policy_settings", "session_control"):
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
                        "session_control": copy.deepcopy(
                            candidate.source_config["session_control"]
                        ),
                    },
                )
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                return SnapshotPublishResult(
                    success=False,
                    diagnostics=(f"failed to save AstrBot system settings: {exc}",),
                )

            self._current = candidate
            return SnapshotPublishResult(success=True, snapshot=candidate)

    def overview(self) -> dict[str, Any]:
        """Return a safe, small Pages overview without raw user configuration."""

        snapshot = self._current
        config = snapshot.runtime_config
        rails = {}
        for name, rail in config.rails.items():
            enabled_rules = sum(1 for rule in rail.rules if rule.enabled and rule.valid)
            rails[name] = {
                "enabled": rail.enabled,
                "enabled_rules": enabled_rules,
                "total_rules": len(rail.rules),
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
        library, legacy_diagnostics = _load_policy_library(source_config)
        source_config["policy_library"] = library.to_dict()
        compiled_config, library_validation = compile_policy_to_legacy_config(
            source_config,
            library,
        )
        runtime_config = normalize_config(compiled_config)
        graph = build_graph_index(runtime_config)
        diagnostics = list(self._startup_diagnostics)
        diagnostics.extend(legacy_diagnostics)
        diagnostics.extend(library_validation.fatal_errors)
        diagnostics.extend(library_validation.warnings)
        diagnostics.extend(runtime_config.warnings)
        if graph.metrics.has_cycle_suspect:
            diagnostics.append("dependency graph contains a cycle suspect")
        return ConfigSnapshot(
            revision=max(0, int(revision)),
            saved_at=time.time(),
            source_config=source_config,
            policy_library=library,
            library_validation=library_validation,
            runtime_config=runtime_config,
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


def _copy_config(raw_config: Any) -> dict[str, Any]:
    """Copy an AstrBotConfig-like object into a JSON-safe plain dict."""

    if isinstance(raw_config, Mapping):
        value: Any = dict(raw_config)
    elif hasattr(raw_config, "items"):
        value = dict(raw_config.items())
    else:
        value = {}
    return copy.deepcopy(value)


def _load_policy_library(source_config: dict[str, Any]) -> tuple[PolicyLibrary, list[str]]:
    """Load only the Pages-owned library; legacy rule lists are no longer a source."""

    raw_library = source_config.get("policy_library")
    if isinstance(raw_library, Mapping):
        return PolicyLibrary.from_dict(raw_library), []
    return PolicyLibrary.empty(), []
