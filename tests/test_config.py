import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config


class ConfigNormalizerTests(unittest.TestCase):
    def test_template_list_rules_are_normalized(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk_words",
                            "keywords": ["Secret"],
                            "keyword_weights": ["Secret:2"],
                            "threshold": 2,
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.rule_id, "risk_words")
        self.assertEqual(rule.config["_keyword_weight_map"]["secret"], 2.0)

    def test_duplicate_rule_id_disables_later_rule(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "plain_keywords", "rule_id": "same"},
                        {"__template_key": "plain_keywords", "rule_id": "same"},
                    ]
                }
            }
        )

        first, second = cfg.rails["input_rail"].rules
        self.assertTrue(first.valid)
        self.assertFalse(second.valid)
        self.assertIn("duplicate rule_id", " ".join(second.warnings))

    def test_regex_compile_error_disables_rule(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "regex_pattern",
                            "rule_id": "bad_regex",
                            "pattern": "[",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["output_rail"].rules[0]
        self.assertFalse(rule.valid)
        self.assertFalse(rule.enabled)

    def test_output_retry_generation_is_unsupported_in_p0(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "retry_rule",
                            "keywords": ["bad"],
                            "action_on_hit": "retry_generation",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["output_rail"].rules[0]
        self.assertFalse(rule.valid)
        self.assertFalse(rule.enabled)

    def test_request_rail_keyword_rule_is_normalized(self):
        cfg = normalize_config(
            {
                "request_rail": {
                    "enabled": True,
                    "default_action_on_hit": "block",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "request_risk",
                            "keywords": ["plugin-added"],
                            "action_on_hit": "observe",
                        }
                    ],
                }
            }
        )

        rail = cfg.rails["request_rail"]
        rule = rail.rules[0]
        self.assertTrue(rail.enabled)
        self.assertTrue(rule.valid)
        self.assertEqual(rule.rule_id, "request_risk")
        self.assertEqual(rail.settings["default_action_on_hit"], "block")

    def test_llm_provider_defaults_are_rail_scoped(self):
        cfg = normalize_config(
            {
                "global_default_settings": {
                    "default_llm_provider": "legacy-global-provider",
                },
                "input_rail": {"default_llm_provider": "input-provider"},
                "request_rail": {"default_llm_provider": "request-provider"},
                "output_rail": {"default_llm_provider": "output-provider"},
            }
        )

        self.assertEqual(
            cfg.global_default_settings["default_llm_provider"],
            "legacy-global-provider",
        )
        self.assertEqual(
            cfg.rails["input_rail"].settings["default_llm_provider"],
            "input-provider",
        )
        self.assertEqual(
            cfg.rails["request_rail"].settings["default_llm_provider"],
            "request-provider",
        )
        self.assertEqual(
            cfg.rails["output_rail"].settings["default_llm_provider"],
            "output-provider",
        )

    def test_legacy_risk_action_alias_is_normalized(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "legacy_action",
                            "keywords": ["secret"],
                            "action_on_hit": "sanitize_input",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertTrue(rule.valid)
        self.assertEqual(rule.config["action_on_hit"], "sanitize")

    def test_error_action_defaults_are_normalized(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "default_action_on_error": "record",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                            "action_on_error": "block",
                        }
                    ],
                }
            }
        )

        rail = cfg.rails["input_rail"]
        rule = rail.rules[0]
        self.assertEqual(rail.settings["default_action_on_error"], "record")
        self.assertEqual(rule.config["action_on_error"], "block")

    def test_invalid_error_actions_fall_back(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "default_action_on_error": "explode",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                            "action_on_error": "explode",
                        }
                    ],
                }
            }
        )

        rail = cfg.rails["input_rail"]
        rule = rail.rules[0]
        self.assertEqual(rail.settings["default_action_on_error"], "discard")
        self.assertEqual(rule.config["action_on_error"], "default")
        self.assertIn("default_action_on_error is invalid", " ".join(cfg.warnings))
        self.assertIn("risk.action_on_error is invalid", " ".join(rule.warnings))

    def test_session_control_normalizes_group_and_private_modes(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "enabled_or_block",
                    "group_chat_enabled": ["group-1"],
                    "private_chat_mode": "all_pass",
                    "private_chat_enabled": ["private-1"],
                }
            }
        )

        self.assertEqual(
            cfg.session_control,
            {
                "group_chat_mode": "enabled_or_block",
                "group_chat_enabled": ["group-1"],
                "private_chat_mode": "all_pass",
                "private_chat_enabled": ["private-1"],
            },
        )
        self.assertEqual(cfg.warnings, [])

    def test_session_control_accepts_all_block(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "all_block",
                    "private_chat_mode": "all_block",
                }
            }
        )

        self.assertEqual(cfg.session_control["group_chat_mode"], "all_block")
        self.assertEqual(cfg.session_control["private_chat_mode"], "all_block")
        self.assertEqual(cfg.warnings, [])

    def test_invalid_session_mode_falls_back_to_all_run(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "bad_mode",
                }
            }
        )

        self.assertEqual(cfg.session_control["group_chat_mode"], "all_run")
        self.assertIn("group_chat_mode is invalid", " ".join(cfg.warnings))


if __name__ == "__main__":
    unittest.main()
