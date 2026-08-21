import asyncio
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from snapshots import ConfigSnapshotManager
from policy_library import PolicyDefinition, PolicyLibrary, PolicyRuleBinding, RuleDefinition


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

        self.assertEqual(snapshot.policy_library.active_policy_id, "none")
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
                PolicyDefinition("none", "None", builtin=True),
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
        self.assertEqual(old_snapshot.policy_library.active_policy_id, "none")


if __name__ == "__main__":
    unittest.main()
