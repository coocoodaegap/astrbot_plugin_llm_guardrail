import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from components import evaluate_request_entry_detector
from config import normalize_config
from core import RailContext
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


class RequestEntryDetectorTests(unittest.TestCase):
    @staticmethod
    def _node(**overrides):
        raw = {
            "__template_key": "request_entry_detector",
            "rule_id": "entry",
            "match_llm_request": False,
            "match_agent_reset": True,
            "action_on_hit": "observe",
            **overrides,
        }
        return normalize_config(
            {"request_rail": {"rule_list": [raw]}}
        ).rails["request_rail"].nodes[0]

    @staticmethod
    def _context(entry):
        return RailContext(
            event=_Event(),
            request=_Request(),
            response=None,
            umo="test:message:session",
            original_input="ordinary text",
            current_input="ordinary text",
            current_output="",
            request_entry=entry,
        )

    def test_boolean_selections_and_unavailable_payload(self):
        cases = (
            ({"match_llm_request": True, "match_agent_reset": False}, "llm_request", True, ["llm_request"]),
            ({"match_llm_request": False, "match_agent_reset": True}, "agent_reset", True, ["agent_reset"]),
            ({"match_llm_request": True, "match_agent_reset": True}, "agent_reset", True, ["llm_request", "agent_reset"]),
            ({"match_llm_request": False, "match_agent_reset": False}, "agent_reset", False, []),
            ({"match_llm_request": True, "match_agent_reset": True}, "unknown", False, ["llm_request", "agent_reset"]),
        )
        for config, entry, expected, selected in cases:
            with self.subTest(config=config, entry=entry):
                result = evaluate_request_entry_detector(
                    self._node(**config), self._context(entry)
                )
                self.assertEqual(result.matched, expected)
                self.assertEqual(result.signal.value, expected)
                self.assertEqual(result.signal.payload["selected_entries"], selected)
                self.assertEqual(result.signal.payload["score"], 100 if expected else 0)
                self.assertEqual(
                    result.signal.payload["entry_available"],
                    entry in {"llm_request", "agent_reset"},
                )
                if entry == "unknown":
                    self.assertEqual(result.signal.payload["entry"], "unavailable")

    def test_defaults_to_agent_reset_observation(self):
        node = normalize_config(
            {
                "request_rail": {
                    "rule_list": [
                        {
                            "__template_key": "request_entry_detector",
                            "rule_id": "entry",
                        }
                    ]
                }
            }
        ).rails["request_rail"].nodes[0]

        self.assertFalse(node.config["match_llm_request"])
        self.assertTrue(node.config["match_agent_reset"])
        self.assertEqual(node.config["action_on_hit"], "observe")

    def test_component_compiles_only_for_step_three(self):
        valid_library = PolicyLibrary(
            policies=(
                PolicyDefinition(
                    "entry_policy",
                    "Entry policy",
                    components=(
                        PolicyComponent(
                            "entry",
                            "request_entry_detector",
                            "request_rail",
                            config={"match_agent_reset": True},
                        ),
                    ),
                ),
            ),
            active_policy_id="entry_policy",
        )
        raw, validation = compile_policy_to_runtime_config({}, valid_library)
        self.assertTrue(validation.valid, validation.fatal_errors)
        self.assertEqual(
            raw["request_rail"]["rule_list"][0]["__template_key"],
            "request_entry_detector",
        )

        invalid_library = PolicyLibrary(
            policies=(
                PolicyDefinition(
                    "entry_policy",
                    "Entry policy",
                    components=(
                        PolicyComponent(
                            "entry",
                            "request_entry_detector",
                            "input_rail",
                        ),
                    ),
                ),
            ),
            active_policy_id="entry_policy",
        )
        _, invalid = compile_policy_to_runtime_config({}, invalid_library)
        self.assertFalse(invalid.valid)

    def test_pipeline_uses_explicit_entry_not_event_extra(self):
        config = normalize_config(
            {
                "request_rail": {
                    "rule_list": [
                        {
                            "__template_key": "request_entry_detector",
                            "rule_id": "normal_entry",
                            "match_llm_request": True,
                            "match_agent_reset": False,
                            "action_on_hit": "observe",
                        },
                        {
                            "__template_key": "request_entry_detector",
                            "rule_id": "reset_entry",
                            "match_llm_request": False,
                            "match_agent_reset": True,
                            "action_on_hit": "observe",
                        },
                    ]
                }
            }
        )
        event = _Event()
        event.set_extra("_llm_guardrail_request_entry", "agent_reset")

        normal = asyncio.run(
            GuardrailPipeline(config).run_request(
                event, _Request(), request_entry="llm_request"
            )
        )
        self.assertTrue(normal.results["normal_entry"].matched)
        self.assertFalse(normal.results["reset_entry"].matched)
        self.assertEqual(normal.request_entry, "llm_request")

        reset = asyncio.run(
            GuardrailPipeline(config).run_request(
                _Event(), _Request(), request_entry="agent_reset"
            )
        )
        self.assertFalse(reset.results["normal_entry"].matched)
        self.assertTrue(reset.results["reset_entry"].matched)
        self.assertEqual(reset.request_entry, "agent_reset")

    def test_agent_reset_selection_can_block_only_that_entry(self):
        config = normalize_config(
            {
                "request_rail": {
                    "rule_list": [
                        {
                            "__template_key": "request_entry_detector",
                            "rule_id": "reset_only",
                            "match_llm_request": False,
                            "match_agent_reset": True,
                            "action_on_hit": "block",
                        }
                    ]
                }
            }
        )

        normal = asyncio.run(
            GuardrailPipeline(config).run_request(
                _Event(), _Request(), request_entry="llm_request"
            )
        )
        reset = asyncio.run(
            GuardrailPipeline(config).run_request(
                _Event(), _Request(), request_entry="agent_reset"
            )
        )

        self.assertFalse(normal.input_blocked)
        self.assertTrue(reset.input_blocked)
        self.assertEqual(reset.terminal_action["node_id"], "reset_only")


if __name__ == "__main__":
    unittest.main()
