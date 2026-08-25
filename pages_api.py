"""AstrBot Pages API for P1 guardrail status and separately saved libraries."""

from __future__ import annotations

import copy
import inspect
import json
import re
from pathlib import Path
from typing import Any

try:
    from quart import jsonify, request
except ImportError:  # pragma: no cover - allows isolated unit tests without AstrBot.
    request = None

    def jsonify(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

try:
    from .access_control import (
        MANUAL_BAN_REASON_CODES,
        MANUAL_PARDON_REASON_CODES,
        REASON_CODE_LABELS,
        make_principal_identity,
    )
    from .policy_library import PolicyDefinition, RuleDefinition
except ImportError:  # pragma: no cover - fallback for direct script loading
    from access_control import (
        MANUAL_BAN_REASON_CODES,
        MANUAL_PARDON_REASON_CODES,
        REASON_CODE_LABELS,
        make_principal_identity,
    )
    from policy_library import PolicyDefinition, RuleDefinition


class GuardrailPagesApiMixin:
    """Register the Guardrail Pages API surface."""

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
            ("get_access_control_records", self._pages_get_access_control_records, ["GET"], "List active input access-control records"),
            ("set_access_control_decision", self._pages_set_access_control_decision, ["POST"], "Create or replace an input access-control decision"),
            ("clear_access_control_decision", self._pages_clear_access_control_decision, ["POST"], "Clear an input access-control decision"),
            ("get_session_policy_states", self._pages_get_session_policy_states, ["GET"], "List observed UMO policy states"),
            ("get_session_policy_state", self._pages_get_session_policy_state, ["GET"], "Get one observed UMO policy state"),
            ("set_umo_policy_selection", self._pages_set_umo_policy_selection, ["POST"], "Set or clear one UMO explicit policy selection"),
            ("get_rag_experiences", self._pages_get_rag_experiences, ["GET"], "List RAG experience records"),
            ("get_rag_experience", self._pages_get_rag_experience, ["GET"], "Get one RAG experience record"),
            ("save_rag_experience", self._pages_save_rag_experience, ["POST"], "Save one RAG experience record"),
            ("delete_rag_experience", self._pages_delete_rag_experience, ["POST"], "Delete one local RAG experience record"),
            ("upload_rag_experience", self._pages_upload_rag_experience, ["POST"], "Upload one RAG experience record to its source knowledge base"),
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
        """Return all active AstrBot configuration groups for Pages."""

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
                    "access_control": dict(config.access_control),
                    "session_policy_state": dict(config.session_policy_state),
                    "debug_settings": dict(config.debug_settings),
                },
                "schema": _load_system_settings_schema(),
                "providers": self._pages_registered_chat_providers(),
            }
        )

    def _pages_registered_chat_providers(self) -> list[dict[str, str]]:
        """List registered chat Providers using AstrBot's public Context API."""

        getter = getattr(self.context, "get_all_providers", None)
        if not callable(getter):
            return []
        try:
            providers = getter()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return []
        if not isinstance(providers, (list, tuple)):
            return []

        options: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for provider in providers:
            metadata = None
            metadata_getter = getattr(provider, "meta", None)
            if callable(metadata_getter):
                try:
                    metadata = metadata_getter()
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    continue
            provider_id = str(
                getattr(metadata, "id", "") or getattr(provider, "id", "") or ""
            ).strip()
            if not provider_id or provider_id in seen_ids:
                continue
            seen_ids.add(provider_id)
            display_name = str(
                getattr(metadata, "name", "")
                or getattr(metadata, "display_name", "")
                or provider_id
            ).strip()
            options.append({"id": provider_id, "name": display_name})
        return sorted(options, key=lambda option: option["id"])

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
            for key in (
                "fallback_policy_settings",
                "session_control",
                "access_control",
                "session_policy_state",
                "debug_settings",
            )
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

    async def _pages_get_access_control_records(self):
        service = self._pages_access_control_service()
        if service is None:
            return self._pages_error("Input access-control service is unavailable", 503)
        result = await service.list_active_records()
        if not result.success:
            return self._pages_error("Input access-control state is unavailable", 503)
        return jsonify(
            {
                "success": True,
                "records": list(result.records),
                "reason_codes": {
                    "ban": [
                        {"code": code, "label": REASON_CODE_LABELS[code]}
                        for code in sorted(MANUAL_BAN_REASON_CODES)
                    ],
                    "pardon": [
                        {"code": code, "label": REASON_CODE_LABELS[code]}
                        for code in sorted(MANUAL_PARDON_REASON_CODES)
                    ],
                },
            }
        )

    async def _pages_set_access_control_decision(self):
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        try:
            principal = make_principal_identity(
                payload.get("platform_id"),
                payload.get("user_id"),
            )
        except (TypeError, ValueError) as exc:
            return self._pages_error("platform_id and user_id are required", 400, str(exc))

        duration_minutes = payload.get("duration_minutes")
        if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int):
            return self._pages_error("duration_minutes must be an integer")
        expected_revision = payload.get("expected_record_revision")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
        ):
            return self._pages_error("expected_record_revision must be an integer")

        service = self._pages_access_control_service()
        if service is None:
            return self._pages_error("Input access-control service is unavailable", 503)
        result = await service.set_manual_decision(
            principal,
            str(payload.get("decision", "")),
            duration_minutes,
            str(payload.get("reason_code", "")),
            expected_record_revision=expected_revision,
        )
        if result.conflict:
            return jsonify(
                {
                    "success": False,
                    "conflict": True,
                    "error": result.error,
                    "record": result.record,
                }
            ), 409
        if not result.success:
            return self._pages_error(result.error or "Access decision was not saved.")
        return jsonify({"success": True, "record": result.record})

    async def _pages_clear_access_control_decision(self):
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        try:
            principal = make_principal_identity(
                payload.get("platform_id"),
                payload.get("user_id"),
            )
        except (TypeError, ValueError) as exc:
            return self._pages_error("platform_id and user_id are required", 400, str(exc))
        expected_revision = payload.get("expected_record_revision")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            return self._pages_error("expected_record_revision must be an integer")

        service = self._pages_access_control_service()
        if service is None:
            return self._pages_error("Input access-control service is unavailable", 503)
        result = await service.clear_manual_decision(
            principal,
            expected_decision=str(payload.get("expected_decision", "")),
            expected_record_revision=expected_revision,
        )
        if result.conflict:
            return jsonify(
                {
                    "success": False,
                    "conflict": True,
                    "error": result.error,
                    "record": result.record,
                }
            ), 409
        if not result.success:
            return self._pages_error(result.error or "Access decision was not cleared.")
        return jsonify({"success": True, "record": result.record})

    def _pages_access_control_service(self):
        return getattr(self, "access_control", None)

    async def _pages_get_session_policy_states(self):
        """List P2-A monitor records without loading every signal payload."""

        service = self._pages_session_policy_state_service()
        if service is None:
            return self._pages_error("Session-policy monitor service is unavailable", 503)
        config = self.snapshot_manager.current.runtime_config
        library = self.snapshot_manager.current.policy_library
        result = await service.list_summaries(
            settings=config.session_policy_state,
            query=self._pages_query_value("query", ""),
            page=self._pages_query_value("page", 1),
            page_size=self._pages_query_value("page_size", 30),
            # An explicit selection is control-plane data, not an observed
            # runtime state.  It still needs a discoverable UMO detail page so
            # an administrator can revoke it before the first conversation.
            placeholder_umos=tuple(
                umo for umo, _policy_id in library.umo_policy_selections
            ),
        )
        if not result.success:
            return self._pages_error(
                result.warning or "Session-policy state is unavailable",
                503,
            )
        return jsonify(
            {
                "success": True,
                "monitoring_enabled": bool(config.session_policy_state.get("enabled", False)),
                "items": list(result.items),
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                },
            }
        )

    async def _pages_get_session_policy_state(self):
        """Return the full, bounded monitor state for a selected UMO."""

        service = self._pages_session_policy_state_service()
        if service is None:
            return self._pages_error("Session-policy monitor service is unavailable", 503)
        umo = self._pages_query_value("umo", "")
        if not str(umo or "").strip():
            return self._pages_error("umo is required", 400)
        config = self.snapshot_manager.current.runtime_config
        selection = self._pages_umo_policy_selection_payload(umo)
        result = await service.get_detail(umo, settings=config.session_policy_state)
        if not result.success:
            return self._pages_error(
                result.warning or "Session-policy state is unavailable",
                503,
            )
        if not result.found and not selection["explicit_policy_id"]:
            return self._pages_error("Session-policy state was not found", 404)
        record = result.record if result.found else service.empty_record(umo)
        return jsonify(
            {
                "success": True,
                "monitoring_enabled": bool(config.session_policy_state.get("enabled", False)),
                "record": record,
                "policy_selection": selection,
            }
        )

    def _pages_session_policy_state_service(self):
        return getattr(self, "session_policy_state", None)

    def _pages_umo_policy_selection_payload(self, umo: str) -> dict[str, Any]:
        """Describe persisted selection and current effective resolution for Pages."""

        library = self.snapshot_manager.current.policy_library
        resolution = library.resolve_usable_policy_for_umo(umo)
        normalized_umo = str(umo or "").strip()
        return {
            "explicit_policy_id": resolution.explicit_policy_id,
            "effective_policy_id": (
                resolution.policy.policy_id if resolution.policy is not None else ""
            ),
            "source": resolution.source,
            "available_policies": [
                {
                    "policy_id": policy.policy_id,
                    "name": policy.name,
                    "umo_matched": bool(
                        normalized_umo and normalized_umo in policy.umo_list
                    ),
                }
                for policy in library.usable_policies()
            ],
        }

    async def _pages_set_umo_policy_selection(self):
        """Set one explicit policy selection, or clear it with JSON null."""

        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        umo = payload.get("umo")
        policy_id = payload.get("policy_id")
        expected_revision = payload.get("expected_revision")
        if not isinstance(umo, str) or not umo.strip():
            return self._pages_error("umo must be a non-empty string")
        if policy_id is not None and not isinstance(policy_id, str):
            return self._pages_error("policy_id must be a string or null")
        if isinstance(policy_id, str) and not policy_id.strip():
            return self._pages_error("policy_id must not be empty; use null for auto")
        if not isinstance(expected_revision, int):
            return self._pages_error("expected_revision must be an integer")
        result = await self.snapshot_manager.publish_umo_policy_selection(
            umo,
            policy_id,
            expected_revision,
        )
        return self._pages_publish_response(result, "UMO policy selection")

    async def _pages_get_rag_experiences(self):
        """List only concise RAG experience summaries for the Page."""
        service = self._pages_rag_experience_service()
        if service is None:
            return self._pages_error("RAG experience service is unavailable", 503)
        result = await service.list_records(
            query=self._pages_query_value("query", ""),
            page=self._pages_query_value("page", 1),
            page_size=self._pages_query_value("page_size", 30),
        )
        if not result.success:
            return self._pages_error(result.warning or "RAG experience is unavailable", 503)
        return jsonify(
            {
                "success": True,
                "items": list(result.items),
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                },
            }
        )

    async def _pages_get_rag_experience(self):
        """Return one editable RAG experience record."""
        service = self._pages_rag_experience_service()
        if service is None:
            return self._pages_error("RAG experience service is unavailable", 503)
        record_id = self._pages_query_value("record_id", "")
        result = await service.get_record(record_id)
        if not result.success:
            return self._pages_error(result.warning or "RAG experience is unavailable", 503)
        if not result.found:
            return self._pages_error("RAG experience record was not found", 404)
        return jsonify({"success": True, "record": result.record})

    async def _pages_save_rag_experience(self):
        """Save only the user-editable title/content fields of one record."""
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        service = self._pages_rag_experience_service()
        if service is None:
            return self._pages_error("RAG experience service is unavailable", 503)
        result = await service.update_record(
            payload.get("record_id"),
            expected_revision=payload.get("expected_record_revision"),
            title=payload.get("title"),
            content=payload.get("content"),
        )
        if not result.success:
            return self._pages_error(result.warning or "RAG experience was not saved")
        if not result.found:
            return self._pages_error("RAG experience record was not found", 404)
        if result.conflict:
            return jsonify(
                {
                    "success": False,
                    "conflict": True,
                    "error": "RAG experience record was changed elsewhere.",
                    "record": result.record,
                }
            ), 409
        return jsonify({"success": True, "record": result.record})

    async def _pages_delete_rag_experience(self):
        """Delete a local experience record; never touch a KB document."""
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        service = self._pages_rag_experience_service()
        if service is None:
            return self._pages_error("RAG experience service is unavailable", 503)
        result = await service.delete_record(
            payload.get("record_id"),
            expected_revision=payload.get("expected_record_revision"),
        )
        if not result.success:
            return self._pages_error(result.warning or "RAG experience was not deleted")
        if not result.found:
            return self._pages_error("RAG experience record was not found", 404)
        if result.conflict:
            return jsonify(
                {
                    "success": False,
                    "conflict": True,
                    "error": "RAG experience record was changed elsewhere.",
                    "record": result.record,
                }
            ), 409
        return jsonify({"success": True})

    async def _pages_upload_rag_experience(self):
        """Upload edited Markdown to the highest-scoring evidence's source KB.

        A successful document belongs wholly to AstrBot's knowledge-base
        system.  This endpoint neither persists its document ID nor exposes
        later document-management operations.
        """
        payload = await self._pages_json_payload()
        if isinstance(payload, tuple):
            return payload
        service = self._pages_rag_experience_service()
        if service is None:
            return self._pages_error("RAG experience service is unavailable", 503)
        expected_revision = payload.get("expected_record_revision")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            return self._pages_error("expected_record_revision must be an integer")
        detail = await service.get_record(payload.get("record_id"))
        if not detail.success:
            return self._pages_error(detail.warning or "RAG experience is unavailable", 503)
        if not detail.found or not isinstance(detail.record, dict):
            return self._pages_error("RAG experience record was not found", 404)
        record = detail.record
        if record.get("record_revision") != expected_revision:
            return jsonify(
                {
                    "success": False,
                    "conflict": True,
                    "error": "RAG experience record was changed elsewhere.",
                    "record": record,
                }
            ), 409

        content = str(record.get("content", "") or "")
        if not content.strip():
            return self._pages_error("RAG experience content must not be empty")
        source_kb_id = str(record.get("source_kb_id", "") or "").strip()
        source_kb_name = str(record.get("source_kb_name", "") or "").strip()
        if not source_kb_id and not source_kb_name:
            return self._pages_error(
                "The highest-scoring evidence did not provide a source knowledge base"
            )

        try:
            helper = await self._pages_get_source_kb_helper(source_kb_id, source_kb_name)
            if helper is None:
                raise ValueError("source knowledge base is unavailable")
            document = await helper.upload_document(
                file_name=_rag_experience_file_name(record),
                file_content=content.encode("utf-8"),
                file_type="md",
            )
            doc_id = str(getattr(document, "doc_id", "") or "").strip()
            doc_name = str(getattr(document, "doc_name", "") or "").strip()
            chunk_count = getattr(document, "chunk_count", 0)
            if not doc_id or not doc_name or not isinstance(chunk_count, int) or chunk_count < 1:
                raise RuntimeError("AstrBot returned an incomplete upload receipt")
            verified = await helper.get_document(doc_id)
            chunks = await helper.get_chunks_by_doc_id(doc_id, limit=1)
            if verified is None or not chunks:
                raise RuntimeError("uploaded document could not be verified")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return self._pages_error(f"Knowledge-base upload failed: {exc}")
        except Exception as exc:
            logger.exception("[LLMGuardrail] unexpected RAG experience upload failure")
            return self._pages_error(
                f"Knowledge-base upload failed with {type(exc).__name__}; check server logs.",
                500,
            )

        return jsonify(
            {
                "success": True,
                "source_knowledge_base": source_kb_name or source_kb_id,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_count": chunk_count,
            }
        )

    def _pages_rag_experience_service(self):
        return getattr(self, "rag_experience", None)

    async def _pages_get_source_kb_helper(
        self,
        source_kb_id: str,
        source_kb_name: str,
    ) -> Any | None:
        manager = getattr(self.context, "kb_manager", None)
        id_getter = getattr(manager, "get_kb", None)
        if source_kb_id and callable(id_getter):
            value = id_getter(source_kb_id)
            helper = await value if inspect.isawaitable(value) else value
            if helper is not None:
                return helper
        name_getter = getattr(manager, "get_kb_by_name", None)
        if source_kb_name and callable(name_getter):
            value = name_getter(source_kb_name)
            helper = await value if inspect.isawaitable(value) else value
            if helper is not None:
                return helper
        return None

    @staticmethod
    def _pages_query_value(key: str, default: Any = "") -> Any:
        if request is None:
            return default
        args = getattr(request, "args", None)
        getter = getattr(args, "get", None)
        if not callable(getter):
            return default
        try:
            value = getter(key, default)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return default
        return default if value is None else value

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
                    "umo_policy_selections": dict(
                        snapshot.policy_library.umo_policy_selections
                    ),
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


def _rag_experience_file_name(record: dict[str, Any]) -> str:
    """Build a display-safe Markdown name without accepting a path from Pages."""
    title = str(record.get("title", "") or "").strip()
    record_id = str(record.get("record_id", "") or "").strip()
    stem = re.sub(r"[^\w.-]+", "_", title, flags=re.UNICODE).strip("._")
    if not stem:
        stem = f"rag_experience_{record_id[:16]}" or "rag_experience"
    if stem.lower().endswith(".md"):
        stem = stem[:-3].rstrip(".") or "rag_experience"
    return f"{stem[:100]}.md"


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
        for key in (
            "fallback_policy_settings",
            "session_control",
            "access_control",
            "session_policy_state",
            "debug_settings",
        )
        if isinstance(raw_schema.get(key), dict)
    }


def _validate_system_settings_payload(
    settings: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Reject incomplete, unknown, or type-invalid direct config writes."""

    diagnostics: list[str] = []
    expected_groups = {
        "fallback_policy_settings",
        "session_control",
        "access_control",
        "session_policy_state",
        "debug_settings",
    }
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
            elif field_type in {"string", "text"} and not isinstance(value, str):
                diagnostics.append(f"{label} must be a string")
            elif field_type == "list" and (
                not isinstance(value, list) or not all(isinstance(item, str) for item in value)
            ):
                diagnostics.append(f"{label} must be a string list")
            options = field.get("options") if isinstance(field, dict) else None
            if isinstance(options, list) and value not in options:
                diagnostics.append(f"{label} must be one of the configured options")
            if label == "access_control.blacklist_duration_minutes" and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or (value != -1 and value <= 0)
            ):
                diagnostics.append(f"{label} must be -1 or a positive integer")
            if label == "access_control.blacklist_max_violations" and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                diagnostics.append(f"{label} must be a positive integer")
            if label == "session_policy_state.state_ttl_seconds" and (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                or (0 < value < 60)
            ):
                diagnostics.append(f"{label} must be 0 or an integer of at least 60")
            if label in {
                "session_policy_state.max_entries",
                "session_policy_state.activity_log_limit",
            } and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                diagnostics.append(f"{label} must be a positive integer")
    return diagnostics
