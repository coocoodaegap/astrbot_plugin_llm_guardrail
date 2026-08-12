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


if __name__ == "__main__":
    unittest.main()
