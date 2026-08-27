import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from actions import resolve_error_action_plan, resolve_hit_action_plan
from config import normalize_config
from rules import evaluate_plain_keywords


class HitActionPlanTests(unittest.TestCase):
    def test_input_default_action_resolves_to_block_targeting_input(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "default_action_on_hit": "block",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                        }
                    ],
                }
            }
        )
        rail = cfg.rails["input_rail"]
        result = evaluate_plain_keywords(rail.rules[0], "risk")

        plan = resolve_hit_action_plan(rail, result)

        self.assertEqual(plan.action, "block")
        self.assertEqual(plan.target, "input")
        self.assertTrue(plan.stop_rail)

    def test_output_default_action_resolves_to_block_targeting_output(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "default_action_on_hit": "block",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                        }
                    ],
                }
            }
        )
        rail = cfg.rails["output_rail"]
        result = evaluate_plain_keywords(rail.rules[0], "risk")

        plan = resolve_hit_action_plan(rail, result)

        self.assertEqual(plan.action, "block")
        self.assertEqual(plan.target, "output")
        self.assertTrue(plan.stop_rail)

    def test_unmatched_result_resolves_to_none(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                        }
                    ],
                }
            }
        )
        rail = cfg.rails["input_rail"]
        result = evaluate_plain_keywords(rail.rules[0], "safe")

        plan = resolve_hit_action_plan(rail, result)

        self.assertEqual(plan.action, "none")
        self.assertFalse(plan.block)
        self.assertFalse(plan.mutate_text)

    def test_retry_generation_outside_step_five_uses_the_step_default(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "retry",
                            "keywords": ["risk"],
                            "action_on_hit": "retry_generation",
                        }
                    ]
                }
            }
        )

        plan = resolve_hit_action_plan(
            cfg.rails["input_rail"],
            evaluate_plain_keywords(cfg.rails["input_rail"].rules[0], "risk"),
        )

        self.assertEqual(plan.action, "block")
        self.assertTrue(plan.block)

    def test_output_retry_generation_hit_action_stops_for_local_retry(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "retry",
                            "keywords": ["risk"],
                            "action_on_hit": "retry_generation",
                        }
                    ]
                }
            }
        )

        plan = resolve_hit_action_plan(
            cfg.rails["output_rail"],
            evaluate_plain_keywords(cfg.rails["output_rail"].rules[0], "risk"),
        )

        self.assertEqual(plan.action, "retry_generation")
        self.assertEqual(plan.target, "output")
        self.assertTrue(plan.stop_rail)
        self.assertFalse(plan.block)


class ErrorActionPlanTests(unittest.TestCase):
    def test_input_default_error_action_targets_input_when_blocking(self):
        cfg = normalize_config(
            {
                "fallback_policy_settings": {"default_action_on_error": "block"},
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                        }
                    ],
                }
            }
        )
        rail = cfg.rails["input_rail"]

        plan = resolve_error_action_plan(rail, "risk", "default")

        self.assertEqual(plan.action, "block")
        self.assertEqual(plan.target, "input")
        self.assertTrue(plan.block)

    def test_output_error_record_has_no_mutation_target(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["risk"],
                        }
                    ],
                }
            }
        )
        rail = cfg.rails["output_rail"]

        plan = resolve_error_action_plan(rail, "risk", "record")

        self.assertEqual(plan.action, "record")
        self.assertEqual(plan.target, "none")
        self.assertTrue(plan.record)
        self.assertFalse(plan.block)

    def test_legacy_retry_generation_error_action_uses_the_step_default(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "retry",
                            "keywords": ["risk"],
                            "action_on_error": "retry_generation",
                        }
                    ]
                }
            }
        )

        rule = cfg.rails["output_rail"].rules[0]
        self.assertEqual(rule.config["action_on_error"], "default")

        plan = resolve_error_action_plan(
            cfg.rails["output_rail"], "retry", "retry_generation"
        )

        self.assertEqual(plan.action, "discard")
        self.assertTrue(plan.discard)
        self.assertFalse(plan.block)


if __name__ == "__main__":
    unittest.main()
