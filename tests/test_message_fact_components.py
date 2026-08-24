import asyncio
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from adapters import AstrBotAdapter
from components import evaluate_message_fact_component
from config import normalize_config
from core import RailContext
from policy_library import (
    PolicyComponent,
    PolicyDefinition,
    PolicyLibrary,
    compile_policy_to_runtime_config,
)
from rails import GuardrailPipeline


def _component(kind, **attributes):
    value = type(kind, (), {})()
    for key, item in attributes.items():
        setattr(value, key, item)
    return value


class _FactEvent:
    def __init__(self, components, sender_id="request-user"):
        self.components = components
        self.sender_id = sender_id
        self.message_str = "ordinary text"
        self.message_outline = "summary"
        self.unified_msg_origin = "test:message:session"
        self.is_at_or_wake_command = True
        self.extras = {}
        self.result = None
        self.stopped = False

    def get_messages(self):
        return self.components

    def get_sender_id(self):
        return self.sender_id

    def get_message_str(self):
        return self.message_str

    def get_message_outline(self):
        return self.message_outline

    def is_private_chat(self):
        return False

    def is_admin(self):
        return False

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def plain_result(self, text):
        return {"plain": text}

    def set_result(self, value):
        self.result = value

    def stop_event(self):
        self.stopped = True


class _MessageChain:
    """Iterable chain shape used by compatibility adapters."""

    def __init__(self, components):
        self.components = components

    def __iter__(self):
        return iter(self.components)


def _all_fact_rules(action_on_hit="default"):
    return [
        {
            "__template_key": "contains_request_user_id",
            "rule_id": "requester",
            "user_ids": ["request-user"],
            "action_on_hit": action_on_hit,
        },
        {
            "__template_key": "contains_at_user_id",
            "rule_id": "mentioned",
            "user_ids": ["at-user"],
            "action_on_hit": action_on_hit,
        },
        *[
            {
                "__template_key": template_key,
                "rule_id": template_key,
                "action_on_hit": action_on_hit,
            }
            for template_key in (
                "contains_forward",
                "contains_file",
                "contains_image",
                "contains_record",
                "contains_video",
                "contains_link",
            )
        ],
    ]


class MessageFactComponentTests(unittest.TestCase):
    def setUp(self):
        self.event = _FactEvent(
            [
                _component("Plain", text="Read https://Example.Test/a?token=secret"),
                _component("At", qq="at-user"),
                _component("Forward"),
                _component("File"),
                _component("Image"),
                _component("Record"),
                _component("Video"),
            ]
        )

    def test_all_eight_components_use_only_safe_message_facts(self):
        snapshot_result = AstrBotAdapter().get_message_fact_snapshot(self.event)
        snapshot = snapshot_result.metadata["message_fact_snapshot"]
        config = normalize_config({"input_rail": {"rule_list": _all_fact_rules()}})
        context = RailContext(None, None, None, "test:umo", "ordinary text", "ordinary text", "")

        results = {
            node.template_key: evaluate_message_fact_component(node, snapshot)
            for node in config.rails["input_rail"].nodes
        }

        self.assertTrue(all(result.matched for result in results.values()))
        self.assertTrue(all(result.action_on_hit == "observe" for result in results.values()))
        self.assertEqual(results["contains_image"].metadata["component_indices"], [4])
        self.assertEqual(results["contains_record"].metadata["message_kind"], "record")
        self.assertEqual(results["contains_link"].metadata["host_summaries"], ["example.test"])
        metadata_text = str(results["contains_link"].metadata)
        self.assertNotIn("token=secret", metadata_text)
        self.assertNotIn("https://", metadata_text)
        self.assertEqual(results["contains_request_user_id"].metadata["matched_user_ids"], ["***user"])
        self.assertEqual(results["contains_at_user_id"].metadata["matched_user_ids"], ["***user"])

    def test_empty_user_list_disables_only_the_affected_component(self):
        config = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "contains_at_user_id",
                            "rule_id": "empty_ids",
                            "user_ids": [],
                        },
                        {"__template_key": "contains_image", "rule_id": "image"},
                    ]
                }
            }
        )

        missing_ids, image = config.rails["input_rail"].nodes
        self.assertFalse(missing_ids.enabled)
        self.assertFalse(missing_ids.valid)
        self.assertTrue(any("user_ids is empty" in warning for warning in missing_ids.warnings))
        self.assertTrue(image.enabled)
        self.assertTrue(image.valid)
        self.assertEqual(image.config["action_on_hit"], "observe")

    def test_missing_message_chain_degrades_to_empty_facts(self):
        class BrokenChainEvent:
            sender_id = "request-user"
            message_obj = None

            def get_messages(self):
                raise RuntimeError("adapter did not provide a chain")

            def get_sender_id(self):
                return self.sender_id

        result = AstrBotAdapter().get_message_fact_snapshot(BrokenChainEvent())
        snapshot = result.metadata["message_fact_snapshot"]

        self.assertTrue(result.success)
        self.assertEqual(snapshot.components, ())
        self.assertFalse(snapshot.message_chain_available)
        self.assertTrue(any("component chain" in warning for warning in result.warnings))

    def test_adapter_accepts_iterable_chains_and_type_based_components(self):
        event = _FactEvent(
            _MessageChain(
                [
                    {"type": "image"},
                    {"component_type": "forward"},
                ]
            )
        )

        result = AstrBotAdapter().get_message_fact_snapshot(event)
        snapshot = result.metadata["message_fact_snapshot"]

        self.assertTrue(snapshot.message_chain_available)
        self.assertEqual([component.kind for component in snapshot.components], ["image", "forward"])
        self.assertFalse(result.warnings)

    def test_file_with_video_metadata_matches_file_and_video_components(self):
        event = _FactEvent([_component("File", name="clip.mp4")])
        snapshot = AstrBotAdapter().get_message_fact_snapshot(event).metadata[
            "message_fact_snapshot"
        ]
        config = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "contains_file", "rule_id": "file"},
                        {"__template_key": "contains_video", "rule_id": "video"},
                    ]
                }
            }
        )

        results = {
            node.template_key: evaluate_message_fact_component(node, snapshot)
            for node in config.rails["input_rail"].nodes
        }

        self.assertEqual(snapshot.components[0].media_category, "video")
        self.assertTrue(results["contains_file"].matched)
        self.assertTrue(results["contains_video"].matched)

    def test_link_component_matches_common_bare_domains_not_email_or_dotted_words(self):
        config = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {"__template_key": "contains_link", "rule_id": "link"}
                    ]
                }
            }
        )
        node = config.rails["input_rail"].nodes[0]
        linked = AstrBotAdapter().get_message_fact_snapshot(
            _FactEvent([_component("Plain", text="请访问 baidu.com。")])
        ).metadata["message_fact_snapshot"]
        ordinary = AstrBotAdapter().get_message_fact_snapshot(
            _FactEvent([_component("Plain", text="model.version 或 name@example.com")])
        ).metadata["message_fact_snapshot"]

        linked_result = evaluate_message_fact_component(node, linked)
        ordinary_result = evaluate_message_fact_component(node, ordinary)

        self.assertTrue(linked_result.matched)
        self.assertEqual(linked_result.metadata["host_summaries"], ["baidu.com"])
        self.assertFalse(ordinary_result.matched)

    def test_component_only_chain_gets_safe_rail_input_marker(self):
        event = _FactEvent([_component("Record")])
        event.message_str = ""
        event.message_outline = ""

        result = AstrBotAdapter().get_message_ingress_profile(event)
        profile = result.metadata["message_ingress_profile"]

        self.assertTrue(profile.has_content)
        self.assertEqual(profile.source, "component_markers")
        self.assertEqual(profile.text, "[ComponentType.Record]")

    def test_policy_component_compiles_and_observes_in_pipeline(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "media_observe",
                    "Media observe",
                    components=(
                        PolicyComponent(
                            "has_image",
                            "contains_image",
                            "input_rail",
                        ),
                    ),
                ),
            ),
            active_policy_id="media_observe",
        )
        raw, validation = compile_policy_to_runtime_config({}, library)
        context = asyncio.run(
            GuardrailPipeline(normalize_config(raw)).run_message_input(self.event)
        )

        self.assertTrue(validation.valid)
        self.assertIn("has_image", context.results)
        self.assertTrue(context.results["has_image"].matched)
        self.assertEqual(context.results["has_image"].action_on_hit, "observe")
        self.assertFalse(context.input_blocked)
        self.assertFalse(self.event.stopped)

    def test_media_only_event_executes_message_fact_component(self):
        event = _FactEvent([_component("Image")])
        event.message_str = ""
        event.message_outline = ""
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "media_only",
                    "Media only",
                    components=(
                        PolicyComponent(
                            "has_image",
                            "contains_image",
                            "input_rail",
                        ),
                    ),
                ),
            ),
            active_policy_id="media_only",
        )
        raw, validation = compile_policy_to_runtime_config({}, library)
        context = asyncio.run(
            GuardrailPipeline(normalize_config(raw)).run_message_input(event)
        )

        self.assertTrue(validation.valid)
        self.assertTrue(context.results["has_image"].executed)
        self.assertTrue(context.results["has_image"].matched)
        self.assertFalse(context.input_blocked)

    def test_explicit_block_action_keeps_existing_pipeline_semantics(self):
        config = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "contains_image",
                            "rule_id": "block_image",
                            "action_on_hit": "block",
                        }
                    ]
                }
            }
        )
        context = asyncio.run(GuardrailPipeline(config).run_message_input(self.event))

        self.assertTrue(context.results["block_image"].matched)
        self.assertTrue(context.input_blocked)
        self.assertTrue(self.event.stopped)


if __name__ == "__main__":
    unittest.main()
