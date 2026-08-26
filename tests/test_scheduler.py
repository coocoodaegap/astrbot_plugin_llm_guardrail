import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from components import evaluate_logic_gate
from core import RailContext, RuleScheduler, build_graph_index, make_result
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

    def test_newly_unlocked_higher_priority_rule_moves_to_heap_head(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "source",
                            "priority": 10,
                            "keywords": ["source"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "queued",
                            "priority": 50,
                            "keywords": ["queued"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "post",
                            "priority": 1,
                            "depend_on": "source",
                            "keywords": ["post"],
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
            return evaluate_text_rule(rule, context, "source queued post")

        RuleScheduler(build_graph_index(cfg)).run(rail, ctx, execute)

        self.assertEqual(order, ["source", "post", "queued"])

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

    def test_error_discard_does_not_unlock_dependencies(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "boom",
                            "keywords": ["boom"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "after",
                            "depend_on": "?boom",
                            "keywords": ["after"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        def execute(rule, context):
            if rule.rule_id == "boom":
                raise RuntimeError("simulated")
            return evaluate_text_rule(rule, context, "after")

        RuleScheduler(build_graph_index(cfg)).run(
            rail,
            ctx,
            execute,
            error_handler=lambda rule, context, exc: None,
        )

        self.assertNotIn("boom", ctx.results)
        self.assertFalse(ctx.results["after"].executed)
        self.assertEqual(ctx.results["after"].skipped_reason, "expired")

    def test_bruteforce_error_discard_expires_dependencies(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "boom",
                            "keywords": ["boom"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "after",
                            "depend_on": "?boom",
                            "keywords": ["after"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        def execute(rule, context):
            if rule.rule_id == "boom":
                raise RuntimeError("simulated")
            return evaluate_text_rule(rule, context, "after")

        RuleScheduler(strategy="bruteforce").run(
            rail,
            ctx,
            execute,
            error_handler=lambda rule, context, exc: None,
        )

        self.assertNotIn("boom", ctx.results)
        self.assertFalse(ctx.results["after"].executed)
        self.assertEqual(ctx.results["after"].skipped_reason, "expired")

    def test_error_record_unlocks_executed_dependencies(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "boom",
                            "keywords": ["boom"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "after",
                            "depend_on": "?boom",
                            "keywords": ["after"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        def execute(rule, context):
            if rule.rule_id == "boom":
                raise RuntimeError("simulated")
            return evaluate_text_rule(rule, context, "after")

        RuleScheduler(build_graph_index(cfg)).run(
            rail,
            ctx,
            execute,
            error_handler=lambda rule, context, exc: make_result(
                rule,
                matched=False,
                status="failed",
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            ),
        )

        self.assertTrue(ctx.results["boom"].executed)
        self.assertFalse(ctx.results["boom"].matched)
        self.assertEqual(ctx.results["boom"].status, "failed")
        self.assertTrue(ctx.results["after"].matched)

    def test_failed_dependency_is_explicit_and_not_not_matched(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "plain_keywords", "rule_id": "boom"},
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "on_failure",
                            "depend_on": "~boom",
                            "keywords": ["failure"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "on_non_match",
                            "depend_on": "!boom",
                            "keywords": ["non-match"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        def execute(rule, context):
            if rule.rule_id == "boom":
                raise RuntimeError("simulated")
            return evaluate_text_rule(rule, context, "failure non-match")

        RuleScheduler(build_graph_index(cfg)).run(
            rail,
            ctx,
            execute,
            error_handler=lambda rule, context, exc: make_result(
                rule, matched=False, status="failed"
            ),
        )

        self.assertEqual(ctx.results["boom"].status, "failed")
        self.assertTrue(ctx.results["on_failure"].matched)
        self.assertFalse(ctx.results["on_non_match"].executed)
        self.assertEqual(ctx.results["on_non_match"].skipped_reason, "dependency_failed")

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

    def test_logic_gate_inputs_support_not_and_executed_prefixes(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "a",
                            "priority": 10,
                            "keywords": ["missing"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "b",
                            "priority": 20,
                            "keywords": ["b"],
                        },
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "gate",
                            "priority": 1,
                            "gate": "all",
                            "inputs": ["!a", "?b"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        RuleScheduler(build_graph_index(cfg)).run(
            rail,
            ctx,
            lambda node, context: (
                evaluate_logic_gate(node, context)
                if node.template_key == "logic_gate"
                else evaluate_text_rule(node, context, "b")
            ),
        )

        self.assertTrue(ctx.results["gate"].matched)
        self.assertEqual(ctx.results["gate"].metadata["inputs"], {"!a": True, "?b": True})

    def test_logic_gate_input_supports_failed_prefix(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "plain_keywords", "rule_id": "boom"},
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "gate",
                            "gate": "all",
                            "inputs": ["~boom"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        def execute(rule, context):
            if rule.rule_id == "boom":
                raise RuntimeError("simulated")
            return evaluate_logic_gate(rule, context)

        RuleScheduler(build_graph_index(cfg)).run(
            rail,
            ctx,
            execute,
            error_handler=lambda rule, context, exc: make_result(
                rule, matched=False, status="failed"
            ),
        )

        self.assertTrue(ctx.results["gate"].matched)
        self.assertEqual(ctx.results["gate"].metadata["inputs"], {"~boom": True})

    def test_current_step_dependency_on_future_step_expires(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "early",
                            "depend_on": "future",
                            "keywords": ["early"],
                        }
                    ]
                },
                "request_rail": {
                    "enabled": True,
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "future",
                            "keywords": ["future"],
                        }
                    ],
                },
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        RuleScheduler(build_graph_index(cfg)).run(
            rail, ctx, lambda rule, context: evaluate_text_rule(rule, context, "early")
        )

        self.assertFalse(ctx.results["early"].executed)
        self.assertEqual(ctx.results["early"].skipped_reason, "expired")

    def test_graph_metrics_record_cross_step_edges(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "input_hint",
                            "keywords": ["hint"],
                        }
                    ]
                },
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "strengthen_prompt",
                            "rule_id": "prompt_hint",
                            "depend_on": "input_hint",
                            "insertion_text": "Be careful.",
                        }
                    ]
                },
            }
        )

        graph = build_graph_index(cfg)

        self.assertTrue(graph.metrics.has_cross_step_edges)
        self.assertEqual(graph.nodes["input_hint"].step, 1)
        self.assertEqual(graph.nodes["prompt_hint"].step, 4)

    def test_run_async_awaits_ready_rules_serially(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "a",
                            "priority": 1,
                            "keywords": ["a"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "b",
                            "priority": 2,
                            "keywords": ["b"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        order = []

        async def execute(rule, context):
            order.append(f"start:{rule.rule_id}")
            await asyncio.sleep(0.001)
            order.append(f"end:{rule.rule_id}")
            return evaluate_text_rule(rule, context, "a b")

        asyncio.run(RuleScheduler(build_graph_index(cfg)).run_async(rail, ctx, execute))

        self.assertEqual(order, ["start:a", "end:a", "start:b", "end:b"])
        self.assertTrue(ctx.results["a"].matched)
        self.assertTrue(ctx.results["b"].matched)


if __name__ == "__main__":
    unittest.main()
