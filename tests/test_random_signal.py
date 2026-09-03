import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from components import evaluate_random_signal
from config import RAIL_NAMES, normalize_config
from policy_library import (
    PolicyComponent,
    PolicyDefinition,
    PolicyLibrary,
    compile_policy_to_runtime_config,
)
from rails import GuardrailPipeline


class _Event:
    def __init__(self):
        self.message_str = "ordinary text"
        self.unified_msg_origin = "test:message:session"
        self.extras = {}
        self.stopped = False

    def get_message_str(self):
        return self.message_str

    def is_private_chat(self):
        return False

    def is_admin(self):
        return False

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def stop_event(self):
        self.stopped = True


class _Request:
    def __init__(self):
        self.prompt = "ordinary text"
        self.system_prompt = ""
        self.extra_user_content_parts = []


class RandomSignalTests(unittest.TestCase):
    def test_probability_edges_and_payload_are_deterministic_at_boundaries(self):
        config = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "random_signal", "rule_id": "never", "probability": 0, "action_on_hit": "observe"},
                        {"__template_key": "random_signal", "rule_id": "always", "probability": 1, "action_on_hit": "observe"},
                    ]
                }
            }
        )
        never, always = config.rails["input_rail"].nodes

        with patch("components.random.random", return_value=0.42):
            never_result = evaluate_random_signal(never)
            always_result = evaluate_random_signal(always)

        self.assertFalse(never_result.matched)
        self.assertTrue(always_result.matched)
        self.assertEqual(never_result.action_on_hit, "observe")
        self.assertEqual(always_result.signal.payload["probability"], 1.0)
        self.assertEqual(always_result.signal.payload["roll"], 0.42)
        self.assertTrue(always_result.signal.payload["sampled"])

    def test_normalization_keeps_probability_and_allows_block_action(self):
        config = normalize_config(
            {
                "request_rail": {
                    "rule_list": [
                        {
                            "__template_key": "random_signal",
                            "rule_id": "sample",
                            "probability": 3,
                            "action_on_hit": "block",
                            "action_on_error": "record",
                        }
                    ]
                }
            }
        )
        node = config.rails["request_rail"].nodes[0]

        self.assertEqual(node.config["probability"], 0.5)
        self.assertEqual(node.config["action_on_hit"], "block")
        self.assertEqual(node.config["action_on_error"], "record")
        self.assertTrue(any("probability" in warning for warning in node.warnings))

    def test_component_compiles_for_every_rail(self):
        components = tuple(
            PolicyComponent(
                component_id=f"sample_{index}",
                component_type="random_signal",
                rail=rail,
                config={"probability": 0.25},
            )
            for index, rail in enumerate(RAIL_NAMES)
        )
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition("all_rails", "All rails", components=components),
            ),
            active_policy_id="all_rails",
        )

        raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        for rail in RAIL_NAMES:
            self.assertEqual(raw[rail]["rule_list"][0]["__template_key"], "random_signal")

    def test_pipeline_can_block_on_a_sampled_signal(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "sampled",
                    "Sampled",
                    components=(
                        PolicyComponent(
                            "sample",
                            "random_signal",
                            "input_rail",
                            action_on_hit="block",
                            config={"probability": 1.0},
                        ),
                    ),
                ),
            ),
            active_policy_id="sampled",
        )
        raw, validation = compile_policy_to_runtime_config({}, library)
        event = _Event()

        context = asyncio.run(
            GuardrailPipeline(normalize_config(raw)).run_message_input(event)
        )

        self.assertTrue(validation.valid)
        self.assertTrue(context.results["sample"].matched)
        self.assertEqual(context.results["sample"].action_on_hit, "block")
        self.assertTrue(context.input_blocked)
        self.assertTrue(event.stopped)

    def test_step_two_executes_an_unconditional_random_signal(self):
        config = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "random_signal",
                            "rule_id": "route_sample",
                            "probability": 1.0,
                        }
                    ]
                },
            }
        )

        context = asyncio.run(GuardrailPipeline(config).run_message(_Event()))

        self.assertIn("route_sample", context.results)
        self.assertTrue(context.results["route_sample"].executed)
        self.assertTrue(context.results["route_sample"].matched)

    def test_step_four_executes_signal_before_dependent_strengthening(self):
        config = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {"enabled": False},
                "request_rail": {"enabled": False},
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "random_signal",
                            "rule_id": "prompt_sample",
                            "probability": 1.0,
                        },
                        {
                            "__template_key": "strengthen_prompt",
                            "rule_id": "sampled_strengthen",
                            "depend_on": "prompt_sample",
                            "insertion_target": "system_prefix",
                            "insertion_text": "Sampled guardrail instruction.",
                        },
                    ]
                },
            }
        )
        request = _Request()

        context = asyncio.run(GuardrailPipeline(config).run_request(_Event(), request))

        self.assertTrue(context.results["prompt_sample"].executed)
        self.assertTrue(context.results["prompt_sample"].matched)
        self.assertTrue(context.results["sampled_strengthen"].matched)
        self.assertIn("Sampled guardrail instruction.", request.system_prompt)

    def test_step_two_and_step_four_accept_default_block_settings(self):
        config = normalize_config(
            {
                "routing_rail": {
                    "__policy_step_settings": {
                        "default_action_on_hit": "block",
                        "default_action_on_error": "record",
                        "block_message": "routing sampled block",
                    },
                    "rule_list": [
                        {
                            "__template_key": "random_signal",
                            "rule_id": "route_sample",
                            "probability": 1.0,
                        }
                    ],
                },
                "prompt_rail": {
                    "__policy_step_settings": {
                        "default_action_on_hit": "block",
                        "default_action_on_error": "record",
                        "block_message": "prompt sampled block",
                    },
                },
            }
        )

        route_rail = config.rails["routing_rail"]
        prompt_rail = config.rails["prompt_rail"]
        event = _Event()
        context = asyncio.run(GuardrailPipeline(config).run_message(event))

        self.assertEqual(route_rail.settings["default_action_on_hit"], "block")
        self.assertEqual(route_rail.settings["default_action_on_error"], "record")
        self.assertEqual(route_rail.settings["block_message"], "routing sampled block")
        self.assertEqual(prompt_rail.settings["default_action_on_hit"], "block")
        self.assertEqual(prompt_rail.settings["default_action_on_error"], "record")
        self.assertEqual(prompt_rail.settings["block_message"], "prompt sampled block")
        self.assertTrue(context.input_blocked)
        self.assertTrue(event.stopped)

    def test_step_four_default_hit_action_blocks_a_sampled_component(self):
        config = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {"enabled": False},
                "request_rail": {"enabled": False},
                "prompt_rail": {
                    "__policy_step_settings": {
                        "default_action_on_hit": "block",
                        "block_message": "prompt sampled block",
                    },
                    "rule_list": [
                        {
                            "__template_key": "random_signal",
                            "rule_id": "prompt_sample",
                            "probability": 1.0,
                        }
                    ],
                },
            }
        )
        event = _Event()

        context = asyncio.run(GuardrailPipeline(config).run_request(event, _Request()))

        self.assertTrue(context.results["prompt_sample"].matched)
        self.assertTrue(context.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(context.terminal_action["rail"], "prompt_rail")

    def test_step_two_default_error_action_blocks_a_failed_component(self):
        config = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {
                    "__policy_step_settings": {
                        "default_action_on_error": "block",
                        "block_message": "routing component error",
                    },
                    "rule_list": [
                        {
                            "__template_key": "random_signal",
                            "rule_id": "route_sample",
                            "probability": 0.5,
                        }
                    ],
                },
            }
        )
        event = _Event()

        with patch("components.random.random", side_effect=RuntimeError("test error")):
            context = asyncio.run(GuardrailPipeline(config).run_message(event))

        self.assertTrue(context.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(context.results["route_sample"].status, "failed")
        self.assertEqual(context.terminal_action["source_kind"], "error")


if __name__ == "__main__":
    unittest.main()
