import asyncio
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from adapters import AstrBotAdapter
from config import normalize_config
from policy_library import (
    PolicyComponent,
    PolicyDefinition,
    PolicyLibrary,
    PolicyRuleBinding,
    RuleDefinition,
    compile_policy_to_runtime_config,
)
from rails import GuardrailPipeline


class _Event:
    def __init__(self, text):
        self.message_str = text
        self.message_outline = ""
        self.command_name = ""
        self.unified_msg_origin = "test:echo:session"
        self.platform_id = "test"
        self.platform_name = "test"
        self.sender_id = "sender"
        self.extras = {}
        self.private = False
        self.admin = False
        self.is_at_or_wake_command = True
        self.message_obj = None
        self.stopped = False

    def get_message_str(self):
        return self.message_str

    def get_message_outline(self):
        return self.message_outline

    def get_platform_id(self):
        return self.platform_id

    def get_platform_name(self):
        return self.platform_name

    def get_sender_id(self):
        return self.sender_id

    def is_private_chat(self):
        return self.private

    def is_admin(self):
        return self.admin

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def stop_event(self):
        self.stopped = True

    def plain_result(self, text):
        return {"plain": text}

    def set_result(self, _value):
        return None


class _Response:
    def __init__(self, text):
        self.completion_text = text
        self.is_chunk = False


class _KbManager:
    def __init__(self):
        self.retrieve_calls = []
        self.retrieve_result = {
            "results": [{"text": "matching policy", "score": 0.95}]
        }

    async def get_kb_by_name(self, name):
        return types.SimpleNamespace(kb=types.SimpleNamespace(kb_id=name, kb_name=name))

    async def retrieve(self, **kwargs):
        self.retrieve_calls.append(kwargs)
        return self.retrieve_result


class _Context:
    def __init__(self):
        self.providers = {"default-provider": object()}
        self.llm_responses = []
        self.llm_calls = []
        self.kb_manager = _KbManager()

    async def get_current_chat_provider_id(self, _umo):
        return "default-provider"

    def get_provider_by_id(self, provider_id):
        return self.providers.get(provider_id)

    async def llm_generate(self, chat_provider_id, prompt, system_prompt=None):
        self.llm_calls.append(
            {
                "provider_id": chat_provider_id,
                "prompt": prompt,
                "system_prompt": system_prompt,
            }
        )
        text = self.llm_responses.pop(0) if self.llm_responses else '{"matched": false}'
        return _Response(text)


class _CaptureService:
    def __init__(self):
        self.calls = []

    async def capture_match(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(success=True, warning="")


def _echo_config(sources, **options):
    return {
        "source_node_ids": sources,
        "scan_limit_chars": options.get("scan_limit_chars", 12000),
        "min_rechecked_sources": options.get("min_rechecked_sources", 1),
        "max_rechecked_sources": options.get("max_rechecked_sources", 4),
        "max_external_rechecks": options.get("max_external_rechecks", 2),
        "ignore_fenced_code": options.get("ignore_fenced_code", True),
    }


class SensitiveEchoDetectorTests(unittest.TestCase):
    def test_rechecks_matched_plain_and_regex_sources_without_exposing_text(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk_terms",
                            "keywords": ["secret"],
                            "action_on_hit": "observe",
                        },
                        {
                            "__template_key": "regex_pattern",
                            "rule_id": "risk_pattern",
                            "pattern": r"RISK-[0-9]+",
                            "action_on_hit": "observe",
                        },
                    ]
                },
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "sensitive_echo_detector",
                            "rule_id": "echo_guard",
                            "action_on_hit": "observe",
                            "inspection_template": "must not replace the output snapshot",
                            **_echo_config(
                                ["risk_terms", "risk_pattern"],
                                min_rechecked_sources=2,
                            ),
                        }
                    ]
                },
            }
        )
        event = _Event("secret RISK-7")
        pipeline = GuardrailPipeline(cfg, AstrBotAdapter(_Context()))

        asyncio.run(pipeline.run_message_input(event))
        context = asyncio.run(pipeline.run_response(event, _Response("secret RISK-7")))

        result = context.results["echo_guard"]
        self.assertTrue(result.matched)
        self.assertEqual(result.metadata["reason_codes"], ["rechecked_input_signal"])
        self.assertEqual(result.metadata["rechecked_source_count"], 2)
        self.assertEqual(result.metadata["rechecked_match_count"], 2)
        self.assertEqual(
            result.metadata["rechecked_kind_counts"],
            {"plain_keywords": 1, "regex_pattern": 1},
        )
        self.assertNotIn("secret", str(result.metadata))
        self.assertNotIn("RISK-7", str(result.signal.payload))

    def test_unmatched_or_fenced_output_does_not_trigger_recheck(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk_terms",
                            "keywords": ["secret"],
                            "action_on_hit": "observe",
                        }
                    ]
                },
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "sensitive_echo_detector",
                            "rule_id": "echo_guard",
                            "action_on_hit": "observe",
                            **_echo_config(["risk_terms"]),
                        }
                    ]
                },
            }
        )
        for output in ("safe response", "```text\nsecret\n```"):
            with self.subTest(output=output):
                event = _Event("secret")
                pipeline = GuardrailPipeline(cfg, AstrBotAdapter(_Context()))
                asyncio.run(pipeline.run_message_input(event))
                context = asyncio.run(pipeline.run_response(event, _Response(output)))

                self.assertFalse(context.results["echo_guard"].matched)
                self.assertEqual(context.results["echo_guard"].metadata["score"], 0)

    def test_rag_recheck_is_virtual_and_does_not_capture_an_experience(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag_signal",
                            "knowledge_bases": ["policy"],
                            "min_score": 0.7,
                            "action_on_hit": "observe",
                        }
                    ]
                },
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "sensitive_echo_detector",
                            "rule_id": "echo_guard",
                            "action_on_hit": "observe",
                            **_echo_config(["rag_signal"]),
                        }
                    ]
                },
            }
        )
        event = _Event("risk input")
        fake_context = _Context()
        capture = _CaptureService()
        pipeline = GuardrailPipeline(
            cfg, AstrBotAdapter(fake_context), rag_experience=capture
        )

        asyncio.run(pipeline.run_message_input(event))
        context = asyncio.run(pipeline.run_response(event, _Response("risk output")))

        self.assertTrue(context.results["echo_guard"].matched)
        self.assertEqual(len(fake_context.kb_manager.retrieve_calls), 2)
        self.assertEqual(fake_context.kb_manager.retrieve_calls[1]["query"], "risk output")
        self.assertEqual(len(capture.calls), 1)
        self.assertNotIn("matching policy", str(context.results["echo_guard"].metadata))

    def test_llm_recheck_honors_external_cap_and_component_error_action(self):
        base_nodes = [
            {
                "__template_key": "llm_review",
                "rule_id": rule_id,
                "audit_prompt": "Return matched for this safety signal.",
                "action_on_hit": "observe",
            }
            for rule_id in ("review_a", "review_b")
        ]
        cfg = normalize_config(
            {
                "input_rail": {"rule_list": base_nodes},
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "sensitive_echo_detector",
                            "rule_id": "echo_guard",
                            "action_on_hit": "observe",
                            **_echo_config(
                                ["review_a", "review_b"],
                                max_external_rechecks=1,
                            ),
                        }
                    ]
                },
            }
        )
        event = _Event("risk input")
        fake_context = _Context()
        fake_context.llm_responses = [
            '{"matched": true, "payload": {}}',
            '{"matched": true, "payload": {}}',
            '{"matched": true, "payload": {"free_text": "not retained"}}',
        ]
        pipeline = GuardrailPipeline(cfg, AstrBotAdapter(fake_context))

        asyncio.run(pipeline.run_message_input(event))
        context = asyncio.run(pipeline.run_response(event, _Response("risk output")))

        result = context.results["echo_guard"]
        self.assertTrue(result.matched)
        self.assertEqual(result.metadata["external_recheck_count"], 1)
        self.assertTrue(result.metadata["external_recheck_limit_reached"])
        self.assertEqual(len(fake_context.llm_calls), 3)
        self.assertNotIn("not retained", str(result.metadata))

        error_cfg = normalize_config(
            {
                "input_rail": {"rule_list": [base_nodes[0]]},
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "sensitive_echo_detector",
                            "rule_id": "echo_guard",
                            "action_on_error": "block",
                            **_echo_config(["review_a"]),
                        }
                    ]
                },
            }
        )
        error_event = _Event("risk input")
        error_context = _Context()
        error_context.llm_responses = ['{"matched": true}', "not valid JSON"]
        error_result = asyncio.run(
            GuardrailPipeline(error_cfg, AstrBotAdapter(error_context)).run_message_input(
                error_event
            )
        )
        self.assertTrue(error_result.results["review_a"].matched)
        output_context = asyncio.run(
            GuardrailPipeline(error_cfg, AstrBotAdapter(error_context)).run_response(
                error_event, _Response("risk output")
            )
        )
        self.assertTrue(output_context.output_blocked)
        self.assertEqual(output_context.results["echo_guard"].status, "failed")
        self.assertNotIn("not valid JSON", str(output_context.results["echo_guard"].metadata))

    def test_policy_sources_must_be_replayable_step_one_or_three_rules(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("risk_terms", "plain_keywords", {"keywords": ["risk"]}),
                RuleDefinition("output_rule", "plain_keywords", {"keywords": ["risk"]}),
            ),
            policies=(
                PolicyDefinition(
                    "echo_policy",
                    "Echo policy",
                    bindings=(
                        PolicyRuleBinding("risk_terms", "input_rail"),
                        PolicyRuleBinding("output_rule", "output_rail"),
                    ),
                    components=(
                        PolicyComponent(
                            "echo_guard",
                            "sensitive_echo_detector",
                            "output_rail",
                            config=_echo_config(["risk_terms"]),
                        ),
                    ),
                ),
            ),
            active_policy_id="echo_policy",
        )
        compiled, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        self.assertIn(
            "sensitive_echo_detector",
            [
                node["__template_key"]
                for node in compiled["output_rail"]["rule_list"]
            ],
        )

        invalid = PolicyLibrary(
            rules=library.rules,
            policies=(
                PolicyDefinition(
                    "invalid_echo",
                    "Invalid echo",
                    bindings=library.policies[0].bindings,
                    components=(
                        PolicyComponent(
                            "echo_guard",
                            "sensitive_echo_detector",
                            "output_rail",
                            config=_echo_config(["output_rule"]),
                        ),
                    ),
                ),
            ),
            active_policy_id="invalid_echo",
        )

        self.assertFalse(invalid.validate().valid)
        self.assertIn(
            "must be in Step 1 or Step 3",
            " ".join(invalid.validate().fatal_errors),
        )


if __name__ == "__main__":
    unittest.main()
