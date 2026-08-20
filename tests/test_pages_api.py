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

    def register_web_api(self, route, handler, methods, description):
        self.routes.append((route, handler, methods, description))


class _Plugin(GuardrailPagesApiMixin):
    PLUGIN_NAME = "astrbot_plugin_llm_guardrail"

    def __init__(self):
        self.context = _Context()
        self.snapshot_manager = ConfigSnapshotManager({"enabled": True})


class _Request:
    def __init__(self, payload):
        self.payload = payload

    async def get_json(self, force=True):
        return self.payload


class GuardrailPagesApiTests(unittest.TestCase):
    def test_registers_separate_rule_and_policy_routes(self):
        plugin = _Plugin()
        plugin._register_pages_web_api()
        routes = {item[0]: item for item in plugin.context.routes}

        self.assertEqual(set(routes), {
            "/astrbot_plugin_llm_guardrail/get_overview",
            "/astrbot_plugin_llm_guardrail/get_diagnostics",
            "/astrbot_plugin_llm_guardrail/get_rule_library",
            "/astrbot_plugin_llm_guardrail/save_rule_library",
            "/astrbot_plugin_llm_guardrail/get_policy_library",
            "/astrbot_plugin_llm_guardrail/save_policy_library",
        })
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/get_rule_library"][2], ["GET"])
        self.assertEqual(routes["/astrbot_plugin_llm_guardrail/save_policy_library"][2], ["POST"])

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
