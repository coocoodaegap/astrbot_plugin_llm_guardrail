"""AstrBot Pages API for P1 guardrail status and separately saved libraries."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

try:
    from quart import jsonify, request
except ImportError:  # pragma: no cover - allows isolated unit tests without AstrBot.
    request = None

    def jsonify(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

try:
    from .policy_library import PolicyDefinition, RuleDefinition
except ImportError:  # pragma: no cover - fallback for direct script loading
    from policy_library import PolicyDefinition, RuleDefinition


class GuardrailPagesApiMixin:
    """Register the small read-only Pages surface introduced in P1."""

    def _register_pages_web_api(self) -> None:
        register_web_api = getattr(self.context, "register_web_api", None)
        if not callable(register_web_api):
            self._pages_api_available = False
            return

        plugin_name = getattr(self, "PLUGIN_NAME", "astrbot_plugin_llm_guardrail")
        routes = (
            ("get_overview", self._pages_get_overview, ["GET"], "Get guardrail overview"),
            ("get_diagnostics", self._pages_get_diagnostics, ["GET"], "Get guardrail diagnostics"),
            ("get_system_settings", self._pages_get_system_settings, ["GET"], "Get normalized system settings"),
            ("save_system_settings", self._pages_save_system_settings, ["POST"], "Save and publish system settings"),
            ("get_rule_library", self._pages_get_rule_library, ["GET"], "Get rule library"),
            ("save_rule_library", self._pages_save_rule_library, ["POST"], "Save rule library"),
            ("get_policy_library", self._pages_get_policy_library, ["GET"], "Get policy library"),
            ("save_policy_library", self._pages_save_policy_library, ["POST"], "Save policy library"),
        )
        for endpoint, handler, methods, description in routes:
            register_web_api(f"/{plugin_name}/{endpoint}", handler, methods, description)
        self._pages_api_available = True

    async def _pages_get_overview(self):
        return jsonify(
            {
                "success": True,
                "overview": self.snapshot_manager.overview(),
            }
        )

    async def _pages_get_diagnostics(self):
        snapshot = self.snapshot_manager.current
        return jsonify(
            {
                "success": True,
                "revision": snapshot.revision,
                "diagnostics": self.snapshot_manager.diagnostics(),
            }
        )

    async def _pages_get_system_settings(self):
        """Return the two active AstrBot configuration groups for read-only Pages."""

        snapshot = self.snapshot_manager.current
        config = snapshot.runtime_config
        return jsonify(
            {
                "success": True,
                "revision": snapshot.revision,
                "settings": {
                    "fallback_policy_settings": dict(config.fallback_policy_settings),
                    "session_control": {
                        key: list(value) if isinstance(value, list) else value
                        for key, value in config.session_control.items()
                    },
                },
                "schema": _load_system_settings_schema(),
            }
        )

    async def _pages_save_system_settings(self):
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        settings = payload.get("settings")
        expected_revision = payload.get("expected_revision")
        if not isinstance(settings, dict):
            return self._pages_error("settings must be an object")
        if not isinstance(expected_revision, int):
            return self._pages_error("expected_revision must be an integer")

        diagnostics = _validate_system_settings_payload(
            settings,
            _load_system_settings_schema(),
        )
        if diagnostics:
            return self._pages_error(
                "System settings are invalid.",
                400,
                "\n".join(diagnostics),
            )

        result = await self.snapshot_manager.publish_system_settings(
            settings,
            expected_revision,
            self._pages_persist_system_settings,
        )
        if result.success and result.snapshot is not None:
            self.normalized_config = result.snapshot.runtime_config
        return self._pages_publish_response(result, "System settings")

    def _pages_persist_system_settings(self, settings: dict[str, Any]) -> None:
        """Write the validated groups through AstrBotConfig with in-memory rollback."""

        config = getattr(self, "config", None)
        save_config = getattr(config, "save_config", None)
        if config is None or not callable(save_config):
            raise RuntimeError("AstrBotConfig.save_config is unavailable")
        original = {
            key: copy.deepcopy(config.get(key))
            for key in ("fallback_policy_settings", "session_control")
        }
        try:
            for key, value in settings.items():
                config[key] = copy.deepcopy(value)
            save_config()
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            for key, value in original.items():
                config[key] = value
            try:
                save_config()
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
                pass
            raise

    async def _pages_get_policy_library(self):
        snapshot = self.snapshot_manager.current
        validation = snapshot.library_validation
        return jsonify(
            {
                "success": True,
                "revision": snapshot.revision,
                "policy_library": {
                    "policies": [policy.to_dict() for policy in snapshot.policy_library.policies],
                    "active_policy_id": snapshot.policy_library.active_policy_id,
                },
                "validation": {
                    "valid": validation.valid,
                    "fatal_errors": list(validation.fatal_errors),
                    "warnings": list(validation.warnings),
                },
            }
        )

    async def _pages_get_rule_library(self):
        snapshot = self.snapshot_manager.current
        validation = snapshot.library_validation
        return jsonify(
            {
                "success": True,
                "revision": snapshot.revision,
                "rule_library": {
                    "rules": [rule.to_dict() for rule in snapshot.policy_library.rules],
                },
                "validation": {
                    "valid": validation.valid,
                    "fatal_errors": list(validation.fatal_errors),
                    "warnings": list(validation.warnings),
                },
            }
        )

    async def _pages_save_rule_library(self):
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        rule_payload = payload.get("rule_library")
        expected_revision = payload.get("expected_revision")
        if not isinstance(rule_payload, dict):
            return self._pages_error("rule_library must be an object")
        if not isinstance(rule_payload.get("rules"), list):
            return self._pages_error("rule_library.rules must be an array")
        if not isinstance(expected_revision, int):
            return self._pages_error("expected_revision must be an integer")

        rules = tuple(
            RuleDefinition.from_dict(item)
            for item in rule_payload["rules"]
            if isinstance(item, dict)
        )
        result = await self.snapshot_manager.publish_rule_library(rules, expected_revision)
        return self._pages_publish_response(result, "Rule library")

    async def _pages_save_policy_library(self):
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        library_payload = payload.get("policy_library")
        if not isinstance(library_payload, dict):
            return self._pages_error("policy_library must be an object")
        expected_revision = payload.get("expected_revision")
        if not isinstance(expected_revision, int):
            return self._pages_error("expected_revision must be an integer")

        policies = library_payload.get("policies")
        active_policy_id = library_payload.get("active_policy_id")
        if not isinstance(policies, list):
            return self._pages_error("policy_library.policies must be an array")
        if not isinstance(active_policy_id, str):
            return self._pages_error("policy_library.active_policy_id must be a string")
        result = await self.snapshot_manager.publish_policy_collection(
            tuple(PolicyDefinition.from_dict(item) for item in policies if isinstance(item, dict)),
            active_policy_id,
            expected_revision,
        )
        return self._pages_publish_response(result, "Policy library")

    async def _pages_json_payload(self) -> dict[str, Any] | tuple[Any, int]:
        if request is None:
            return self._pages_error("Pages request context is unavailable", 503)
        try:
            payload = await request.get_json(force=True)
        except (RuntimeError, TypeError, ValueError) as exc:
            return self._pages_error("Invalid JSON payload", 400, str(exc))
        if not isinstance(payload, dict):
            return self._pages_error("JSON payload must be an object")
        return payload

    def _pages_publish_response(self, result: Any, label: str):
        if result.conflict:
            return jsonify(
                {
                    "success": False,
                    "conflict": True,
                    "error": "Configuration revision conflict.",
                    "diagnostics": list(result.diagnostics),
                }
            ), 409
        if not result.success:
            return self._pages_error(
                f"{label} was not saved.",
                400,
                "\n".join(result.diagnostics),
            )
        snapshot = result.snapshot
        return jsonify(
            {
                "success": True,
                "revision": snapshot.revision if snapshot else None,
                "diagnostics": list(snapshot.diagnostics) if snapshot else [],
            }
        )

    @staticmethod
    def _pages_error(message: str, status: int = 400, detail: str = ""):
        payload: dict[str, Any] = {"success": False, "error": message}
        if detail:
            payload["detail"] = detail
        return jsonify(payload), status


def _load_system_settings_schema() -> dict[str, Any]:
    """Load only the active system-setting schema shown by the Pages UI."""

    schema_path = Path(__file__).with_name("_conf_schema.json")
    try:
        with schema_path.open("r", encoding="utf-8") as schema_file:
            raw_schema = json.load(schema_file)
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        key: raw_schema[key]
        for key in ("fallback_policy_settings", "session_control")
        if isinstance(raw_schema.get(key), dict)
    }


def _validate_system_settings_payload(
    settings: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Reject incomplete, unknown, or type-invalid direct config writes."""

    diagnostics: list[str] = []
    expected_groups = {"fallback_policy_settings", "session_control"}
    if set(settings) != expected_groups:
        diagnostics.append("settings must contain exactly the active system setting groups")
        return diagnostics
    for group_key in expected_groups:
        group_schema = schema.get(group_key)
        group_settings = settings.get(group_key)
        if not isinstance(group_schema, dict) or not isinstance(group_settings, dict):
            diagnostics.append(f"{group_key} must be an object")
            continue
        expected_fields = group_schema.get("items")
        if not isinstance(expected_fields, dict):
            diagnostics.append(f"schema for {group_key} is unavailable")
            continue
        if set(group_settings) != set(expected_fields):
            diagnostics.append(f"{group_key} must contain every defined field exactly once")
            continue
        for field_key, field in expected_fields.items():
            value = group_settings[field_key]
            field_type = field.get("type") if isinstance(field, dict) else None
            label = f"{group_key}.{field_key}"
            if field_type == "bool" and not isinstance(value, bool):
                diagnostics.append(f"{label} must be a boolean")
            elif field_type == "int" and (
                not isinstance(value, int) or isinstance(value, bool)
            ):
                diagnostics.append(f"{label} must be an integer")
            elif field_type == "string" and not isinstance(value, str):
                diagnostics.append(f"{label} must be a string")
            elif field_type == "list" and (
                not isinstance(value, list) or not all(isinstance(item, str) for item in value)
            ):
                diagnostics.append(f"{label} must be a string list")
            options = field.get("options") if isinstance(field, dict) else None
            if isinstance(options, list) and value not in options:
                diagnostics.append(f"{label} must be one of the configured options")
    return diagnostics
