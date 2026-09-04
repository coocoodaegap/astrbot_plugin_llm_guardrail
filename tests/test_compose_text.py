import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

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
    def __init__(self, text="current input"):
        self.message_str = text
        self.unified_msg_origin = "test:message:session"
        self.extras = {}

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
        return None


class ComposeTextTests(unittest.TestCase):
    def test_normalization_forces_data_only_actions_without_capping_template(self):
        template = "prefix:" + "x" * 20000
        config = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "compose_text",
                            "rule_id": "compose",
                            "template": template,
                            "inspection_template": "ignored",
                            "action_on_hit": "block",
                            "action_on_error": "block",
                        }
                    ]
                }
            }
        )

        node = config.rails["input_rail"].nodes[0]
        self.assertEqual(node.config["template"], template)
        self.assertEqual(node.config["inspection_template"], "")
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertEqual(node.config["action_on_error"], "discard")

    def test_pipeline_exposes_full_value_and_consumer_uses_its_normal_window(self):
        original = "A" * 64 + " needle"
        config = normalize_config(
            {
                "input_rail": {
                    "max_text_chars": 8,
                    "rule_list": [
                        {
                            "__template_key": "compose_text",
                            "rule_id": "compose",
                            "template": "header:${event_origin}",
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "consumer",
                            "keywords": ["header"],
                            "depend_on": "compose",
                            "inspection_template": "${compose.value}",
                            "action_on_hit": "observe",
                        },
                    ]
                }
            }
        )

        context = asyncio.run(GuardrailPipeline(config).run_message_input(_Event(original)))

        composed = context.results["compose"]
        self.assertTrue(composed.matched)
        self.assertTrue(composed.signal.truthy)
        self.assertEqual(composed.signal.payload["value"], f"header:{original}")
        self.assertEqual(composed.metadata["value_length"], len(f"header:{original}"))
        self.assertTrue(context.results["consumer"].matched)

    def test_policy_compilation_allows_context_to_compose_to_inspection(self):
        context_component = PolicyComponent(
            "history", "context_extractor", "input_rail", config={"turns": 0}
        )
        composer = PolicyComponent(
            "compose",
            "compose_text",
            "input_rail",
            depend_on="history",
            config={"template": "current:${event_origin}\nhistory:${history.value}"},
        )
        rule = RuleDefinition("consumer", "plain_keywords", {"keywords": ["current"]})
        binding = PolicyRuleBinding(
            "consumer",
            "input_rail",
            depend_on="compose",
            inspection_template="${compose.value}",
            action_on_hit="observe",
        )
        library = PolicyLibrary(
            rules=(rule,),
            policies=(
                PolicyDefinition(
                    "composed",
                    "Composed",
                    bindings=(binding,),
                    components=(context_component, composer),
                    node_order=("history", "compose", "consumer"),
                ),
            ),
            active_policy_id="composed",
        )

        raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid, validation.fatal_errors)
        context = asyncio.run(
            GuardrailPipeline(normalize_config(raw)).run_message_input(_Event())
        )
        self.assertTrue(context.results["consumer"].matched)

    def test_policy_rejects_noninspection_consumers_and_unknown_fields(self):
        composer = PolicyComponent(
            "compose", "compose_text", "input_rail", config={"template": "safe"}
        )
        invalid_redirect = PolicyDefinition(
            "redirect",
            "Redirect",
            components=(composer,),
            rail_settings={"input_rail": {"output_redirect_template": "${compose.value}"}},
        )
        invalid_field_rule = RuleDefinition("consumer", "plain_keywords", {"keywords": ["safe"]})
        invalid_field = PolicyDefinition(
            "field",
            "Field",
            bindings=(
                PolicyRuleBinding(
                    "consumer", "input_rail", inspection_template="${compose.component}"
                ),
            ),
            components=(composer,),
        )

        redirect_validation = PolicyLibrary(policies=(invalid_redirect,)).validate()
        field_validation = PolicyLibrary(
            rules=(invalid_field_rule,), policies=(invalid_field,)
        ).validate()

        self.assertFalse(redirect_validation.valid)
        self.assertIn("output_redirect_template cannot read compose_text", redirect_validation.fatal_errors[0])
        self.assertFalse(field_validation.valid)
        self.assertIn("may only read compose.value from compose_text", field_validation.fatal_errors[0])

    def test_raw_runtime_config_cannot_redirect_with_composed_value(self):
        config = normalize_config(
            {
                "input_rail": {
                    "__policy_step_settings": {
                        "output_redirect_template": "${compose.value}"
                    },
                    "rule_list": [
                        {
                            "__template_key": "compose_text",
                            "rule_id": "compose",
                            "enabled": False,
                            "template": "private text",
                        }
                    ],
                }
            }
        )
        event = _Event("unchanged input")

        context = asyncio.run(GuardrailPipeline(config).run_message_input(event))

        self.assertEqual(event.message_str, "unchanged input")
        self.assertTrue(
            any("output_redirect_template cannot read context_extractor or compose_text" in warning
                for warning in context.warnings)
        )


if __name__ == "__main__":
    unittest.main()
