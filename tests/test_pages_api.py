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
from snapshots import ConfigSnapshotManager


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


class _Request:
    def __init__(self, payload):
        self.payload = payload

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
            "/astrbot_plugin_llm_guardrail/get_rule_library",
            "/astrbot_plugin_llm_guardrail/save_rule_library",
            "/astrbot_plugin_llm_guardrail/get_policy_library",
            "/astrbot_plugin_llm_guardrail/save_policy_library",
        })
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/get_rule_library"][2], ["GET"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/save_policy_library"][2], ["POST"])

    def test_system_settings_save_persists_config_then_publishes_snapshot(self):
        plugin = _Plugin()
        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            settings = asyncio.run(plugin._pages_get_system_settings())["settings"]
            settings["fallback_policy_settings"]["max_text_chars"] = 321
            settings["session_control"]["group_chat_mode"] = "all_pass"
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
            {"fallback_policy_settings", "session_control", "debug_settings"},
        )
        self.assertEqual(set(result["schema"]), set(result["settings"]))
        self.assertEqual(result["settings"]["fallback_policy_settings"]["max_text_chars"], 6000)
        self.assertEqual(result["settings"]["session_control"]["group_chat_mode"], "all_run")
        self.assertFalse(result["settings"]["debug_settings"]["logging"])
        self.assertEqual(result["providers"], [{"id": "openai/test", "name": "Test OpenAI"}])

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
        policies = {"policies": [{"policy_id": "none", "name": "None", "builtin": True}, {"policy_id": "input_policy", "name": "Input", "bindings": [{"rule_id": "risk", "rail": "input_rail"}]}], "active_policy_id": "input_policy"}
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
        library = {"rules": [{"rule_id": "risk", "template_key": "plain_keywords"}], "policies": [{"policy_id": "none", "name": "None", "builtin": True}, {"policy_id": "active", "name": "Active", "bindings": [{"rule_id": "risk", "rail": "input_rail"}]}], "active_policy_id": "active"}
        asyncio.run(plugin.snapshot_manager.publish_policy_library(PolicyLibrary.from_dict(library), 0))

        with patch("pages_api.jsonify", side_effect=lambda payload: payload):
            with patch("pages_api.request", _Request({"expected_revision": 1, "rule_library": {"rules": []}})):
                rejected = asyncio.run(plugin._pages_save_rule_library())

        self.assertEqual(rejected[1], 400)
        self.assertIn("references missing rule risk", rejected[0]["detail"])


if __name__ == "__main__":
    unittest.main()
