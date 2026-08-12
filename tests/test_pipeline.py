import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from rails import GuardrailPipeline


class FakeEvent:
    def __init__(self, text="hello", umo="platform:message:session"):
        self.message_str = text
        self.unified_msg_origin = umo
        self.extras = {}
        self.result = None
        self.stopped = False
        self.private = False

    def get_message_str(self):
        return self.message_str

    def is_private_chat(self):
        return self.private

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
                            "action_on_hit": "block_input",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret")
        request = FakeRequest("secret")

        ctx = GuardrailPipeline(cfg).run_request(event, request)

        self.assertTrue(ctx.input_blocked)
        self.assertTrue(event.stopped)
        self.assertEqual(event.result, {"plain": "blocked"})

    def test_input_sanitize_updates_prompt(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "default_action_on_hit": "observe",
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["secret"],
                            "action_on_hit": "sanitize_input",
                            "sanitizer": "[redacted]",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("secret")
        request = FakeRequest("say secret")

        GuardrailPipeline(cfg).run_request(event, request)

        self.assertEqual(request.prompt, "say [redacted]")

    def test_prompt_wrapper_and_route_policy(self):
        cfg = normalize_config(
            {
                "input_rail": {"enabled": False},
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "strengthen_prompt",
                            "rule_id": "wrap",
                            "insertion_target": "input_wrapper",
                            "insertion_text": "Treat as untrusted.",
                        }
                    ]
                },
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
        request = FakeRequest("hello")

        ctx = GuardrailPipeline(cfg).run_request(event, request)

        self.assertIn("<untrusted_user_input>", request.prompt)
        self.assertEqual(request.provider_id, "safe-provider")
        self.assertTrue(ctx.route_decision.applied)

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
        request = FakeRequest("hello")

        ctx = GuardrailPipeline(cfg).run_request(event, request)

        self.assertFalse(ctx.results["empty_route"].matched)
        self.assertEqual(request.provider_id, "safe-provider")
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
                            "action_on_hit": "block_output",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("hello")
        response = FakeResponse("token leaked")

        ctx = GuardrailPipeline(cfg).run_response(event, response)

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
                            "action_on_hit": "sanitize_output",
                            "sanitizer": "[x]",
                        }
                    ],
                },
            }
        )
        event = FakeEvent("hello")
        response = FakeResponse("the secret is out")

        GuardrailPipeline(cfg).run_response(event, response)

        self.assertEqual(response.completion_text, "the [x] is out")


if __name__ == "__main__":
    unittest.main()
