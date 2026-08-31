import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from pages_api import GuardrailPagesApiMixin
from policy_library import PolicyDefinition, PolicyLibrary
from access_control import AccessControlService
from rag_experience import RagExperienceService
from session_lock import PrincipalLockManager, UmoLockManager
from session_policy_state import SessionPolicyStateService
from snapshots import ConfigSnapshotManager
from state import MemoryStateStore


class _Context:
    def __init__(self):
        self.routes = []
        self.providers = []
        self.kb_manager = _KBManager()

    def register_web_api(self, route, handler, methods, description):
        self.routes.append((route, handler, methods, description))

    def get_all_providers(self):
        return self.providers


class _KBHelper:
    def __init__(self):
        self.upload_calls = []
        self.documents = {}
        self.delete_calls = []

    async def upload_document(self, **kwargs):
        self.upload_calls.append(kwargs)
        document = type(
            "Document",
            (),
            {"doc_id": "doc-1", "doc_name": kwargs["file_name"], "chunk_count": 1},
        )()
        self.documents[document.doc_id] = document
        return document

    async def get_document(self, doc_id):
        return self.documents.get(doc_id)

    async def get_chunks_by_doc_id(self, doc_id, limit=1):
        return [{"chunk_id": "chunk-1"}] if doc_id in self.documents else []

    async def delete_document(self, doc_id):
        self.delete_calls.append(doc_id)


class _KBManager:
    def __init__(self):
        self.helper = _KBHelper()
        self.id_references = []
        self.name_references = []

    async def get_kb(self, reference):
        self.id_references.append(reference)
        return self.helper if reference == "kb-1" else None

    async def get_kb_by_name(self, reference):
        self.name_references.append(reference)
        return self.helper if reference == "source-kb" else None


class _ProviderMeta:
    def __init__(self, provider_id, name):
        self.id = provider_id
        self.name = name


class _Provider:
    def __init__(self, provider_id, name):
        self._metadata = _ProviderMeta(provider_id, name)

    def meta(self):
        return self._metadata


class _Plugin(GuardrailPagesApiMixin):
    PLUGIN_NAME = "astrbot_plugin_llm_guardrail"

    def __init__(self):
        self.context = _Context()
        self.config = _Config({})
        self.snapshot_manager = ConfigSnapshotManager(self.config)
        self.state_store = MemoryStateStore()
        self.access_control = AccessControlService(
            self.state_store,
            principal_locks=PrincipalLockManager(),
        )
        self.session_policy_state = SessionPolicyStateService(
            self.state_store,
            session_locks=UmoLockManager(),
        )
        self.rag_experience = RagExperienceService(self.state_store)


class _Request:
    def __init__(self, payload=None, args=None):
        self.payload = payload
        self.args = args or {}

    async def get_json(self, force=True):
        return self.payload


class _Config(dict):
    def __init__(self, payload):
        super().__init__(payload)
        self.save_count = 0

    def save_config(self):
        self.save_count += 1


class GuardrailPagesApiTests(unittest.TestCase):
    def test_registers_separate_rule_policy_and_system_setting_routes(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()
        routes = {item[0]: item for item in plugin.context.routes}

        self.assertEqual(set(routes), {
            "/astrbot_plugin_llm_guardrail/get_overview",
            "/astrbot_plugin_llm_guardrail/get_diagnostics",
            "/astrbot_plugin_llm_guardrail/get_system_settings",
            "/astrbot_plugin_llm_guardrail/save_system_settings",
            "/astrbot_plugin_llm_guardrail/get_registered_providers",
            "/astrbot_plugin_llm_guardrail/get_shared_constants",
            "/astrbot_plugin_llm_guardrail/save_shared_constants",
            "/astrbot_plugin_llm_guardrail/get_access_control_records",
            "/astrbot_plugin_llm_guardrail/set_access_control_decision",
            "/astrbot_plugin_llm_guardrail/clear_access_control_decision",
            "/astrbot_plugin_llm_guardrail/get_session_policy_states",
            "/astrbot_plugin_llm_guardrail/get_session_policy_state",
            "/astrbot_plugin_llm_guardrail/delete_session_policy_state",
            "/astrbot_plugin_llm_guardrail/set_umo_policy_selection",
            "/astrbot_plugin_llm_guardrail/get_rag_experiences",
            "/astrbot_plugin_llm_guardrail/get_rag_experience",
            "/astrbot_plugin_llm_guardrail/save_rag_experience",
            "/astrbot_plugin_llm_guardrail/delete_rag_experience",
            "/astrbot_plugin_llm_guardrail/upload_rag_experience",
            "/astrbot_plugin_llm_guardrail/get_rule_library",
            "/astrbot_plugin_llm_guardrail/save_rule_library",
            "/astrbot_plugin_llm_guardrail/get_policy_library",
            "/astrbot_plugin_llm_guardrail/save_policy_library",
            "/astrbot_plugin_llm_guardrail/preview_config_import",
            "/astrbot_plugin_llm_guardrail/import_config_package",
        })
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/get_rule_library"][2], ["GET"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/save_policy_library"][2], ["POST"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/get_session_policy_states"][2], ["GET"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/delete_session_policy_state"][2], ["POST"])

    def test_rag_experience_pages_edit_delete_and_upload_to_saved_source(self):
        plugin = _Plugin()
        captured = asyncio.run(
            plugin.rag_experience.capture_match(
                rail="input_rail",
                rule_id="rag_policy",
                content="Original matched content",
                evidence=[
                    {
                        "text": "Highest evidence",
                        "score": 0.95,
                        "metadata": {
                            "kb_id": "kb-1",
                            "doc_name": "source.md",
                        },
                    }
                ],
            )
        ).record
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request(args={"query": "", "page": "1"})):
                listed = asyncio.run(plugin._pages_get_rag_experiences())
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "record_id": captured["record_id"],
                        "expected_record_revision": captured["record_revision"],
                        "title": "Edited RAG experience",
                        "content": "Edited content for AstrBot KB",
                    }
                ),
            ):
                saved = asyncio.run(plugin._pages_save_rag_experience())
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "record_id": captured["record_id"],
                        "expected_record_revision": saved["record"]["record_revision"],
                    }
                ),
            ):
                uploaded = asyncio.run(plugin._pages_upload_rag_experience())

        self.assertTrue(listed["success"])
        self.assertNotIn("content", listed["items"][0])
        self.assertTrue(saved["success"])
        self.assertTrue(uploaded["success"])
        helper = plugin.context.kb_manager.helper
        self.assertEqual(plugin.context.kb_manager.id_references, ["kb-1"])
        self.assertEqual(plugin.context.kb_manager.name_references, [])
        self.assertEqual(
            helper.upload_calls[0]["file_content"], b"Edited content for AstrBot KB"
        )
        self.assertEqual(helper.delete_calls, [])

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "record_id": captured["record_id"],
                        "expected_record_revision": saved["record"]["record_revision"],
                    }
                ),
            ):
                deleted = asyncio.run(plugin._pages_delete_rag_experience())

        self.assertTrue(deleted["success"])
        self.assertEqual(helper.delete_calls, [])

    def test_rag_experience_upload_falls_back_to_source_name(self):
        plugin = _Plugin()
        captured = asyncio.run(
            plugin.rag_experience.capture_match(
                rail="input_rail",
                rule_id="rag_policy",
                content="Matched content",
                evidence=[
                    {
                        "text": "Highest evidence",
                        "score": 0.95,
                        "metadata": {"kb_name": "source-kb"},
                    }
                ],
            )
        ).record

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "record_id": captured["record_id"],
                        "expected_record_revision": captured["record_revision"],
                    }
                ),
            ):
                uploaded = asyncio.run(plugin._pages_upload_rag_experience())

        self.assertTrue(uploaded["success"])
        self.assertEqual(plugin.context.kb_manager.id_references, [])
        self.assertEqual(plugin.context.kb_manager.name_references, ["source-kb"])

    def test_rag_experience_upload_refuses_unknown_source(self):
        plugin = _Plugin()
        captured = asyncio.run(
            plugin.rag_experience.capture_match(
                rail="input_rail",
                rule_id="rag_policy",
                content="Matched content",
                evidence=[{"text": "scoreless", "score": None, "metadata": {}}],
            )
        ).record

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "record_id": captured["record_id"],
                        "expected_record_revision": captured["record_revision"],
                    }
                ),
            ):
                refused = asyncio.run(plugin._pages_upload_rag_experience())

        self.assertEqual(refused[1], 400)
        self.assertIn("source knowledge base", refused[0]["error"])

    def test_system_settings_save_persists_config_then_publishes_snapshot(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            settings = asyncio.run(plugin._pages_get_system_settings())["settings"]
            settings["fallback_policy_settings"]["max_text_chars"] = 321
            settings["fallback_policy_settings"]["max_retries"] = 2
            settings["session_control"]["group_chat_mode"] = "all_pass"
            settings["session_policy_state"]["state_ttl_seconds"] = 7200
            settings["debug_settings"]["logging"] = True
            with patch(
                "pages_api.request",
                _Request({"expected_revision": 0, "settings": settings}),
            ):
                saved = asyncio.run(plugin._pages_save_system_settings())

        self.assertTrue(saved["success"])
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(plugin.config.save_count, 1)
        self.assertEqual(plugin.config["fallback_policy_settings"]["max_text_chars"], 321)
        self.assertEqual(plugin.config["fallback_policy_settings"]["max_retries"], 2)
        self.assertNotIn("system_constants", plugin.config)
        self.assertEqual(
            plugin.snapshot_manager.current.runtime_config.rails["output_rail"].settings["max_retries"],
            2,
        )
        self.assertEqual(plugin.config["session_policy_state"]["state_ttl_seconds"], 7200)
        self.assertTrue(plugin.config["debug_settings"]["logging"])
        self.assertEqual(
            plugin.snapshot_manager.current.runtime_config.session_control[
                "group_chat_mode"
            ],
            "all_pass",
        )

    def test_system_settings_save_rejects_incomplete_payload(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request({"expected_revision": 0, "settings": {}}),
            ):
                result = asyncio.run(plugin._pages_save_system_settings())

        self.assertEqual(result[1], 400)
        self.assertEqual(plugin.config.save_count, 0)

    def test_shared_constants_reject_invalid_name(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request({"expected_revision": 0, "constants": {"not_allowed": "value"}}),
            ):
                result = asyncio.run(plugin._pages_save_shared_constants())

        self.assertEqual(result[1], 400)
        self.assertIn("uppercase letters", result[0]["detail"])

    def test_system_settings_returns_active_schema_and_normalized_values(self):
        plugin = _Plugin()
        plugin.context.providers = [_Provider("openai/test", "Test OpenAI")]
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            result = asyncio.run(plugin._pages_get_system_settings())

        self.assertEqual(
            set(result["settings"]),
            {
                "fallback_policy_settings",
                "session_control",
                "access_control",
                "session_policy_state",
                "debug_settings",
            },
        )
        self.assertEqual(set(result["schema"]), set(result["settings"]))
        self.assertEqual(result["settings"]["fallback_policy_settings"]["max_text_chars"], 6000)
        self.assertEqual(result["settings"]["session_control"]["group_chat_mode"], "all_run")
        self.assertEqual(result["settings"]["access_control"]["blacklist_duration_minutes"], 60)
        self.assertEqual(
            result["settings"]["access_control"]["blacklist_message_interval_minutes"],
            5,
        )
        self.assertTrue(result["settings"]["session_policy_state"]["enabled"])
        self.assertEqual(result["settings"]["session_policy_state"]["state_ttl_seconds"], 604800)
        self.assertFalse(result["settings"]["debug_settings"]["logging"])
        self.assertEqual(result["providers"], [{"id": "openai/test", "name": "Test OpenAI"}])

    def test_shared_constants_return_and_publish_without_astrbot_config_write(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            listed = asyncio.run(plugin._pages_get_shared_constants())
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "expected_revision": listed["revision"],
                        "constants": {"SAFETY_PREAMBLE": "Keep replies safe."},
                    }
                ),
            ):
                saved = asyncio.run(plugin._pages_save_shared_constants())

        self.assertEqual(listed["constants"], {})
        self.assertTrue(saved["success"])
        self.assertEqual(plugin.config.save_count, 0)
        self.assertEqual(
            plugin.snapshot_manager.current.runtime_config.system_constants,
            {"SAFETY_PREAMBLE": "Keep replies safe."},
        )

    def test_system_settings_rejects_invalid_access_control_duration(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            settings = asyncio.run(plugin._pages_get_system_settings())["settings"]
            settings["access_control"]["blacklist_duration_minutes"] = 0
            with patch(
                "pages_api.request",
                _Request({"expected_revision": 0, "settings": settings}),
            ):
                result = asyncio.run(plugin._pages_save_system_settings())

        self.assertEqual(result[1], 400)
        self.assertIn("must be -1 or a positive integer", result[0]["detail"])

    def test_system_settings_rejects_invalid_blacklist_message_interval(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            settings = asyncio.run(plugin._pages_get_system_settings())["settings"]
            settings["access_control"]["blacklist_message_interval_minutes"] = -2
            with patch(
                "pages_api.request",
                _Request({"expected_revision": 0, "settings": settings}),
            ):
                result = asyncio.run(plugin._pages_save_system_settings())

        self.assertEqual(result[1], 400)
        self.assertIn("must be -1, 0, or a positive integer", result[0]["detail"])

    def test_system_settings_rejects_invalid_session_policy_state_retention(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            settings = asyncio.run(plugin._pages_get_system_settings())["settings"]
            settings["session_policy_state"]["state_ttl_seconds"] = 1
            with patch(
                "pages_api.request",
                _Request({"expected_revision": 0, "settings": settings}),
            ):
                result = asyncio.run(plugin._pages_save_system_settings())

        self.assertEqual(result[1], 400)
        self.assertIn("must be 0 or an integer of at least 60", result[0]["detail"])

    def test_access_control_pages_api_supports_ban_pardon_and_versioned_clear(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "platform_id": "qq",
                        "user_id": "42",
                        "decision": "ban",
                        "duration_minutes": -1,
                        "reason_code": "manual_ban",
                    }
                ),
            ):
                ban = asyncio.run(plugin._pages_set_access_control_decision())
            listed = asyncio.run(plugin._pages_get_access_control_records())
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "platform_id": "qq",
                        "user_id": "42",
                        "expected_decision": "ban",
                        "expected_record_revision": ban["record"]["record_revision"],
                    }
                ),
            ):
                cleared = asyncio.run(plugin._pages_clear_access_control_decision())

        self.assertTrue(ban["success"])
        self.assertEqual(listed["records"][0]["decision"], "ban")
        self.assertTrue(cleared["success"])

    def test_session_policy_state_pages_api_lists_summaries_and_returns_detail(self):
        plugin = _Plugin()
        settings = {"enabled": True, "state_ttl_seconds": 0, "max_entries": 500, "activity_log_limit": 50}
        asyncio.run(
            plugin.session_policy_state.record_phase(
                "qq:group:1",
                run_id="run-a",
                policy_id="safe-chat",
                snapshot_revision=4,
                started_at=1,
                phase="message_input",
                outcome="blocked",
                terminal_action={"source_kind": "rule", "action": "block"},
                rail_outcomes={"input_rail": {"outcome": "blocked"}},
                signals=[{
                    "rail": "input_rail",
                    "node_id": "risk",
                    "user_node_id": "risk",
                    "template_key": "plain_keywords",
                    "signal": {"value": True, "truthy": True, "payload": {}},
                }],
                settings=settings,
            )
        )
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request(args={"query": "safe", "page": "1", "page_size": "30"})):
                listed = asyncio.run(plugin._pages_get_session_policy_states())
            with patch("pages_api.request", _Request(args={"umo": "qq:group:1"})):
                detail = asyncio.run(plugin._pages_get_session_policy_state())

        self.assertTrue(listed["success"])
        self.assertEqual(listed["pagination"]["total"], 1)
        self.assertNotIn("signals", listed["items"][0]["last_policy_result"])
        self.assertTrue(detail["success"])
        self.assertEqual(detail["record"]["last_policy_result"]["signals"][0]["node_id"], "risk")
        self.assertEqual(detail["policy_selection"]["source"], "system_fallback")

    def test_session_policy_state_pages_api_returns_not_found_for_unknown_umo(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request(args={"umo": "qq:missing"})):
                missing = asyncio.run(plugin._pages_get_session_policy_state())

        self.assertEqual(missing[1], 404)

    def test_pages_lists_selection_only_umo_and_returns_a_reversible_detail(self):
        plugin = _Plugin()
        library = PolicyLibrary(
            policies=(PolicyDefinition("manual", "Manual"),),
            active_policy_id="manual",
            umo_policy_selections=(("qq:private:never-spoke", "manual"),),
        )
        asyncio.run(plugin.snapshot_manager.publish_policy_library(library, 0))

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request(args={})):
                listed = asyncio.run(plugin._pages_get_session_policy_states())
            with patch(
                "pages_api.request", _Request(args={"umo": "qq:private:never-spoke"})
            ):
                detail = asyncio.run(plugin._pages_get_session_policy_state())

        self.assertEqual(listed["pagination"]["total"], 1)
        self.assertEqual(listed["items"][0]["umo"], "qq:private:never-spoke")
        self.assertEqual(detail["record"]["activity_count"] if "activity_count" in detail["record"] else 0, 0)
        self.assertIsNone(detail["record"]["last_policy_result"])
        self.assertEqual(detail["policy_selection"]["explicit_policy_id"], "manual")

    def test_pages_deletes_complete_umo_monitor_state(self):
        plugin = _Plugin()

        async def seed():
            return await plugin.session_policy_state.record_phase(
                "qq:group:1", run_id="run-a", policy_id="safe",
                snapshot_revision=1, started_at=1, phase="message_input",
                outcome="allowed", terminal_action=None, rail_outcomes={}, signals=[],
                settings=plugin.snapshot_manager.current.runtime_config.session_policy_state,
            )

        written = asyncio.run(seed())
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request({
                "umo": "qq:group:1",
                "expected_record_revision": written.record["record_revision"],
            })):
                deleted = asyncio.run(plugin._pages_delete_session_policy_state())

        self.assertTrue(deleted["success"])
        self.assertTrue(deleted["found"])
        detail = asyncio.run(plugin.session_policy_state.get_detail(
            "qq:group:1",
            settings=plugin.snapshot_manager.current.runtime_config.session_policy_state,
        ))
        self.assertFalse(detail.found)

    def test_pages_can_set_and_clear_an_explicit_umo_policy_selection(self):
        plugin = _Plugin()
        library = PolicyLibrary(
            policies=(PolicyDefinition("auto", "Automatic"),),
            active_policy_id="auto",
        )
        published = asyncio.run(
            plugin.snapshot_manager.publish_policy_library(library, 0)
        )

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "umo": "qq:group:1",
                        "policy_id": "auto",
                        "expected_revision": published.snapshot.revision,
                    }
                ),
            ):
                selected = asyncio.run(plugin._pages_set_umo_policy_selection())
            selected_policy_id = (
                plugin.snapshot_manager.current.policy_library.explicit_policy_id_for_umo(
                    "qq:group:1"
                )
            )
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "umo": "qq:group:1",
                        "policy_id": None,
                        "expected_revision": selected["revision"],
                    }
                ),
            ):
                cleared = asyncio.run(plugin._pages_set_umo_policy_selection())

        self.assertTrue(selected["success"])
        self.assertEqual(selected_policy_id, "auto")
        self.assertTrue(cleared["success"])
        self.assertEqual(
            plugin.snapshot_manager.current.policy_library.explicit_policy_id_for_umo(
                "qq:group:1"
            ),
            "",
        )

    def test_rule_and_policy_libraries_are_returned_without_each_other(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            rules = asyncio.run(plugin._pages_get_rule_library())
            policies = asyncio.run(plugin._pages_get_policy_library())

        self.assertEqual(rules["revision"], 0)
        self.assertEqual(set(rules["rule_library"]), {"rules"})
        self.assertEqual(
            set(policies["policy_library"]),
            {"policies", "active_policy_id", "umo_policy_selections"},
        )

    def test_rule_and_policy_edits_save_independently_as_new_snapshots(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()
        rules = {"rules": [{"rule_id": "risk", "template_key": "plain_keywords", "template_config": {"keywords": ["secret"]}}]}
        policies = {"policies": [{"policy_id": "_default", "name": "Default", "builtin": True}, {"policy_id": "input_policy", "name": "Input", "bindings": [{"rule_id": "risk", "rail": "input_rail"}]}], "active_policy_id": "input_policy"}
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request({"expected_revision": 0, "rule_library": rules})):
                saved_rules = asyncio.run(plugin._pages_save_rule_library())
            with patch("pages_api.request", _Request({"expected_revision": 1, "policy_library": policies})):
                saved_policies = asyncio.run(plugin._pages_save_policy_library())

        self.assertTrue(saved_rules["success"])
        self.assertEqual(saved_rules["revision"], 1)
        self.assertTrue(saved_policies["success"])
        self.assertEqual(saved_policies["revision"], 2)
        library = plugin.snapshot_manager.current.policy_library
        self.assertEqual(library.rules[0].rule_id, "risk")
        self.assertEqual(library.active_policy_id, "input_policy")

    def test_configuration_package_preview_and_copy_import_are_atomic(self):
        plugin = _Plugin()
        package = {
            "format_version": 1,
            "kind": "policies",
            "rules": [
                {
                    "rule_id": "risk",
                    "template_key": "plain_keywords",
                    "template_config": {"keywords": ["secret"]},
                }
            ],
            "policies": [
                {
                    "policy_id": "input_policy",
                    "name": "Imported policy",
                    "bindings": [{"rule_id": "risk", "rail": "input_rail"}],
                    "node_order": ["risk"],
                }
            ],
        }
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request({"package": package})):
                preview = asyncio.run(plugin._pages_preview_config_import())
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "package": package,
                        "conflict_mode": "copy",
                        "expected_revision": 0,
                    }
                ),
            ):
                imported = asyncio.run(plugin._pages_import_config_package())

        self.assertTrue(preview["success"])
        self.assertEqual(preview["preview"]["rule_conflicts"], [])
        self.assertTrue(imported["success"])
        self.assertEqual(imported["revision"], 1)
        library = plugin.snapshot_manager.current.policy_library
        self.assertEqual([rule.rule_id for rule in library.rules], ["risk"])
        self.assertEqual([policy.policy_id for policy in library.policies], ["input_policy"])

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request(
                    {
                        "package": package,
                        "conflict_mode": "copy",
                        "expected_revision": 1,
                    }
                ),
            ):
                copied = asyncio.run(plugin._pages_import_config_package())

        self.assertTrue(copied["success"])
        copied_library = plugin.snapshot_manager.current.policy_library
        self.assertEqual(
            [rule.rule_id for rule in copied_library.rules], ["risk", "risk_copy"]
        )
        copied_policy = copied_library.get_policy("input_policy_copy")
        self.assertIsNotNone(copied_policy)
        self.assertEqual(copied_policy.bindings[0].rule_id, "risk_copy")

    def test_configuration_package_rejects_policy_without_packaged_rule(self):
        plugin = _Plugin()
        package = {
            "format_version": 1,
            "kind": "policies",
            "rules": [],
            "policies": [
                {
                    "policy_id": "input_policy",
                    "name": "Broken policy",
                    "bindings": [{"rule_id": "missing", "rail": "input_rail"}],
                }
            ],
        }
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request({"package": package})):
                rejected = asyncio.run(plugin._pages_preview_config_import())

        self.assertEqual(rejected[1], 400)
        self.assertIn("missing packaged rules", rejected[0]["detail"])

    def test_rule_deletion_is_rejected_when_a_policy_uses_it(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()
        library = {"rules": [{"rule_id": "risk", "template_key": "plain_keywords"}], "policies": [{"policy_id": "_default", "name": "Default", "builtin": True}, {"policy_id": "active", "name": "Active", "bindings": [{"rule_id": "risk", "rail": "input_rail"}]}], "active_policy_id": "active"}
        asyncio.run(plugin.snapshot_manager.publish_policy_library(PolicyLibrary.from_dict(library), 0))

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request({"expected_revision": 1, "rule_library": {"rules": []}})):
                rejected = asyncio.run(plugin._pages_save_rule_library())

        self.assertEqual(rejected[1], 400)
        self.assertIn("references missing rule risk", rejected[0]["detail"])

    def test_rule_library_rejects_policy_component_templates(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch(
                "pages_api.request",
                _Request({
                    "expected_revision": 0,
                    "rule_library": {
                        "rules": [{"rule_id": "gate", "template_key": "logic_gate"}],
                    },
                }),
            ):
                rejected = asyncio.run(plugin._pages_save_rule_library())

        self.assertEqual(rejected[1], 400)
        self.assertIn("policy component types", rejected[0]["detail"])


if __name__ == "__main__":
    unittest.main()
