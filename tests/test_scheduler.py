import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from core import RailContext, RuleScheduler
from rules import evaluate_text_rule


class SchedulerTests(unittest.TestCase):
    def test_depend_on_executes_after_dependency(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "first",
                            "priority": 10,
                            "keywords": ["first"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "second",
                            "priority": 1,
                            "depend_on": "first",
                            "keywords": ["second"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        order = []

        def execute(rule, context):
            order.append(rule.rule_id)
            return evaluate_text_rule(rule, context, "first second")

        RuleScheduler().run(rail, ctx, execute)

        self.assertEqual(order, ["first", "second"])
        self.assertTrue(ctx.results["second"].matched)

    def test_not_matched_dependency(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "first",
                            "keywords": ["missing"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "second",
                            "depend_on": "!first",
                            "keywords": ["second"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        RuleScheduler().run(
            rail, ctx, lambda rule, context: evaluate_text_rule(rule, context, "second")
        )

        self.assertFalse(ctx.results["first"].matched)
        self.assertTrue(ctx.results["second"].matched)

    def test_dependency_not_satisfied_skips_rule(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "first",
                            "keywords": ["first"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "second",
                            "depend_on": "!first",
                            "keywords": ["second"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        RuleScheduler().run(
            rail,
            ctx,
            lambda rule, context: evaluate_text_rule(rule, context, "first second"),
        )

        self.assertFalse(ctx.results["second"].executed)
        self.assertEqual(ctx.results["second"].skipped_reason, "dependency_not_satisfied")

    def test_cyclic_dependency_is_skipped(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "a",
                            "depend_on": "b",
                            "keywords": ["a"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "b",
                            "depend_on": "a",
                            "keywords": ["b"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        RuleScheduler().run(
            rail, ctx, lambda rule, context: evaluate_text_rule(rule, context, "a b")
        )

        self.assertEqual(ctx.results["a"].skipped_reason, "cyclic_dependency")
        self.assertEqual(ctx.results["b"].skipped_reason, "cyclic_dependency")


if __name__ == "__main__":
    unittest.main()
