import asyncio
import json
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from adapters import AstrBotAdapter
from config import normalize_config
from context_extractor import CONTEXT_EXTRACTOR_SCHEMA, build_context_extraction
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
    def __init__(self, text="current input"):
        self.message_str = text
        self.unified_msg_origin = "platform:message:session"
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
    def __init__(self, prompt="current input"):
        self.prompt = prompt
        self.system_prompt = ""
        self.extra_user_content_parts = []


class _Response:
    def __init__(self, text="current output"):
        self.completion_text = text
        self.is_chunk = False


class _ConversationManager:
    def __init__(self, history):
        self.history = json.dumps(history, ensure_ascii=False)
        self.current_id_calls = 0
        self.conversation_calls = 0

    async def get_curr_conversation_id(self, umo):
        self.current_id_calls += 1
        return "branch-1"

    async def get_conversation(self, umo, conversation_id, create_if_not_exists=False):
        self.conversation_calls += 1
        self.last_create_if_not_exists = create_if_not_exists
        return types.SimpleNamespace(history=self.history)


class _Context:
    def __init__(self, history):
        self.conversation_manager = _ConversationManager(history)


class ContextExtractorFormatTests(unittest.TestCase):
    def test_config_keeps_extractor_data_only_and_normalizes_turns(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "context_extractor",
                            "rule_id": "ctx",
                            "turns": -1,
                            "inspection_template": "${event_origin}",
                            "action_on_hit": "block",
                            "action_on_error": "block",
                        }
                    ]
                }
            }
        )
        node = cfg.rails["input_rail"].nodes[0]
        self.assertEqual(node.config["turns"], 3)
        self.assertEqual(node.config["inspection_template"], "")
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertEqual(node.config["action_on_error"], "discard")

    def test_normalizes_abnormal_entries_as_neutral_notices(self):
        extraction = build_context_extraction(
            [
                {"role": "user", "content": "first user"},
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "first bot"}],
                },
                {"role": "system", "content": "internal"},
                {"role": "tool", "content": "tool result"},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "orphan answer"},
                {"not": "a message"},
            ],
            turns=3,
            user_only=False,
        )

        self.assertEqual(extraction.payload()["schema"], CONTEXT_EXTRACTOR_SCHEMA)
        self.assertEqual(
            extraction.value.splitlines(),
            [
                '[guardrail-context/v1 turn=1 source=previous_message] "first user"',
                '[guardrail-context/v1 turn=1 source=previous_reply] "first bot"',
                '[guardrail-context/v1 source=notice] "此条记录为 system 条目。"',
                '[guardrail-context/v1 source=notice] "此条记录为 tool 条目。"',
                '[guardrail-context/v1 source=notice] "此条记录为空条目。"',
                '[guardrail-context/v1 source=notice] "此条记录为损坏条目。"',
                '[guardrail-context/v1 source=notice] "此条记录为损坏条目。"',
            ],
        )

    def test_reads_astrbot_content_part_lists_without_marking_text_as_damaged(self):
        extraction = build_context_extraction(
            [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "part user"}],
                },
                {
                    "role": "assistant",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "ignored"}},
                        {"type": "text", "text": "part reply"},
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "ignored"}}],
                },
            ],
            turns=2,
            user_only=False,
        )
        self.assertEqual(
            extraction.value.splitlines(),
            [
                '[guardrail-context/v1 turn=1 source=previous_message] "part user"',
                '[guardrail-context/v1 turn=1 source=previous_reply] "part reply"',
                '[guardrail-context/v1 source=notice] "此条记录为非文本条目。"',
            ],
        )

    def test_zero_turns_and_bounded_rendering(self):
        disabled = build_context_extraction(
            [{"role": "user", "content": "ignored"}],
            turns=0,
            user_only=False,
        )
        self.assertEqual(disabled.value, "")
        self.assertEqual(disabled.diagnostic, "turns_disabled")

        bounded = build_context_extraction(
            [{"role": "user", "content": "x" * 1000}],
            turns=1,
            user_only=True,
            max_chars=256,
        )
        self.assertTrue(bounded.truncated)
        self.assertLessEqual(len(bounded.value), 256)
        self.assertTrue(bounded.value.startswith("[guardrail-context/v1"))


class ContextExtractorPipelineTests(unittest.TestCase):
    def _config(self):
        return normalize_config(
            {
                "fallback_policy_settings": {"default_action_on_hit": "observe"},
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "context_extractor", "rule_id": "ctx_input", "turns": 3},
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "history_consumer",
                            "keywords": ["earlier evidence"],
                            "depend_on": "ctx_input",
                            "inspection_template": "${ctx_input.value}",
                            "action_on_hit": "observe",
                        },
                    ]
                },
                "request_rail": {
                    "rule_list": [
                        {"__template_key": "context_extractor", "rule_id": "ctx_request", "turns": 1, "user_only": True}
                    ]
                },
                "output_rail": {
                    "rule_list": [
                        {"__template_key": "context_extractor", "rule_id": "ctx_output", "turns": 1}
                    ]
                },
            }
        )

    def test_pipeline_redirects_context_and_reuses_one_history_read_across_steps(self):
        adapter_context = _Context(
            [
                {"role": "user", "content": "earlier evidence"},
                {"role": "assistant", "content": [{"type": "text", "text": "earlier answer"}]},
                {"role": "user", "content": "current input"},
                {"role": "assistant", "content": [{"type": "text", "text": "current output"}]},
            ]
        )
        event = _Event()
        pipeline = GuardrailPipeline(self._config(), AstrBotAdapter(adapter_context))

        input_context = asyncio.run(pipeline.run_message_input(event))
        self.assertTrue(input_context.results["ctx_input"].matched)
        self.assertTrue(input_context.results["history_consumer"].matched)
        self.assertNotIn("current input", input_context.results["ctx_input"].signal.payload["value"])

        request_context = asyncio.run(pipeline.run_request(event, _Request()))
        self.assertTrue(request_context.results["ctx_request"].matched)
        output_context = asyncio.run(pipeline.run_response(event, _Response()))
        self.assertTrue(output_context.results["ctx_output"].matched)
        manager = adapter_context.conversation_manager
        self.assertEqual(manager.current_id_calls, 1)
        self.assertEqual(manager.conversation_calls, 1)
        self.assertFalse(manager.last_create_if_not_exists)

    def test_missing_history_is_true_fail_open_signal_with_empty_value(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "context_extractor", "rule_id": "ctx"}
                    ]
                }
            }
        )
        context = asyncio.run(
            GuardrailPipeline(cfg, AstrBotAdapter()).run_message_input(_Event())
        )
        result = context.results["ctx"]
        self.assertTrue(result.matched)
        self.assertEqual(result.signal.payload["value"], "")
        self.assertEqual(result.signal.payload["diagnostic"], "history_unavailable")

    def test_raw_stage_redirect_cannot_use_context_payload(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "__policy_step_settings": {
                        "output_redirect_template": "${ctx.value}"
                    },
                    "rule_list": [
                        {"__template_key": "context_extractor", "rule_id": "ctx"}
                    ],
                }
            }
        )
        event = _Event("unchanged input")
        context = asyncio.run(
            GuardrailPipeline(cfg, AstrBotAdapter()).run_message_input(event)
        )
        self.assertEqual(event.message_str, "unchanged input")
        self.assertTrue(
            any(
                "output_redirect_template cannot read context_extractor" in warning
                for warning in context.warnings
            )
        )

    def test_policy_compilation_permits_nonblocking_context_reads_and_blocks_redirects(self):
        extractor = PolicyComponent(
            component_id="ctx",
            component_type="context_extractor",
            rail="input_rail",
            action_on_hit="observe",
            action_on_error="discard",
            config={"turns": 2},
        )
        consumer = PolicyRuleBinding(
            rule_id="history_word",
            rail="input_rail",
            depend_on="ctx",
            inspection_template="${ctx.value}",
            action_on_hit="observe",
        )
        rule = RuleDefinition(
            rule_id="history_word",
            template_key="plain_keywords",
            template_config={"keywords": ["earlier evidence"]},
        )
        policy = PolicyDefinition(
            policy_id="history_policy",
            name="History",
            bindings=(consumer,),
            components=(extractor,),
            node_order=("ctx", "history_word"),
        )
        library = PolicyLibrary(
            rules=(rule,), policies=(policy,), active_policy_id="history_policy"
        )
        compiled, validation = compile_policy_to_runtime_config({}, library)
        self.assertTrue(validation.valid, validation.fatal_errors)
        context = asyncio.run(
            GuardrailPipeline(
                normalize_config(compiled),
                AstrBotAdapter(
                    _Context([{"role": "user", "content": "earlier evidence"}])
                ),
            ).run_message_input(_Event("current input"))
        )
        self.assertTrue(context.results["history_word"].matched)

        nonblocking_policy = PolicyDefinition(
            policy_id="nonblocking_history",
            name="Nonblocking",
            bindings=(
                PolicyRuleBinding(
                    rule_id="history_word",
                    rail="input_rail",
                    inspection_template="${ctx.value}",
                ),
            ),
            components=(extractor,),
        )
        self.assertTrue(
            PolicyLibrary(
                rules=(rule,), policies=(nonblocking_policy,)
            ).validate().valid
        )

        invalid_policy = PolicyDefinition(
            policy_id="invalid_history",
            name="Invalid",
            components=(extractor,),
            rail_settings={
                "input_rail": {"output_redirect_template": "${ctx.value}"}
            },
        )
        invalid = PolicyLibrary(policies=(invalid_policy,)).validate()
        self.assertFalse(invalid.valid)
        self.assertIn("output_redirect_template cannot read context_extractor", invalid.fatal_errors[0])


if __name__ == "__main__":
    unittest.main()
