import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from pages_api import GuardrailPagesApiMixin
from policy_library import PolicyLibrary
from access_control import AccessControlService
from session_lock import PrincipalLockManager, UmoLockManager
from session_policy_state import SessionPolicyStateService
from snapshots import ConfigSnapshotManager
from state import MemoryStateStore


class _Context:
    def __init__(self):
        self.routes = []
        self.providers = []

    def register_web_api(self, route, handler, methods, description):
        self.routes.append((route, handler, methods, description))

    def get_all_providers(self):
        return self.providers


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
            "/astrbot_plugin_llm_guardrail/get_access_control_records",
            "/astrbot_plugin_llm_guardrail/set_access_control_decision",
            "/astrbot_plugin_llm_guardrail/clear_access_control_decision",
            "/astrbot_plugin_llm_guardrail/get_session_policy_states",
            "/astrbot_plugin_llm_guardrail/get_session_policy_state",
            "/astrbot_plugin_llm_guardrail/get_rule_library",
            "/astrbot_plugin_llm_guardrail/save_rule_library",
            "/astrbot_plugin_llm_guardrail/get_policy_library",
            "/astrbot_plugin_llm_guardrail/save_policy_library",
        })
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/get_rule_library"][2], ["GET"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/save_policy_library"][2], ["POST"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/get_session_policy_states"][2], ["GET"])

    def test_system_settings_save_persists_config_then_publishes_snapshot(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            settings = asyncio.run(plugin._pages_get_system_settings())["settings"]
            settings["fallback_policy_settings"]["max_text_chars"] = 321
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
        self.assertTrue(result["settings"]["session_policy_state"]["enabled"])
        self.assertEqual(result["settings"]["session_policy_state"]["state_ttl_seconds"], 604800)
        self.assertFalse(result["settings"]["debug_settings"]["logging"])
        self.assertEqual(result["providers"], [{"id": "openai/test", "name": "Test OpenAI"}])

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
                        "sender_id": "42",
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
                        "sender_id": "42",
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

    def test_session_policy_state_pages_api_returns_not_found_for_unknown_umo(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request(args={"umo": "qq:missing"})):
                missing = asyncio.run(plugin._pages_get_session_policy_state())

        self.assertEqual(missing[1], 404)

    def test_rule_and_policy_libraries_are_returned_without_each_other(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            rules = asyncio.run(plugin._pages_get_rule_library())
            policies = asyncio.run(plugin._pages_get_policy_library())

        self.assertEqual(rules["revision"], 0)
        self.assertEqual(set(rules["rule_library"]), {"rules"})
        self.assertEqual(set(policies["policy_library"]), {"policies", "active_policy_id"})

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
