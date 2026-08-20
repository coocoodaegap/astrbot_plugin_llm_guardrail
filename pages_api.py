"""AstrBot Pages API for P1 guardrail status and separately saved libraries."""

from __future__ import annotations

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
