import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config


class ConfigNormalizerTests(unittest.TestCase):
    def test_session_policy_state_settings_are_normalized(self):
        cfg = normalize_config(
            {
                "session_policy_state": {
                    "enabled": True,
                    "state_ttl_seconds": 7200,
                    "max_entries": 321,
                    "activity_log_limit": 25,
                }
            }
        )

        self.assertEqual(
            cfg.session_policy_state,
            {
                "enabled": True,
                "state_ttl_seconds": 7200,
                "max_entries": 321,
                "activity_log_limit": 25,
            },
        )

    def test_session_policy_state_migrates_legacy_ttl_and_rejects_bad_limits(self):
        migrated = normalize_config({"session_policy_state": {"ttl_seconds": 3600}})
        invalid = normalize_config(
            {
                "session_policy_state": {
                    "state_ttl_seconds": 1,
                    "max_entries": 0,
                    "activity_log_limit": 0,
                }
            }
        )

        self.assertEqual(migrated.session_policy_state["state_ttl_seconds"], 3600)
        self.assertEqual(invalid.session_policy_state["state_ttl_seconds"], 604800)
        self.assertEqual(invalid.session_policy_state["max_entries"], 500)
        self.assertEqual(invalid.session_policy_state["activity_log_limit"], 50)
        self.assertIn(
            "session_policy_state.state_ttl_seconds must be 0 or at least 60",
            " ".join(invalid.warnings),
        )

    def test_access_control_settings_are_normalized(self):
        cfg = normalize_config(
            {
                "access_control": {
                    "auto_blacklist_enabled": True,
                    "blacklist_duration_minutes": -1,
                    "blacklist_max_violations": 4,
                    "blacklist_message": "blocked by access control",
                }
            }
        )

        self.assertEqual(
            cfg.access_control,
            {
                "auto_blacklist_enabled": True,
                "blacklist_duration_minutes": -1,
                "blacklist_max_violations": 4,
                "blacklist_message": "blocked by access control",
            },
        )

    def test_invalid_access_control_duration_and_threshold_fall_back(self):
        cfg = normalize_config(
            {
                "access_control": {
                    "blacklist_duration_minutes": 0,
                    "blacklist_max_violations": 0,
                }
            }
        )

        self.assertEqual(cfg.access_control["blacklist_duration_minutes"], 60)
        self.assertEqual(cfg.access_control["blacklist_max_violations"], 3)
        self.assertIn(
            "access_control.blacklist_duration_minutes must be -1 or positive",
            " ".join(cfg.warnings),
        )

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

    def test_logic_gate_reports_disabled_reference_reason(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "rule1",
                            "enabled": False,
                        },
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "rule3",
                            "inputs": ["rule1"],
                        },
                    ]
                }
            }
        )

        warning_text = " ".join(cfg.warnings)
        self.assertIn("rule3.inputs references unavailable rule(s)", warning_text)
        self.assertIn("input_rail.rule1 is disabled", warning_text)

    def test_logic_gate_reports_duplicate_reference_reason(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "future_template",
                            "rule_id": "rule1",
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "rule1",
                        },
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "rule3",
                            "inputs": ["rule1"],
                        },
                    ]
                }
            }
        )

        warning_text = " ".join(cfg.warnings)
        self.assertIn("input_rail.rule1 is disabled/invalid", warning_text)
        self.assertIn("unsupported template future_template", warning_text)
        self.assertIn("duplicate rule_id rule1", warning_text)

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

    def test_output_retry_generation_is_valid_at_step_five(self):
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
        self.assertTrue(rule.valid)
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.config["action_on_hit"], "retry_generation")

    def test_sanitize_is_rejected_for_non_text_matching_templates(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "gate",
                            "action_on_hit": "sanitize",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertEqual(rule.config["action_on_hit"], "default")
        self.assertTrue(any("only supported" in warning for warning in rule.warnings))

    def test_retry_generation_is_accepted_as_a_rule_error_action(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "retry_error",
                            "keywords": ["risk"],
                            "action_on_error": "retry_generation",
                        }
                    ]
                }
            }
        )

        self.assertEqual(
            cfg.rails["input_rail"].rules[0].config["action_on_error"],
            "retry_generation",
        )

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

    def test_llm_review_rule_is_supported_and_normalized(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "llm_review",
                            "rule_id": "review",
                            "provider_id": "audit-provider",
                            "timeout_seconds": -1,
                            "audit_prompt": " Judge risk. ",
                            "action_on_hit": "block",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertTrue(rule.valid)
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.config["provider_id"], "audit-provider")
        self.assertEqual(rule.config["timeout_seconds"], 0.0)
        self.assertEqual(rule.config["audit_prompt"], "Judge risk.")

    def test_llm_review_empty_prompt_disables_rule(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "llm_review",
                            "rule_id": "review",
                            "audit_prompt": "",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertFalse(rule.valid)
        self.assertFalse(rule.enabled)
        self.assertIn("audit_prompt is empty", " ".join(rule.warnings))

    def test_rag_judge_rule_is_supported_and_normalized(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": [" policy ", ""],
                            "top_k": 0,
                            "min_score": -1,
                            "timeout_seconds": -1,
                            "action_on_hit": "block",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertTrue(rule.valid)
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.config["knowledge_bases"], ["policy"])
        self.assertEqual(rule.config["top_k"], 1)
        self.assertEqual(rule.config["min_score"], 0.0)
        self.assertEqual(rule.config["timeout_seconds"], 0.0)

    def test_rag_judge_empty_knowledge_bases_disables_rule(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": [],
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["input_rail"].rules[0]
        self.assertFalse(rule.valid)
        self.assertFalse(rule.enabled)
        self.assertIn("knowledge_bases is empty", " ".join(rule.warnings))

    def test_fallback_settings_supply_all_execution_rails(self):
        cfg = normalize_config(
            {
                "fallback_policy_settings": {
                    "default_llm_provider": "fallback-provider",
                    "max_text_chars": 42,
                    "default_action_on_hit": "observe",
                    "default_action_on_error": "record",
                    "enable_prompt_leakage_detector": False,
                },
                "input_rail": {"default_llm_provider": "ignored-old-value"},
            }
        )

        self.assertEqual(cfg.fallback_policy_settings["default_llm_provider"], "fallback-provider")
        self.assertEqual(
            cfg.rails["input_rail"].settings["default_llm_provider"],
            "fallback-provider",
        )
        self.assertEqual(
            cfg.rails["request_rail"].settings["default_llm_provider"],
            "fallback-provider",
        )
        self.assertEqual(
            cfg.rails["output_rail"].settings["default_llm_provider"],
            "fallback-provider",
        )
        self.assertEqual(cfg.rails["input_rail"].settings["max_text_chars"], 42)
        self.assertFalse(cfg.fallback_policy_settings["enable_prompt_leakage_detector"])

    def test_error_action_defaults_are_normalized(self):
        cfg = normalize_config(
            {
                "fallback_policy_settings": {
                    "default_action_on_error": "record",
                },
                "input_rail": {
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
                "fallback_policy_settings": {
                    "default_action_on_error": "explode",
                },
                "input_rail": {
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
        self.assertIn("fallback_policy_settings.default_action_on_error is invalid", " ".join(cfg.warnings))
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

    def test_debug_settings_are_normalized_independently(self):
        cfg = normalize_config(
            {
                "debug_settings": {
                    "enable_stats": False,
                    "stats_max_records": "8",
                    "logging": True,
                },
                "global_default_settings": {"debug": False},
            }
        )

        self.assertEqual(
            cfg.debug_settings,
            {"enable_stats": False, "stats_max_records": 8, "logging": True},
        )
        self.assertEqual(cfg.warnings, [])

    def test_invalid_debug_stats_limit_falls_back_to_default(self):
        cfg = normalize_config({"debug_settings": {"stats_max_records": 0}})

        self.assertEqual(cfg.debug_settings["stats_max_records"], 200)
        self.assertIn("stats_max_records must be positive", " ".join(cfg.warnings))

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
