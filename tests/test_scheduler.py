import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from components import evaluate_logic_gate
from core import NodeSignal, RailContext, RuleScheduler, build_graph_index, make_result
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

    def test_logic_gate_dotted_inputs_collect_first_and_joined_payload_values(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "plain_keywords", "rule_id": "first"},
                        {"__template_key": "plain_keywords", "rule_id": "second"},
                        {"__template_key": "plain_keywords", "rule_id": "third"},
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "gate",
                            "gate": "all",
                            "inputs": ["first.sanitized?", "second.category", "!third.note"],
                            "value_item_template": "${source}=${value}",
                            "value_separator": " | ",
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        source_results = {
            "first": (True, {"sanitized": ""}),
            "second": (True, {"category": "review"}),
            "third": (False, {"note": "fallback"}),
        }

        def execute(rule, context):
            if rule.template_key == "logic_gate":
                return evaluate_logic_gate(rule, context)
            matched, payload = source_results[rule.rule_id]
            return make_result(
                rule,
                matched=matched,
                signal=NodeSignal(value=matched, truthy=matched, payload=payload),
            )

        RuleScheduler(build_graph_index(cfg)).run(rail, ctx, execute)

        result = ctx.results["gate"]
        self.assertTrue(result.matched)
        self.assertEqual(
            result.metadata["inputs"],
            {"first.sanitized?": True, "second.category": True, "!third.note": True},
        )
        self.assertEqual(result.signal.payload["first_value"], "")
        self.assertEqual(
            result.signal.payload["joined_string"],
            "first= | second=review | third=fallback",
        )
        self.assertNotIn("values", result.signal.payload)

    def test_logic_gate_dotted_input_rejects_missing_null_and_unmarked_empty_values(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "plain_keywords", "rule_id": "empty"},
                        {"__template_key": "plain_keywords", "rule_id": "null_value"},
                        {"__template_key": "plain_keywords", "rule_id": "missing"},
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "gate",
                            "gate": "any",
                            "inputs": ["empty.value", "null_value.value", "missing.value"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        source_results = {
            "empty": {"value": ""},
            "null_value": {"value": None},
            "missing": {},
        }

        def execute(rule, context):
            if rule.template_key == "logic_gate":
                return evaluate_logic_gate(rule, context)
            return make_result(
                rule,
                matched=True,
                signal=NodeSignal(value=True, truthy=True, payload=source_results[rule.rule_id]),
            )

        RuleScheduler(build_graph_index(cfg)).run(rail, ctx, execute)

        result = ctx.results["gate"]
        self.assertFalse(result.matched)
        self.assertEqual(
            result.metadata["inputs"],
            {"empty.value": False, "null_value.value": False, "missing.value": False},
        )
        self.assertEqual(result.signal.payload, {})

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

    def test_run_async_publishes_fast_dependency_before_slow_sibling_settles(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "a",
                            "priority": 10,
                            "keywords": ["a"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "b",
                            "priority": 20,
                            "keywords": ["b"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "child",
                            "priority": 1,
                            "depend_on": "?a",
                            "keywords": ["child"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        seed = make_result(
            rail.nodes[0],
            matched=True,
            signal=NodeSignal(
                value=True,
                truthy=True,
                payload={"nested": {"state": "original"}},
            ),
        )
        ctx.results["seed"] = seed

        async def scenario():
            a_started = asyncio.Event()
            b_started = asyncio.Event()
            release_a = asyncio.Event()
            release_b = asyncio.Event()
            child_started = asyncio.Event()
            seen_sibling = {"value": "unset"}
            settlements = []

            async def execute(rule, worker_context):
                if rule.rule_id == "a":
                    worker_context.results["seed"].signal.payload["nested"][
                        "state"
                    ] = "changed-by-a"
                    a_started.set()
                    await release_a.wait()
                elif rule.rule_id == "b":
                    seen_sibling["value"] = worker_context.results.get("a")
                    self.assertEqual(
                        worker_context.results["seed"].signal.payload["nested"][
                            "state"
                        ],
                        "original",
                    )
                    b_started.set()
                    await release_b.wait()
                else:
                    child_started.set()
                    self.assertIn("a", worker_context.results)
                return evaluate_text_rule(rule, worker_context, "a b child")

            async def settle_rail(executions, _context):
                settlements.append([rule.rule_id for rule, _execution in executions])

            task = asyncio.create_task(
                RuleScheduler(build_graph_index(cfg)).run_async(
                    rail,
                    ctx,
                    execute,
                    max_parallel_checks=2,
                    settlement_handler=settle_rail,
                )
            )
            await asyncio.wait_for(
                asyncio.gather(a_started.wait(), b_started.wait()), timeout=1
            )
            self.assertFalse(child_started.is_set())
            release_a.set()
            await asyncio.wait_for(child_started.wait(), timeout=1)
            self.assertFalse(release_b.is_set())
            release_b.set()
            await asyncio.wait_for(task, timeout=1)

            self.assertIsNone(seen_sibling["value"])
            self.assertEqual(
                ctx.results["seed"].signal.payload["nested"]["state"],
                "original",
            )
            self.assertEqual(settlements, [["child", "a", "b"]])

        asyncio.run(scenario())

    def test_terminal_result_closes_intake_before_waiting_rule_enters_executor(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "terminal",
                            "priority": 10,
                            "keywords": ["terminal"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "running",
                            "priority": 20,
                            "keywords": ["running"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "waiting",
                            "priority": 30,
                            "keywords": ["waiting"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        async def scenario():
            terminal_started = asyncio.Event()
            running_started = asyncio.Event()
            release_terminal = asyncio.Event()
            release_running = asyncio.Event()
            intake_closed = asyncio.Event()
            waiting_entered = False

            async def execute(rule, context):
                nonlocal waiting_entered
                if rule.rule_id == "terminal":
                    terminal_started.set()
                    await release_terminal.wait()
                elif rule.rule_id == "running":
                    running_started.set()
                    await release_running.wait()
                else:
                    waiting_entered = True
                return evaluate_text_rule(rule, context, "terminal running waiting")

            def close_intake(rule, execution, _context):
                if rule.rule_id == "terminal":
                    intake_closed.set()
                    return True
                return False

            task = asyncio.create_task(
                RuleScheduler(build_graph_index(cfg)).run_async(
                    rail,
                    ctx,
                    execute,
                    max_parallel_checks=2,
                    intake_close_predicate=close_intake,
                )
            )
            await asyncio.wait_for(
                asyncio.gather(terminal_started.wait(), running_started.wait()),
                timeout=1,
            )
            release_terminal.set()
            await asyncio.wait_for(intake_closed.wait(), timeout=1)
            self.assertFalse(waiting_entered)
            release_running.set()
            await asyncio.wait_for(task, timeout=1)

        asyncio.run(scenario())

        self.assertTrue(ctx.results["terminal"].matched)
        self.assertTrue(ctx.results["running"].matched)
        self.assertFalse(ctx.results["waiting"].executed)
        self.assertEqual(ctx.results["waiting"].skipped_reason, "rail_stopped")

    def test_run_async_streaming_commits_error_and_sibling_in_stable_order(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "slow_failure",
                            "priority": 10,
                            "keywords": ["slow_failure"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "fast_success",
                            "priority": 20,
                            "keywords": ["fast_success"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        async def execute(rule, context):
            if rule.rule_id == "slow_failure":
                await asyncio.sleep(0.01)
                raise RuntimeError("simulated")
            await asyncio.sleep(0)
            return evaluate_text_rule(rule, context, "fast_success")

        asyncio.run(
            RuleScheduler(build_graph_index(cfg)).run_async(
                rail,
                ctx,
                execute,
                error_handler=lambda rule, context, exc: make_result(
                    rule, matched=False, status="failed"
                ),
                max_parallel_checks=2,
                settlement_handler=lambda _executions, _context: None,
            )
        )

        self.assertEqual(list(ctx.results)[-2:], ["slow_failure", "fast_success"])
        self.assertEqual(ctx.results["slow_failure"].status, "failed")
        self.assertTrue(ctx.results["fast_success"].matched)

    def test_run_async_batch_isolates_node_cancelled_error_from_siblings(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "cancelled",
                            "priority": 10,
                            "keywords": ["cancelled"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "sibling",
                            "priority": 20,
                            "keywords": ["sibling"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        async def execute(rule, context):
            if rule.rule_id == "cancelled":
                raise asyncio.CancelledError("simulated node cancellation")
            return evaluate_text_rule(rule, context, "sibling")

        asyncio.run(
            RuleScheduler(build_graph_index(cfg)).run_async(
                rail,
                ctx,
                execute,
                error_handler=lambda rule, context, exc: make_result(
                    rule, matched=False, status="failed"
                ),
                max_parallel_checks=2,
            )
        )

        self.assertEqual(ctx.results["cancelled"].status, "failed")
        self.assertTrue(ctx.results["sibling"].matched)

    def test_streaming_max_one_refreshes_ready_heap_before_next_executor_entry(self):
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
                            "rule_id": "sibling",
                            "priority": 50,
                            "keywords": ["sibling"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "child",
                            "priority": 1,
                            "depend_on": "?source",
                            "keywords": ["child"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        order = []

        async def execute(rule, worker_context):
            order.append(rule.rule_id)
            return evaluate_text_rule(rule, worker_context, "source sibling child")

        async def settle_rail(_executions, _context):
            return None

        asyncio.run(
            RuleScheduler(build_graph_index(cfg)).run_async(
                rail,
                ctx,
                execute,
                max_parallel_checks=1,
                settlement_handler=settle_rail,
            )
        )

        self.assertEqual(order, ["source", "child", "sibling"])

    def test_streaming_external_slot_wait_does_not_block_local_ready_sibling(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "external",
                            "priority": 10,
                            "keywords": ["external"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "local",
                            "priority": 20,
                            "keywords": ["local"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        async def scenario():
            external_slots = asyncio.Semaphore(0)
            local_finished = asyncio.Event()
            external_started = asyncio.Event()

            async def execute(rule, context):
                if rule.rule_id == "external":
                    external_started.set()
                else:
                    local_finished.set()
                return evaluate_text_rule(rule, context, "external local")

            async def settle_rail(_executions, _context):
                return None

            task = asyncio.create_task(
                RuleScheduler(build_graph_index(cfg)).run_async(
                    rail,
                    ctx,
                    execute,
                    max_parallel_checks=1,
                    execution_semaphore=external_slots,
                    execution_semaphore_predicate=lambda rule: rule.rule_id
                    == "external",
                    settlement_handler=settle_rail,
                )
            )
            await asyncio.wait_for(local_finished.wait(), timeout=1)
            self.assertFalse(external_started.is_set())
            external_slots.release()
            await asyncio.wait_for(external_started.wait(), timeout=1)
            await asyncio.wait_for(task, timeout=1)

        asyncio.run(scenario())

        self.assertTrue(ctx.results["external"].matched)
        self.assertTrue(ctx.results["local"].matched)

    def test_streaming_predicate_error_cancels_started_siblings(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "fast",
                            "priority": 10,
                            "keywords": ["fast"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "slow",
                            "priority": 20,
                            "keywords": ["slow"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")

        async def scenario():
            slow_started = asyncio.Event()
            slow_cancelled = asyncio.Event()
            never = asyncio.Event()

            async def execute(rule, worker_context):
                if rule.rule_id == "fast":
                    await slow_started.wait()
                    return evaluate_text_rule(rule, worker_context, "fast")
                slow_started.set()
                try:
                    await never.wait()
                except asyncio.CancelledError:
                    slow_cancelled.set()
                    raise

            def explode(_rule, _execution, _context):
                raise RuntimeError("predicate boom")

            with self.assertRaisesRegex(RuntimeError, "predicate boom"):
                await RuleScheduler(build_graph_index(cfg)).run_async(
                    rail,
                    ctx,
                    execute,
                    max_parallel_checks=2,
                    intake_close_predicate=explode,
                )
            await asyncio.wait_for(slow_cancelled.wait(), timeout=1)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
