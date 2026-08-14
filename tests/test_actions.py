import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from actions import resolve_action_plan
from config import normalize_config
from rules import evaluate_plain_keywords


class ActionPlanTests(unittest.TestCase):
    def test_input_default_action_resolves_to_block_input(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "default_action_on_hit": "block_input",
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

        plan = resolve_action_plan(rail, result)

        self.assertEqual(plan.action, "block_input")
        self.assertEqual(plan.target, "input")
        self.assertTrue(plan.stop_rail)

    def test_output_default_action_resolves_to_block_output(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "default_action_on_hit": "block_output",
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

        plan = resolve_action_plan(rail, result)

        self.assertEqual(plan.action, "block_output")
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

        plan = resolve_action_plan(rail, result)

        self.assertEqual(plan.action, "none")
        self.assertFalse(plan.block)
        self.assertFalse(plan.mutate_text)


if __name__ == "__main__":
    unittest.main()
