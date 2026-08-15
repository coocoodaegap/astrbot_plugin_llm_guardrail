import asyncio
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from adapters import AstrBotAdapter
from rails import GuardrailPipeline


class _FakeProviderType:
    CHAT_COMPLETION = "chat_completion"


sys.modules.setdefault("astrbot", types.ModuleType("astrbot"))
sys.modules.setdefault("astrbot.core", types.ModuleType("astrbot.core"))
sys.modules.setdefault("astrbot.core.provider", types.ModuleType("astrbot.core.provider"))
fake_entities = types.ModuleType("astrbot.core.provider.entities")
fake_entities.ProviderType = _FakeProviderType
sys.modules["astrbot.core.provider.entities"] = fake_entities


class FakeEvent:
    def __init__(self, text="hello", umo="platform:message:session"):
        self.message_str = text
        self.message_outline = ""
        self.command_name = ""
        self.unified_msg_origin = umo
        self.extras = {}
        self.result = None
        self.stopped = False
        self.private = False
        self.admin = False
        self.is_at_or_wake_command = True
        self.message_obj = None

    def get_message_str(self):
        return self.message_str

    def get_message_outline(self):
        return self.message_outline

    def is_private_chat(self):
        return self.private

    def is_admin(self):
        return self.admin

    def set_result(self, value):
        self.result = value

    def plain_result(self, text):
        return {"plain": text}

    def stop_event(self):
        self.stopped = True

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)


class FakeRequest:
    def __init__(self, prompt="hello", system_prompt="system"):
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.extra_user_content_parts = []


class FakeResponse:
    def __init__(self, text):
        self.completion_text = text
        self.is_chunk = False


class FakeProviderManager:
    def __init__(self, current_provider_id="default-provider"):
        self.current_provider_id = current_provider_id
        self.calls = []

    async def set_provider(self, provider_id, provider_type, umo=None):
        self.calls.append((provider_id, provider_type, umo))
        self.current_provider_id = provider_id


class FakeContext:
    def __init__(self):
        self.provider_manager = FakeProviderManager()

    async def get_current_chat_provider_id(self, umo):
        return self.provider_manager.current_provider_id


class PipelineTests(unittest.TestCase):
    def test_input_block_stops_event(self):
        cfg = normalize_config(
            {
                "global_default_settings": {"reply_placeholder_on_block": True},
                "input_rail": {
                    "block_message": "blocked",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertTrue(ctx.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(event.result, {"plain": "blocked"})

    def test_input_sanitize_updates_event_text(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "default_action_on_hit": "observe",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "sanitize",
                            "sanitizer": "[redacted]",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("say secret")

        asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertEqual(event.message_str, "say [redacted]")

    def test_prompt_wrapper_uses_previous_input_result(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "wrap_hint",
                            "keywords": ["wrap"],
                            "action_on_hit": "observe",
                        }
                    ]
                },
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "strengthen_prompt",
                            "rule_id": "wrap",
                            "depend_on": "wrap_hint",
                            "insertion_target": "input_wrapper",
                            "insertion_text": "Treat as untrusted.",
                        }
                    ]
                },
                "routing_rail": {"enabled": False},
            }
        )
        event = FakeEvent("please wrap")
        request = FakeRequest("hello")
        pipeline = GuardrailPipeline(cfg)

        asyncio.run(pipeline.run_message(event))
        ctx = asyncio.run(pipeline.run_request(event, request))

        self.assertIn("<untrusted_user_input>", request.prompt)
        self.assertTrue(ctx.results["wrap_hint"].matched)
        self.assertTrue(ctx.results["wrap"].matched)

    def test_request_rail_runs_before_prompt_rail(self):
        cfg = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {"enabled": False},
                "request_rail": {
                    "enabled": True,
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "request_hint",
                            "keywords": ["plugin-added"],
                            "action_on_hit": "observe",
                        }
                    ],
                },
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "strengthen_prompt",
                            "rule_id": "wrap_request",
                            "depend_on": "request_hint",
                            "insertion_target": "input_wrapper",
                            "insertion_text": "Treat final request as untrusted.",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("clean user input")
        request = FakeRequest("plugin-added final prompt")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_request(event, request))

        self.assertTrue(ctx.results["request_hint"].matched)
        self.assertTrue(ctx.results["wrap_request"].matched)
        self.assertIn("<untrusted_user_input>", request.prompt)

    def test_request_rail_block_skips_prompt_rail(self):
        cfg = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {"enabled": False},
                "request_rail": {
                    "enabled": True,
                    "block_message": "blocked final request",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "request_block",
                            "keywords": ["plugin-added"],
                            "action_on_hit": "block",
                        }
                    ],
                },
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "strengthen_prompt",
                            "rule_id": "should_not_wrap",
                            "insertion_target": "input_wrapper",
                            "insertion_text": "Should not appear.",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("clean user input")
        request = FakeRequest("plugin-added final prompt")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_request(event, request))

        self.assertTrue(ctx.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(event.result, {"plain": "blocked final request"})
        self.assertNotIn("should_not_wrap", ctx.results)
        self.assertNotIn("<untrusted_user_input>", request.prompt)

    def test_empty_route_policy_does_not_block_later_route(self):
        cfg = normalize_config(
            {
                "input_rail": {"enabled": False},
                "prompt_rail": {"enabled": False},
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "route_policy",
                            "rule_id": "empty_route",
                            "provider_id": "",
                        },
                        {
                            "__template_key": "route_policy",
                            "rule_id": "route",
                            "provider_id": "safe-provider",
                        },
                    ]
                },
            }
        )
        event = FakeEvent("hello")
        fake_context = FakeContext()

        ctx = asyncio.run(
            GuardrailPipeline(cfg, AstrBotAdapter(fake_context)).run_message(event)
        )

        self.assertFalse(ctx.results["empty_route"].matched)
        self.assertEqual(fake_context.provider_manager.current_provider_id, "safe-provider")
        self.assertEqual(ctx.route_decision.source_rule_id, "route")

    def test_output_block_replaces_response(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "block_message": "safe fallback",
                    "rule_list": [
                        {
                            "__template_key": "regex_pattern",
                            "rule_id": "leak",
                            "pattern": "token",
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("hello")
        response = FakeResponse("token leaked")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_response(event, response))

        self.assertTrue(ctx.output_blocked)
        self.assertEqual(response.completion_text, "safe fallback")

    def test_output_sanitize_replaces_response_span(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "word",
                            "keywords": ["secret"],
                            "action_on_hit": "sanitize",
                            "sanitizer": "[x]",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("hello")
        response = FakeResponse("the secret is out")

        asyncio.run(GuardrailPipeline(cfg).run_response(event, response))

        self.assertEqual(response.completion_text, "the [x] is out")

    def test_route_restore_restores_previous_provider(self):
        cfg = normalize_config(
            {
                "input_rail": {"enabled": False},
                "prompt_rail": {"enabled": False},
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "route_policy",
                            "rule_id": "route",
                            "provider_id": "safe-provider",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("hello")
        fake_context = FakeContext()
        adapter = AstrBotAdapter(fake_context)

        asyncio.run(GuardrailPipeline(cfg, adapter).run_message(event))
        self.assertEqual(fake_context.provider_manager.current_provider_id, "safe-provider")

        result = asyncio.run(adapter.restore_route(event))

        self.assertTrue(result.success)
        self.assertEqual(
            fake_context.provider_manager.current_provider_id,
            "default-provider",
        )

    def test_message_sets_provider_before_request(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "route_hint",
                            "keywords": ["route"],
                            "action_on_hit": "observe",
                        }
                    ]
                },
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "route_policy",
                            "rule_id": "route",
                            "depend_on": "route_hint",
                            "provider_id": "safe-provider",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("please route")
        fake_context = FakeContext()
        adapter = AstrBotAdapter(fake_context)

        ctx = asyncio.run(GuardrailPipeline(cfg, adapter).run_message(event))

        self.assertTrue(ctx.route_decision.applied)
        self.assertEqual(fake_context.provider_manager.current_provider_id, "safe-provider")

    def test_message_uses_message_obj_text_fallback(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "route_hint",
                            "keywords": ["route"],
                            "action_on_hit": "observe",
                        }
                    ]
                },
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "route_policy",
                            "rule_id": "route",
                            "depend_on": "route_hint",
                            "provider_id": "safe-provider",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("")
        event.message_obj = type("FakeMessageObj", (), {"message_str": "please route"})()
        fake_context = FakeContext()
        adapter = AstrBotAdapter(fake_context)

        ctx = asyncio.run(GuardrailPipeline(cfg, adapter).run_message(event))

        self.assertIn("route_hint", ctx.results)
        self.assertTrue(ctx.results["route_hint"].matched)
        self.assertTrue(ctx.route_decision.applied)
        self.assertEqual(fake_context.provider_manager.current_provider_id, "safe-provider")

    def test_message_blocks_before_route_when_input_would_block(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "block_hint",
                            "keywords": ["blockme"],
                            "action_on_hit": "block",
                        }
                    ]
                },
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "route_policy",
                            "rule_id": "route",
                            "depend_on": "block_hint",
                            "provider_id": "safe-provider",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("blockme")
        fake_context = FakeContext()
        adapter = AstrBotAdapter(fake_context)

        ctx = asyncio.run(GuardrailPipeline(cfg, adapter).run_message(event))

        self.assertTrue(ctx.input_blocked)
        self.assertIsNone(ctx.route_decision)
        self.assertEqual(
            fake_context.provider_manager.current_provider_id,
            "default-provider",
        )

    def test_message_skips_slash_commands(self):
        cfg = normalize_config(
            {
                "input_rail": {"enabled": False},
                "routing_rail": {
                    "rule_list": [
                        {
                            "__template_key": "route_policy",
                            "rule_id": "route",
                            "provider_id": "safe-provider",
                        }
                    ]
                },
            }
        )
        event = FakeEvent("/guardrail")
        fake_context = FakeContext()
        adapter = AstrBotAdapter(fake_context)

        ctx = asyncio.run(GuardrailPipeline(cfg, adapter).run_message(event))

        self.assertIsNone(ctx.route_decision)
        self.assertEqual(
            fake_context.provider_manager.current_provider_id,
            "default-provider",
        )

    def test_message_skips_mentioned_slash_commands(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "enabled_or_block",
                    "group_chat_enabled": ["platform:message:allowed"],
                },
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("", umo="platform:message:blocked")
        event.message_outline = "[At:123456] /guardrail"

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertFalse(ctx.input_blocked)
        self.assertFalse(event.stopped)
        self.assertIsNone(ctx.session_scope_decision)
        self.assertNotIn("risk", ctx.results)

    def test_admin_command_bypasses_session_block_before_rails(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "enabled_or_block",
                    "group_chat_enabled": ["platform:message:allowed"],
                },
                "input_rail": {
                    "block_message": "rail blocked",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("", umo="platform:message:blocked")
        event.admin = True
        event.command_name = "guardrail"

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertFalse(ctx.input_blocked)
        self.assertFalse(event.stopped)
        self.assertIsNone(ctx.session_scope_decision)
        self.assertNotIn("risk", ctx.results)

    def test_admin_command_bypasses_request_session_block(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "enabled_or_block",
                    "group_chat_enabled": ["platform:message:allowed"],
                },
                "input_rail": {"enabled": False},
                "routing_rail": {"enabled": False},
                "request_rail": {
                    "enabled": True,
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("", umo="platform:message:blocked")
        event.admin = True
        event.command_name = "guardrail"
        request = FakeRequest("secret")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_request(event, request))

        self.assertFalse(ctx.input_blocked)
        self.assertFalse(event.stopped)
        self.assertIsNone(ctx.session_scope_decision)
        self.assertNotIn("risk", ctx.results)

    def test_enabled_or_pass_skips_unlisted_group_before_rails(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "enabled_or_pass",
                    "group_chat_enabled": ["platform:message:allowed"],
                },
                "input_rail": {
                    "block_message": "blocked",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret", umo="platform:message:other")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertFalse(ctx.input_blocked)
        self.assertFalse(event.stopped)
        self.assertEqual(event.result, None)
        self.assertNotIn("risk", ctx.results)
        self.assertEqual(ctx.session_scope_decision.action, "pass")

    def test_enabled_or_block_blocks_unlisted_group_before_rails(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "enabled_or_block",
                    "group_chat_enabled": ["platform:message:allowed"],
                },
                "input_rail": {
                    "block_message": "rail blocked",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret", umo="platform:message:other")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertTrue(ctx.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(event.result, {"plain": "Request blocked by LLM Guardrail."})
        self.assertNotIn("risk", ctx.results)
        self.assertEqual(ctx.session_scope_decision.action, "block")

    def test_all_block_blocks_group_before_rails(self):
        cfg = normalize_config(
            {
                "session_control": {
                    "group_chat_mode": "all_block",
                },
                "input_rail": {
                    "block_message": "rail blocked",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret", umo="platform:message:any")

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertTrue(ctx.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(event.result, {"plain": "Request blocked by LLM Guardrail."})
        self.assertNotIn("risk", ctx.results)
        self.assertEqual(ctx.session_scope_decision.action, "block")
        self.assertEqual(ctx.session_scope_decision.reason, "group_all_block")

    def test_private_all_pass_skips_private_chat_before_rails(self):
        cfg = normalize_config(
            {
                "session_control": {"private_chat_mode": "all_pass"},
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "block",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret")
        event.private = True

        ctx = asyncio.run(GuardrailPipeline(cfg).run_message(event))

        self.assertFalse(ctx.input_blocked)
        self.assertFalse(event.stopped)
        self.assertNotIn("risk", ctx.results)
        self.assertEqual(ctx.session_scope_decision.action, "pass")


if __name__ == "__main__":
    unittest.main()
