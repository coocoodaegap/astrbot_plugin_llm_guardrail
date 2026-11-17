"""Tests for the Step 4 style_dialogs component."""

import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from _astrbot_runtime_stub import install as _install_astrbot_runtime

_install_astrbot_runtime()

from adapters import BEGIN_DIALOGS_MARKER, AstrBotAdapter
from config import normalize_config
from policy_library import PolicyComponent, PolicyDefinition, PolicyLibrary
from rails import GuardrailPipeline
from test_pipeline import FakeEvent, FakeRequest


PERSONA_TURNS = [
    {"role": "user", "content": "persona user", "_no_save": True},
    {"role": "assistant", "content": "persona assistant", "_no_save": True},
]


def _request(contexts=None):
    request = FakeRequest("hello")
    request.contexts = list(contexts or [])
    return request


def _style_config(
    pairs=None,
    *,
    position="front",
    persona="keep",
    action_on_hit="default",
):
    return normalize_config(
        {
            "request_rail": {"enabled": False},
            "prompt_rail": {
                "rule_list": [
                    {
                        "__template_key": "style_dialogs",
                        "rule_id": "style",
                        "pairs": pairs
                        if pairs is not None
                        else [{"user": "u1", "assistant": "a1"}],
                        "position": position,
                        "persona_dialogs": persona,
                        "action_on_hit": action_on_hit,
                    }
                ]
            },
        }
    )


def _marker_entries(contexts, node_id="style"):
    return [
        entry
        for entry in contexts
        if isinstance(entry, dict)
        and entry.get(BEGIN_DIALOGS_MARKER) == node_id
    ]


class StyleDialogsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = AstrBotAdapter()

    def test_front_inserts_after_persona_block(self):
        request = _request(
            [*PERSONA_TURNS, {"role": "user", "content": "history"}]
        )

        result = self.adapter.insert_begin_dialogs(
            request, ["u1", "a1"], "front", node_id="n1"
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [entry["role"] for entry in request.contexts],
            ["user", "assistant", "user", "assistant", "user"],
        )
        self.assertEqual(request.contexts[2]["content"], "u1")
        self.assertEqual(request.contexts[3]["content"], "a1")
        for entry in request.contexts[2:4]:
            self.assertTrue(entry["_no_save"])
            self.assertEqual(entry[BEGIN_DIALOGS_MARKER], "n1")

    def test_tail_appends_after_history(self):
        request = _request([{"role": "user", "content": "history"}])

        result = self.adapter.insert_begin_dialogs(
            request, ["u1", "a1"], "tail", node_id="n1"
        )

        self.assertTrue(result.success)
        self.assertEqual(request.contexts[-2]["content"], "u1")
        self.assertEqual(request.contexts[-1]["content"], "a1")

    def test_tail_stops_before_trailing_user_when_prompt_is_empty(self):
        request = FakeRequest("")
        request.contexts = [
            {"role": "assistant", "content": "previous"},
            {"role": "user", "content": "current"},
        ]

        result = self.adapter.insert_begin_dialogs(
            request, ["u1", "a1"], "tail", node_id="n1"
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [entry.get("content") for entry in request.contexts],
            ["previous", "u1", "a1", "current"],
        )

    def test_second_run_replaces_instead_of_duplicating(self):
        request = _request([*PERSONA_TURNS])

        self.adapter.insert_begin_dialogs(request, ["u1", "a1"], "front", node_id="n1")
        self.adapter.insert_begin_dialogs(request, ["u2", "a2"], "front", node_id="n1")

        entries = _marker_entries(request.contexts, "n1")
        self.assertEqual(len(entries), 2)
        self.assertEqual([entry["content"] for entry in entries], ["u2", "a2"])

    def test_other_nodes_are_kept(self):
        request = _request([*PERSONA_TURNS])

        self.adapter.insert_begin_dialogs(request, ["u1", "a1"], "front", node_id="n1")
        self.adapter.insert_begin_dialogs(request, ["u2", "a2"], "tail", node_id="n2")

        self.assertEqual(len(_marker_entries(request.contexts, "n1")), 2)
        self.assertEqual(len(_marker_entries(request.contexts, "n2")), 2)

    def test_discard_removes_persona_but_keeps_style_entries(self):
        request = _request([*PERSONA_TURNS])
        self.adapter.insert_begin_dialogs(request, ["u1", "a1"], "front", node_id="n1")

        result = self.adapter.insert_begin_dialogs(
            request, ["u2", "a2"], "front", node_id="n2", discard_persona=True
        )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["discarded_persona"], 2)
        contents = [entry.get("content") for entry in request.contexts]
        self.assertNotIn("persona user", contents)
        self.assertNotIn("persona assistant", contents)
        self.assertEqual(len(_marker_entries(request.contexts, "n1")), 2)
        self.assertEqual(len(_marker_entries(request.contexts, "n2")), 2)

    def test_odd_dialogs_are_rejected(self):
        request = _request([])

        result = self.adapter.insert_begin_dialogs(
            request, ["u1", "a1", "u2"], "front", node_id="n1"
        )

        self.assertFalse(result.success)
        self.assertEqual(request.contexts, [])

    def test_string_contexts_can_be_normalized_then_used(self):
        request = _request([])
        request.contexts = json.dumps([{"role": "user", "content": "history"}])

        self.assertFalse(self.adapter.get_request_contexts(request).success)
        normalized = self.adapter.normalize_request_contexts(request)
        self.assertTrue(normalized.success)
        self.assertTrue(normalized.metadata["normalized"])
        self.assertIsInstance(request.contexts, list)

        inserted = self.adapter.insert_begin_dialogs(
            request, ["u1", "a1"], "tail", node_id="n1"
        )
        self.assertTrue(inserted.success)
        self.assertEqual(request.contexts[-1]["content"], "a1")

    def test_invalid_json_contexts_stay_untouched(self):
        request = _request([])
        request.contexts = "{not json"

        result = self.adapter.normalize_request_contexts(request)

        self.assertFalse(result.success)
        self.assertEqual(request.contexts, "{not json")

    def test_candidate_assignment_does_not_mutate_original(self):
        request = _request([*PERSONA_TURNS])
        candidate = copy.copy(request)

        self.adapter.insert_begin_dialogs(
            candidate, ["u1", "a1"], "front", node_id="n1"
        )

        self.assertNotIn(BEGIN_DIALOGS_MARKER, json.dumps(request.contexts))
        self.assertIsNot(request.contexts, candidate.contexts)

    def test_retry_snapshot_strips_runtime_marker(self):
        request = _request(
            [
                {
                    "role": "user",
                    "content": "u1",
                    "_no_save": True,
                    BEGIN_DIALOGS_MARKER: "style",
                },
                {
                    "role": "assistant",
                    "content": "a1",
                    "_no_save": True,
                    BEGIN_DIALOGS_MARKER: "style",
                },
            ]
        )

        result = asyncio.run(
            self.adapter.capture_retry_request_snapshot(FakeEvent("hello"), request)
        )

        self.assertTrue(result.success)
        snapshot = result.metadata["snapshot"]
        for entry in snapshot.contexts:
            self.assertNotIn(BEGIN_DIALOGS_MARKER, entry)
            self.assertTrue(entry["_no_save"])


class StyleDialogsConfigTests(unittest.TestCase):
    def test_pairs_and_defaults_are_normalized(self):
        cfg = normalize_config(
            {
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [{"user": " u ", "assistant": " a "}],
                        }
                    ]
                }
            }
        )
        config = cfg.rails["prompt_rail"].nodes[0].config
        self.assertEqual(config["pairs"], [{"user": " u ", "assistant": " a "}])
        self.assertEqual(config["position"], "front")
        self.assertEqual(config["persona_dialogs"], "keep")
        self.assertEqual(config["action_on_hit"], "observe")
        self.assertEqual(config["action_on_error"], "discard")

    def test_legacy_odd_dialogs_are_truncated_with_warning(self):
        cfg = normalize_config(
            {
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "dialogs": ["u1", "a1", "u2"],
                        }
                    ]
                }
            }
        )
        node = cfg.rails["prompt_rail"].nodes[0]
        self.assertEqual(node.config["pairs"], [{"user": "u1", "assistant": "a1"}])
        self.assertIn("even number", " ".join(node.warnings))

    def test_empty_pairs_warn_only_when_keeping_persona(self):
        keep = normalize_config(
            {
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [],
                        }
                    ]
                }
            }
        ).rails["prompt_rail"].nodes[0]
        discard = normalize_config(
            {
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [],
                            "persona_dialogs": "discard",
                        }
                    ]
                }
            }
        ).rails["prompt_rail"].nodes[0]
        self.assertIn("empty", " ".join(keep.warnings))
        self.assertNotIn("empty", " ".join(discard.warnings))

    def test_limits_truncate_pairs_and_entries(self):
        pairs = [
            {"user": f"u{index}" * 300, "assistant": f"a{index}"}
            for index in range(12)
        ]
        cfg = normalize_config(
            {
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": pairs,
                        }
                    ]
                }
            }
        )
        node = cfg.rails["prompt_rail"].nodes[0]
        self.assertLessEqual(len(node.config["pairs"]), 8)
        self.assertLessEqual(
            len(node.config["pairs"][0]["user"]), 500
        )
        self.assertIn("500", " ".join(node.warnings))

    def test_mixed_persona_modes_produce_a_warning(self):
        policy = PolicyDefinition(
            policy_id="p",
            name="P",
            components=(
                PolicyComponent(
                    component_id="keep",
                    component_type="style_dialogs",
                    rail="prompt_rail",
                    config={"pairs": [], "persona_dialogs": "keep"},
                ),
                PolicyComponent(
                    component_id="drop",
                    component_type="style_dialogs",
                    rail="prompt_rail",
                    config={"pairs": [], "persona_dialogs": "discard"},
                ),
            ),
        )
        validation = PolicyLibrary(policies=(policy,)).validate()

        self.assertTrue(validation.valid)
        self.assertIn("mixes persona_dialogs", " ".join(validation.warnings))

    def test_fixed_observe_action_warns(self):
        cfg = normalize_config(
            {
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [{"user": "u", "assistant": "a"}],
                            "action_on_hit": "block",
                        }
                    ]
                }
            }
        )
        node = cfg.rails["prompt_rail"].nodes[0]
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertIn("fixed to observe", " ".join(node.warnings))


class StyleDialogsPipelineTests(unittest.TestCase):
    def test_system_constants_are_rendered(self):
        cfg = normalize_config(
            {
                "system_constants": {"GREETING": "你好", "BOT_NAME": "小司"},
                "output_rail": {"enabled": False},
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [
                                {
                                    "user": "${GREETING}",
                                    "assistant": "我是${BOT_NAME}",
                                }
                            ],
                            "position": "tail",
                        }
                    ]
                },
            }
        )
        request = _request([{"role": "assistant", "content": "previous"}])

        asyncio.run(GuardrailPipeline(cfg).run_request(FakeEvent("hello"), request))

        entries = _marker_entries(request.contexts)
        self.assertEqual(
            [entry["content"] for entry in entries], ["你好", "我是小司"]
        )

    def test_payload_references_are_kept_literal_and_warned(self):
        cfg = normalize_config(
            {
                "output_rail": {"enabled": False},
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [
                                {"user": "${prepared.value}", "assistant": "a"}
                            ],
                            "position": "tail",
                        }
                    ]
                },
            }
        )
        node = cfg.rails["prompt_rail"].nodes[0]
        self.assertIn("payload references", " ".join(node.warnings))

        request = _request([{"role": "assistant", "content": "previous"}])
        asyncio.run(GuardrailPipeline(cfg).run_request(FakeEvent("hello"), request))

        entries = _marker_entries(request.contexts)
        self.assertEqual(entries[0]["content"], "${prepared.value}")

    def test_prompt_rail_injects_into_request_contexts(self):
        request = _request([*PERSONA_TURNS])
        pipeline = GuardrailPipeline(_style_config())

        context = asyncio.run(pipeline.run_request(FakeEvent("hello"), request))

        entries = _marker_entries(request.contexts)
        self.assertEqual(len(entries), 2)
        self.assertEqual(
            [mutation["kind"] for mutation in context.prompt_mutations],
            ["style_dialogs"],
        )

    def test_four_pairs_insert_eight_alternating_entries(self):
        pairs = [
            {"user": f"u{index}", "assistant": f"a{index}"}
            for index in range(4)
        ]
        request = _request([{"role": "user", "content": "history"}])
        pipeline = GuardrailPipeline(_style_config(pairs=pairs, position="tail"))

        asyncio.run(pipeline.run_request(FakeEvent("hello"), request))

        entries = _marker_entries(request.contexts)
        self.assertEqual(len(entries), 8)
        self.assertEqual(
            [entry["role"] for entry in entries],
            ["user", "assistant"] * 4,
        )

    def test_blocked_request_does_not_inject(self):
        cfg = normalize_config(
            {
                "request_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "block",
                            "keywords": ["hello"],
                            "action_on_hit": "block",
                        }
                    ]
                },
                "prompt_rail": {
                    "rule_list": [
                        {
                            "__template_key": "style_dialogs",
                            "rule_id": "style",
                            "pairs": [{"user": "u", "assistant": "a"}],
                        }
                    ]
                },
            }
        )
        request = _request([*PERSONA_TURNS])
        pipeline = GuardrailPipeline(cfg)

        context = asyncio.run(pipeline.run_request(FakeEvent("hello"), request))

        self.assertTrue(context.input_blocked)
        self.assertEqual(_marker_entries(request.contexts), [])

    def test_pipeline_normalizes_string_contexts_once(self):
        request = _request([])
        request.contexts = json.dumps([{"role": "user", "content": "history"}])
        pipeline = GuardrailPipeline(_style_config())

        asyncio.run(pipeline.run_request(FakeEvent("hello"), request))

        self.assertIsInstance(request.contexts, list)
        self.assertEqual(len(_marker_entries(request.contexts)), 2)


if __name__ == "__main__":
    unittest.main()
