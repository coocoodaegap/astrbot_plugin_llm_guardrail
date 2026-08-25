import asyncio
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from snapshots import ConfigSnapshotManager, SYSTEM_FALLBACK_POLICY_ID
from fallback_graph import FallbackDetectorSpec, build_fallback_runtime_config
from policy_library import (
    PolicyComponent,
    PolicyDefinition,
    PolicyLibrary,
    PolicyRuleBinding,
    RuleDefinition,
)


class _Event:
    def __init__(self):
        self.extras = {}

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def set_extra(self, key, value):
        self.extras[key] = value


class _Adapter:
    @staticmethod
    def get_event_extra(event, key, default=None):
        return event.get_extra(key, default)

    @staticmethod
    def set_event_extra(event, key, value):
        event.set_extra(key, value)


class ConfigSnapshotManagerTests(unittest.TestCase):
    def test_bound_event_keeps_old_snapshot_after_publish(self):
        manager = ConfigSnapshotManager({"fallback_policy_settings": {"max_text_chars": 1}})
        event = _Event()
        old_snapshot = manager.bind_event(_Adapter(), event)

        result = asyncio.run(
            manager.publish({"fallback_policy_settings": {"max_text_chars": 2}}, expected_revision=0)
        )

        self.assertTrue(result.success)
        self.assertEqual(manager.current.revision, 1)
        self.assertEqual(manager.current.runtime_config.fallback_policy_settings["max_text_chars"], 2)
        self.assertIs(manager.bind_event(_Adapter(), event), old_snapshot)
        self.assertEqual(old_snapshot.runtime_config.fallback_policy_settings["max_text_chars"], 1)

    def test_system_setting_publish_updates_only_new_requests(self):
        manager = ConfigSnapshotManager(
            {"fallback_policy_settings": {"max_text_chars": 1}}
        )
        event = _Event()
        old_snapshot = manager.bind_event(_Adapter(), event)
        saved_settings = []

        result = asyncio.run(
            manager.publish_system_settings(
                {
                    "fallback_policy_settings": {"max_text_chars": 2},
                    "session_control": {},
                    "access_control": {
                        "auto_blacklist_enabled": True,
                        "blacklist_duration_minutes": -1,
                        "blacklist_max_violations": 2,
                        "blacklist_message": "blocked",
                    },
                    "session_policy_state": {
                        "enabled": True,
                        "state_ttl_seconds": 7200,
                        "max_entries": 123,
                        "activity_log_limit": 25,
                    },
                    "debug_settings": {"logging": True},
                },
                expected_revision=0,
                persist_settings=lambda settings: saved_settings.append(settings),
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(saved_settings[0]["fallback_policy_settings"]["max_text_chars"], 2)
        self.assertTrue(saved_settings[0]["debug_settings"]["logging"])
        self.assertEqual(manager.current.runtime_config.fallback_policy_settings["max_text_chars"], 2)
        self.assertTrue(manager.current.runtime_config.debug_settings["logging"])
        self.assertTrue(manager.current.runtime_config.access_control["auto_blacklist_enabled"])
        self.assertEqual(
            manager.current.runtime_config.session_policy_state["state_ttl_seconds"],
            7200,
        )
        self.assertIs(manager.bind_event(_Adapter(), event), old_snapshot)
        self.assertEqual(old_snapshot.runtime_config.fallback_policy_settings["max_text_chars"], 1)

    def test_fallback_graph_has_fixed_steps_and_registered_detectors(self):
        manager = ConfigSnapshotManager({})

        config = manager.current.fallback_runtime_config

        self.assertTrue(config.rails["input_rail"].enabled)
        self.assertFalse(config.rails["routing_rail"].enabled)
        self.assertFalse(config.rails["request_rail"].enabled)
        self.assertFalse(config.rails["prompt_rail"].enabled)
        self.assertTrue(config.rails["output_rail"].enabled)
        self.assertEqual(
            [node.node_id for node in config.rails["input_rail"].nodes],
            [
                "__fallback_length_anomaly",
                "__fallback_role_marker_spoofing",
                "__fallback_instruction_override",
                "__fallback_input_or",
                "__fallback_input_enforcement",
            ],
        )
        self.assertTrue(config.rails["input_rail"].nodes[0].enabled)
        self.assertTrue(config.rails["input_rail"].nodes[0].valid)
        self.assertEqual(
            config.rails["input_rail"].nodes[3].config["inputs"],
            ["__fallback_length_anomaly", "__fallback_role_marker_spoofing", "__fallback_instruction_override"],
        )
        self.assertNotIn("inputs is empty", " ".join(config.warnings))
        self.assertFalse(config.rails["output_rail"].nodes)

    def test_fallback_graph_keeps_access_control_system_settings(self):
        manager = ConfigSnapshotManager(
            {
                "access_control": {
                    "auto_blacklist_enabled": True,
                    "blacklist_duration_minutes": -1,
                    "blacklist_max_violations": 7,
                    "blacklist_message": "access blocked",
                }
            }
        )

        fallback = manager.current.fallback_runtime_config

        self.assertTrue(fallback.access_control["auto_blacklist_enabled"])
        self.assertEqual(fallback.access_control["blacklist_duration_minutes"], -1)
        self.assertEqual(fallback.access_control["blacklist_max_violations"], 7)

    def test_fallback_llm_review_is_controlled_by_system_settings_and_snapshot_safe(self):
        manager = ConfigSnapshotManager(
            {"fallback_policy_settings": {"enable_llm_review_in_fallback_policy": False}}
        )
        old_snapshot = manager.current

        result = asyncio.run(
            manager.publish(
                {"fallback_policy_settings": {"enable_llm_review_in_fallback_policy": True}},
                expected_revision=0,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [node.node_id for node in old_snapshot.fallback_runtime_config.rails["input_rail"].nodes],
            [
                "__fallback_length_anomaly",
                "__fallback_role_marker_spoofing",
                "__fallback_instruction_override",
                "__fallback_input_or",
                "__fallback_input_enforcement",
            ],
        )
        nodes = result.snapshot.fallback_runtime_config.rails["input_rail"].nodes
        self.assertEqual(
            [node.node_id for node in nodes],
            [
                "__fallback_length_anomaly",
                "__fallback_role_marker_spoofing",
                "__fallback_instruction_override",
                "__fallback_input_or",
                "__fallback_llm_review",
            ],
        )
        self.assertEqual(nodes[4].depend_on, "__fallback_input_or")

    def test_fallback_detector_registry_honors_its_system_switch(self):
        detector = FallbackDetectorSpec(
            "enable_test_detector",
            "__fallback_test_detector",
            "input_rail",
            "plain_keywords",
            {"keywords": ["risk"]},
        )

        disabled = build_fallback_runtime_config(
            {"enable_test_detector": False},
            implemented_detectors=(detector,),
        )
        enabled = build_fallback_runtime_config(
            {"enable_test_detector": True},
            implemented_detectors=(detector,),
        )

        self.assertEqual(
            [node.node_id for node in disabled.rails["input_rail"].nodes],
            ["__fallback_input_or", "__fallback_input_enforcement"],
        )
        self.assertEqual(
            [node.node_id for node in enabled.rails["input_rail"].nodes],
            ["__fallback_test_detector", "__fallback_input_or", "__fallback_input_enforcement"],
        )
        self.assertEqual(
            enabled.rails["input_rail"].nodes[1].config["inputs"],
            ["__fallback_test_detector"],
        )

    def test_conflicting_revision_does_not_publish(self):
        manager = ConfigSnapshotManager({})

        result = asyncio.run(
            manager.publish({}, expected_revision=2)
        )

        self.assertFalse(result.success)
        self.assertTrue(result.conflict)
        self.assertEqual(manager.current.revision, 0)
        self.assertEqual(manager.current.runtime_config.fallback_policy_settings["max_text_chars"], 6000)

    def test_persisted_snapshot_is_loaded_on_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config_snapshot.json"
            manager = ConfigSnapshotManager({"fallback_policy_settings": {"max_text_chars": 1}}, path)
            result = asyncio.run(
                manager.publish({"fallback_policy_settings": {"max_text_chars": 2}}, expected_revision=0)
            )

            restarted = ConfigSnapshotManager({"fallback_policy_settings": {"max_text_chars": 3}}, path)

        self.assertTrue(result.success)
        self.assertEqual(restarted.current.revision, 1)
        self.assertEqual(restarted.current.runtime_config.fallback_policy_settings["max_text_chars"], 3)
        self.assertTrue(path.with_suffix(".json.bak").exists() is False)

    def test_explicit_umo_policy_selection_persists_with_the_policy_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config_snapshot.json"
            manager = ConfigSnapshotManager({}, path)
            library = PolicyLibrary(
                policies=(PolicyDefinition("auto", "Policy named auto"),),
                active_policy_id="auto",
            )
            published = asyncio.run(manager.publish_policy_library(library, 0))
            selected = asyncio.run(
                manager.publish_umo_policy_selection(
                    "qq:group:1", "auto", published.snapshot.revision
                )
            )
            restarted = ConfigSnapshotManager({}, path)

        self.assertTrue(selected.success)
        self.assertEqual(
            restarted.current.policy_library.explicit_policy_id_for_umo("qq:group:1"),
            "auto",
        )

    def test_overview_has_no_raw_config(self):
        manager = ConfigSnapshotManager(
            {
                "fallback_policy_settings": {"max_text_chars": 100},
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                        }
                    ]
                },
            }
        )

        overview = manager.overview()

        self.assertNotIn("runtime_config", overview)
        self.assertEqual(overview["rails"]["input_rail"]["enabled_rules"], 0)

    def test_legacy_rule_list_is_not_a_configuration_source(self):
        manager = ConfigSnapshotManager(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "legacy_risk",
                            "keywords": ["secret"],
                        }
                    ]
                }
            }
        )

        snapshot = manager.current

        self.assertEqual(snapshot.policy_library.active_policy_id, "")
        self.assertEqual(snapshot.policy_library.rules, ())
        self.assertEqual(snapshot.runtime_config.rails["input_rail"].rules, [])

    def test_publish_policy_library_updates_only_new_requests(self):
        manager = ConfigSnapshotManager({})
        event = _Event()
        old_snapshot = manager.bind_event(_Adapter(), event)
        library = PolicyLibrary(
            rules=(
                RuleDefinition("risk", "plain_keywords", {"keywords": ["secret"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "input_policy",
                    "Input",
                    bindings=(PolicyRuleBinding("risk", "input_rail"),),
                ),
            ),
            active_policy_id="input_policy",
        )

        result = asyncio.run(manager.publish_policy_library(library, 0))

        self.assertTrue(result.success)
        self.assertEqual(manager.current.policy_library.active_policy_id, "input_policy")
        self.assertEqual(manager.current.runtime_config.rails["input_rail"].rules[0].rule_id, "risk")
        self.assertIs(manager.bind_event(_Adapter(), event), old_snapshot)
        self.assertEqual(old_snapshot.policy_library.active_policy_id, "")

    def test_policy_component_is_compiled_into_the_published_snapshot(self):
        manager = ConfigSnapshotManager({})
        library = PolicyLibrary(
            rules=(RuleDefinition("risk", "plain_keywords", {"keywords": ["secret"]}),),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "with_component",
                    "With component",
                    bindings=(PolicyRuleBinding("risk", "input_rail"),),
                    components=(
                        PolicyComponent(
                            "gate",
                            "logic_gate",
                            "input_rail",
                            config={"gate": "all", "inputs": ["risk"]},
                        ),
                    ),
                    node_order=("risk", "gate"),
                ),
            ),
            active_policy_id="with_component",
        )

        result = asyncio.run(manager.publish_policy_library(library, 0))

        self.assertTrue(result.success)
        rules = result.snapshot.runtime_config.rails["input_rail"].rules
        self.assertEqual([rule.rule_id for rule in rules], ["risk", "gate"])
        self.assertEqual(rules[1].template_key, "logic_gate")

    def test_existing_rule_template_cannot_be_changed(self):
        manager = ConfigSnapshotManager({})
        first = asyncio.run(
            manager.publish_rule_library(
                (RuleDefinition("risk", "plain_keywords", {"keywords": ["secret"]}),),
                expected_revision=0,
            )
        )
        changed = asyncio.run(
            manager.publish_rule_library(
                (RuleDefinition("risk", "regex_pattern", {"pattern": "secret"}),),
                expected_revision=1,
            )
        )

        self.assertTrue(first.success)
        self.assertFalse(changed.success)
        self.assertIn("template cannot change", changed.diagnostics[0])

    def test_legacy_default_policy_is_removed_when_publishing_snapshot(self):
        manager = ConfigSnapshotManager({})

        result = asyncio.run(
            manager.publish_policy_collection((), "_default", expected_revision=0)
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.snapshot.policy_library.get_policy("_default"))
        self.assertEqual(result.snapshot.policy_library.active_policy_id, "")

    def test_missing_or_invalid_default_pointer_is_cleared(self):
        manager = ConfigSnapshotManager(
            {
                "policy_library": {
                    "policies": [{"policy_id": "custom", "name": "Custom"}],
                    "active_policy_id": "missing",
                }
            }
        )

        self.assertEqual(manager.current.policy_library.active_policy_id, "")

    def test_snapshot_selects_policy_runtime_config_by_umo(self):
        manager = ConfigSnapshotManager({})
        library = PolicyLibrary(
            rules=(RuleDefinition("risk", "plain_keywords", {"keywords": ["secret"]}),),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "protected",
                    "Protected",
                    bindings=(PolicyRuleBinding("risk", "input_rail"),),
                    umo_list=("umo:protected",),
                ),
            ),
            active_policy_id="_default",
        )
        result = asyncio.run(manager.publish_policy_library(library, 0))

        policy_id, config = result.snapshot.runtime_config_for_umo("umo:protected")
        fallback_policy_id, fallback_config = result.snapshot.runtime_config_for_umo("umo:other")

        self.assertEqual(policy_id, "protected")
        self.assertEqual(config.rails["input_rail"].rules[0].rule_id, "risk")
        self.assertEqual(fallback_policy_id, SYSTEM_FALLBACK_POLICY_ID)
        self.assertEqual(
            [node.node_id for node in fallback_config.rails["input_rail"].nodes],
            [
                "__fallback_length_anomaly",
                "__fallback_role_marker_spoofing",
                "__fallback_instruction_override",
                "__fallback_input_or",
                "__fallback_input_enforcement",
            ],
        )

    def test_explicit_umo_selection_publishes_by_revision_and_clears_to_auto(self):
        manager = ConfigSnapshotManager({})
        library = PolicyLibrary(
            rules=(RuleDefinition("risk", "plain_keywords", {"keywords": ["secret"]}),),
            policies=(
                PolicyDefinition(
                    "matched",
                    "Matched",
                    bindings=(PolicyRuleBinding("risk", "input_rail"),),
                    umo_list=("umo:one",),
                ),
                PolicyDefinition("manual", "Manual"),
            ),
            active_policy_id="manual",
        )
        first = asyncio.run(manager.publish_policy_library(library, 0))
        selected = asyncio.run(
            manager.publish_umo_policy_selection(
                "umo:one", "manual", first.snapshot.revision
            )
        )

        selected_id, selected_config = selected.snapshot.runtime_config_for_umo("umo:one")
        cleared = asyncio.run(
            manager.publish_umo_policy_selection(
                "umo:one", None, selected.snapshot.revision
            )
        )
        automatic_id, automatic_config = cleared.snapshot.runtime_config_for_umo("umo:one")

        self.assertTrue(selected.success)
        self.assertEqual(selected_id, "manual")
        self.assertEqual(selected_config.rails["input_rail"].rules, [])
        self.assertTrue(cleared.success)
        self.assertEqual(automatic_id, "matched")
        self.assertEqual(automatic_config.rails["input_rail"].rules[0].rule_id, "risk")

    def test_missing_usable_policy_graph_selects_system_fallback(self):
        manager = ConfigSnapshotManager({})
        snapshot = replace(manager.current, policy_runtime_configs={})

        policy_id, config = snapshot.runtime_config_for_umo("umo:any")

        self.assertEqual(policy_id, SYSTEM_FALLBACK_POLICY_ID)
        self.assertIs(config, snapshot.fallback_runtime_config)
        self.assertEqual(
            [node.node_id for node in config.rails["input_rail"].nodes],
            [
                "__fallback_length_anomaly",
                "__fallback_role_marker_spoofing",
                "__fallback_instruction_override",
                "__fallback_input_or",
                "__fallback_input_enforcement",
            ],
        )

    def test_publish_rejects_dependency_target_that_normalizes_as_unavailable(self):
        manager = ConfigSnapshotManager({})
        library = PolicyLibrary(
            rules=(
                RuleDefinition("broken_regex", "regex_pattern", {"pattern": "["}),
                RuleDefinition("dependent", "plain_keywords", {"keywords": ["dependent"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "invalid_target",
                    "Invalid target",
                    bindings=(
                        PolicyRuleBinding("broken_regex", "input_rail"),
                        PolicyRuleBinding("dependent", "input_rail", depend_on="broken_regex"),
                    ),
                ),
            ),
            active_policy_id="invalid_target",
        )

        result = asyncio.run(manager.publish_policy_library(library, expected_revision=0))

        self.assertFalse(result.success)
        self.assertEqual(manager.current.revision, 0)
        self.assertTrue(any("depends on unavailable rule broken_regex" in item for item in result.diagnostics))

    def test_publish_rejects_dependency_target_in_a_disabled_step(self):
        manager = ConfigSnapshotManager({})
        library = PolicyLibrary(
            rules=(
                RuleDefinition("source", "plain_keywords", {"keywords": ["source"]}),
                RuleDefinition("dependent", "plain_keywords", {"keywords": ["dependent"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "disabled_step",
                    "Disabled step",
                    rail_settings={"input_rail": {"enabled": False}},
                    bindings=(
                        PolicyRuleBinding("source", "input_rail"),
                        PolicyRuleBinding("dependent", "request_rail", depend_on="source"),
                    ),
                ),
            ),
            active_policy_id="disabled_step",
        )

        result = asyncio.run(manager.publish_policy_library(library, expected_revision=0))

        self.assertFalse(result.success)
        self.assertEqual(manager.current.revision, 0)
        self.assertTrue(any("but Step input_rail is disabled" in item for item in result.diagnostics))


if __name__ == "__main__":
    unittest.main()
