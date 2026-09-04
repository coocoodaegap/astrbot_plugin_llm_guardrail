import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from components import evaluate_output_detector
from config import normalize_config
from constants import INTERNAL_MARKER
from core import RailContext


def _output_node(template_key, config, request, text):
    normalized = normalize_config(
        {
            "output_rail": {
                "rule_list": [
                    {
                        "__template_key": template_key,
                        "rule_id": "detector",
                        **config,
                    }
                ]
            }
        }
    )
    node = normalized.rails["output_rail"].nodes[0]
    context = RailContext(None, None, None, "test:umo", request, request, text)
    return node, context


def _node(config, text):
    return _output_node("poor_quality_detector", config, "request", text)


class PoorQualityDetectorTests(unittest.TestCase):
    def test_poor_quality_error_envelope_materials_preserve_current_boundaries(self):
        samples = {
            '{"error":"upstream unavailable","status":503}': True,
            "Error: upstream unavailable (HTTP 503)": True,
            "ValueError: invalid response": True,
            "The word error does not mean this reply failed.": False,
            '{"title":"error budget","count":1}': False,
        }
        for text, expected_match in samples.items():
            with self.subTest(text=text):
                node, context = _node({}, text)
                result = evaluate_output_detector(node, context, text)

                self.assertEqual(result.matched, expected_match)
                self.assertIn("core-materials-v8", str(result.metadata))

    def test_detects_clear_generation_failures_without_returning_text(self):
        samples = {
            "   \u200b\n": "empty_output",
            "?!?!?!": "punctuation_only",
            "x" * 80: "repeat_run",
            "same response line\n" * 4: "duplicate_lines",
            "Traceback (most recent call last):\nFile \"app.py\", line 2\nValueError: bad": "unformatted_error_envelope",
        }
        for text, expected_code in samples.items():
            with self.subTest(expected_code=expected_code):
                node, context = _node({}, text)
                result = evaluate_output_detector(node, context, text)

                self.assertTrue(result.matched)
                self.assertIn(expected_code, result.metadata["reason_codes"])
                self.assertGreater(result.metadata["score"], 0)
                self.assertNotIn(text, str(result.metadata))

    def test_does_not_judge_short_answers_or_fenced_error_examples(self):
        samples = (
            "是",
            "OK",
            "✅",
            "```text\nTraceback (most recent call last):\nFile \"app.py\", line 2\nValueError: example\n```",
            "A normal explanation with a short list:\n- first\n- second",
        )
        for text in samples:
            with self.subTest(text=text):
                node, context = _node({}, text)
                result = evaluate_output_detector(node, context, text)

                self.assertFalse(result.matched)
                self.assertEqual(result.metadata["score"], 0)

    def test_multiple_signal_threshold_and_truncation_are_explicit(self):
        repeated = "x" * 80
        node, context = _node({"min_signal_families": 2}, repeated)
        result = evaluate_output_detector(node, context, repeated)

        self.assertFalse(result.matched)
        self.assertEqual(result.metadata["reason_codes"], ["repeat_run"])

        long_text = "x" * 300
        node, context = _node({"scan_limit_chars": 256}, long_text)
        result = evaluate_output_detector(node, context, long_text)

        self.assertTrue(result.matched)
        self.assertTrue(result.metadata["scan_truncated"])
        self.assertEqual(result.metadata["raw_char_count"], len(long_text))

    def test_falls_back_from_unknown_action_and_bounds_parameters(self):
        node, _context = _node(
            {
                "action_on_hit": "unknown_action",
                "min_signal_families": 99,
                "max_punctuation_ratio": 0,
            },
            "hello",
        )

        self.assertEqual(node.config["min_signal_families"], 1)
        self.assertEqual(node.config["max_punctuation_ratio"], 0.95)
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertTrue(any("fallback to observe" in warning for warning in node.warnings))


class MetadataLeakageDetectorTests(unittest.TestCase):
    def test_detects_internal_control_marker_without_returning_it(self):
        response = f"Unexpected control value: {INTERNAL_MARKER}"
        node, context = _output_node(
            "metadata_leakage_detector", {}, "request", response,
        )
        result = evaluate_output_detector(node, context, response)

        self.assertTrue(result.matched)
        self.assertEqual(result.metadata["reason_codes"], ["internal_control_marker"])
        self.assertEqual(result.metadata["core_material_version"], "core-materials-v8")
        self.assertNotIn(INTERNAL_MARKER, str(result.metadata))

    def test_bounds_tool_structure_scanning_before_later_candidates(self):
        response = (
            '{"title":"ordinary object"} '
            '{"name":"calendar.create","arguments":{"title":"meeting"}}'
        )
        limited_node, limited_context = _output_node(
            "metadata_leakage_detector", {"max_structures": 1}, "request", response,
        )
        complete_node, complete_context = _output_node(
            "metadata_leakage_detector", {"max_structures": 3}, "request", response,
        )

        limited = evaluate_output_detector(limited_node, limited_context, response)
        complete = evaluate_output_detector(complete_node, complete_context, response)

        self.assertFalse(limited.matched)
        self.assertTrue(limited.metadata["structure_scan_limited"])
        self.assertTrue(complete.matched)
        self.assertFalse(complete.metadata["structure_scan_limited"])
        self.assertEqual(complete.metadata["reason_codes"], ["tool_call_envelope"])


class LanguageDriftDetectorTests(unittest.TestCase):
    def test_language_drift_materials_preserve_current_boundaries(self):
        chinese_request = "请用中文回答这个问题。"
        chinese_response = "这是符合要求的中文回复内容。" * 12
        english_response = "This response is deliberately written in English instead. " * 8
        contaminated_response = chinese_response + " مرحبا"
        fenced_response = chinese_response + "\n```python\nprint('hello world')\n```"

        cases = (
            (chinese_request, chinese_response, False, ()),
            (chinese_request, english_response, True, ("dominant_script_drift",)),
            (
                chinese_request,
                contaminated_response,
                True,
                ("foreign_script_contamination",),
            ),
            (chinese_request, fenced_response, False, ()),
            ("请用中文回答。", "hello", False, ()),
        )
        for request, response, expected_match, expected_codes in cases:
            with self.subTest(request=request, expected_codes=expected_codes):
                node, context = _output_node(
                    "language_drift_detector", {}, request, response,
                )
                result = evaluate_output_detector(node, context, response)

                self.assertEqual(result.matched, expected_match)
                self.assertEqual(
                    tuple(result.metadata["reason_codes"]), expected_codes,
                )
                self.assertEqual(result.metadata["expectation_source"], "explicit")
                self.assertEqual(result.metadata["core_material_version"], "core-materials-v8")
                self.assertNotIn(response, str(result.metadata))

    def test_uses_an_unambiguous_inferred_baseline_and_ignores_technical_tokens(self):
        request = "Please explain the deployment steps in enough detail for a new operator. " * 3
        same_script_response = "The API returns JSON and HTTP status details for the deployment. " * 4
        foreign_response = "这是完全不同文字脚本的回复内容。" * 12
        ambiguous_request = "Please reply in English and Chinese."
        quoted_request = (
            "Please explain why the example \"reply in Chinese\" appears in "
            "documentation and describe it in enough English detail."
        )

        node, context = _output_node(
            "language_drift_detector", {}, request, same_script_response,
        )
        same_script = evaluate_output_detector(node, context, same_script_response)
        self.assertFalse(same_script.matched)
        self.assertEqual(same_script.metadata["expectation_source"], "inferred")

        node, context = _output_node(
            "language_drift_detector", {}, request, foreign_response,
        )
        foreign = evaluate_output_detector(node, context, foreign_response)
        self.assertTrue(foreign.matched)
        self.assertIn("dominant_script_drift", foreign.metadata["reason_codes"])

        node, context = _output_node(
            "language_drift_detector", {}, ambiguous_request, foreign_response,
        )
        ambiguous = evaluate_output_detector(node, context, foreign_response)
        self.assertFalse(ambiguous.matched)
        self.assertEqual(ambiguous.metadata["expectation_source"], "unavailable")

        node, context = _output_node(
            "language_drift_detector", {}, quoted_request, same_script_response,
        )
        quoted = evaluate_output_detector(node, context, same_script_response)
        self.assertFalse(quoted.matched)
        self.assertEqual(quoted.metadata["expectation_source"], "inferred")

    def test_normalizes_all_public_parameters_and_falls_back_from_unknown_action(self):
        node, _context = _output_node(
            "language_drift_detector",
            {
                "scan_limit_chars": 1,
                "min_analyzable_chars": 1,
                "dominant_script_ratio": 0.1,
                "max_baseline_script_ratio": 0.9,
                "min_foreign_script_run_chars": 1,
                "action_on_hit": "unknown_action",
            },
            "请用中文回答。",
            "中文回复。",
        )

        self.assertEqual(node.config["scan_limit_chars"], 12000)
        self.assertEqual(node.config["min_analyzable_chars"], 80)
        self.assertEqual(node.config["dominant_script_ratio"], 0.7)
        self.assertEqual(node.config["max_baseline_script_ratio"], 0.2)
        self.assertEqual(node.config["min_foreign_script_run_chars"], 4)
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertTrue(any("fallback to observe" in warning for warning in node.warnings))

    def test_handles_japanese_han_boundary_and_korean_drift(self):
        han_response = "这是只包含汉字的回复内容。" * 12
        japanese_response = "これは日本語だけで書かれた回答です。" * 12

        node, context = _output_node(
            "language_drift_detector", {}, "日本語で回答してください。", han_response,
        )
        japanese_boundary = evaluate_output_detector(node, context, han_response)
        self.assertFalse(japanese_boundary.matched)
        self.assertEqual(japanese_boundary.metadata["expectation_source"], "explicit")

        node, context = _output_node(
            "language_drift_detector", {}, "请用中文回答。", japanese_response,
        )
        chinese_to_japanese = evaluate_output_detector(node, context, japanese_response)
        self.assertTrue(chinese_to_japanese.matched)
        self.assertIn(
            "dominant_script_drift", chinese_to_japanese.metadata["reason_codes"],
        )

        node, context = _output_node(
            "language_drift_detector", {}, "한국어로 답변해주세요.", han_response,
        )
        korean_to_han = evaluate_output_detector(node, context, han_response)
        self.assertTrue(korean_to_han.matched)
        self.assertEqual(korean_to_han.metadata["expectation_source"], "explicit")


class FormatViolationDetectorTests(unittest.TestCase):
    def test_format_violation_materials_preserve_current_boundaries(self):
        cases = (
            ("Return a JSON object.", '{"answer":"ok"}', False, ()),
            (
                "Return a JSON object.",
                "The answer is ready.",
                True,
                ("requested_json_invalid",),
            ),
            (
                "Return a JSON object.",
                '["answer"]',
                True,
                ("requested_json_wrong_top_level",),
            ),
            (
                "Return a JSON array.",
                '{"answer":"ok"}',
                True,
                ("requested_json_wrong_top_level",),
            ),
            (
                "Please reply in a single line.",
                "first line\nsecond line",
                True,
                ("requested_single_line_multiline",),
            ),
            (
                "只输出纯文本。",
                "# Heading\n- item",
                True,
                ("requested_plain_text_markdown",),
            ),
            (
                "Please use a code fence.",
                "plain answer",
                True,
                ("requested_fence_missing",),
            ),
            (
                "Do not use a code fence.",
                "```text\nexample\n```",
                True,
                ("requested_fence_present",),
            ),
        )
        for request, response, expected_match, expected_codes in cases:
            with self.subTest(request=request, expected_codes=expected_codes):
                node, context = _output_node(
                    "format_violation_detector", {}, request, response,
                )
                result = evaluate_output_detector(node, context, response)

                self.assertEqual(result.matched, expected_match)
                self.assertEqual(
                    tuple(result.metadata["reason_codes"]), expected_codes,
                )
                self.assertEqual(result.metadata["core_material_version"], "core-materials-v8")
                self.assertNotIn(request, str(result.metadata))
                self.assertNotIn(response, str(result.metadata))

    def test_requires_a_command_and_fails_open_for_conflicting_contracts(self):
        no_command_request = (
            "Explain the JSON format and compare a code fence with Markdown."
        )
        generic_json_request = "Return JSON."
        conflicting_request = "Reply only in a JSON object and JSON array."
        quoted_request = 'Explain why the example "reply only in JSON" is useful.'

        for request in (
            no_command_request,
            generic_json_request,
            conflicting_request,
            quoted_request,
        ):
            with self.subTest(request=request):
                node, context = _output_node(
                    "format_violation_detector", {}, request, "ordinary explanation",
                )
                result = evaluate_output_detector(node, context, "ordinary explanation")

                self.assertFalse(result.matched)
                self.assertEqual(result.metadata["reason_codes"], [])
                self.assertEqual(result.metadata["active_contract_count"], 0)

    def test_surrounding_whitespace_behavior_is_explicitly_configurable(self):
        request = "Return a JSON object."
        response = "\n{}\n"
        default_node, default_context = _output_node(
            "format_violation_detector", {}, request, response,
        )
        strict_node, strict_context = _output_node(
            "format_violation_detector",
            {"allow_surrounding_whitespace": False},
            request,
            response,
        )

        self.assertFalse(
            evaluate_output_detector(default_node, default_context, response).matched
        )
        strict_result = evaluate_output_detector(strict_node, strict_context, response)
        self.assertTrue(strict_result.matched)
        self.assertEqual(strict_result.metadata["reason_codes"], ["requested_json_invalid"])

    def test_normalizes_all_public_parameters_and_falls_back_from_unknown_action(self):
        node, _context = _output_node(
            "format_violation_detector",
            {
                "scan_limit_chars": 1,
                "max_contract_candidates": 0,
                "allow_surrounding_whitespace": False,
                "action_on_hit": "unknown_action",
            },
            "Return a JSON object.",
            "{}",
        )

        self.assertEqual(node.config["scan_limit_chars"], 12000)
        self.assertEqual(node.config["max_contract_candidates"], 8)
        self.assertFalse(node.config["allow_surrounding_whitespace"])
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertTrue(any("fallback to observe" in warning for warning in node.warnings))


class RefusalLeakageDetectorTests(unittest.TestCase):
    def test_refusal_leakage_materials_preserve_current_boundaries(self):
        cases = (
            (
                "I cannot provide that because my system instructions are private.",
                True,
            ),
            ("我无法提供，因为这涉及内部安全策略。", True),
            ("I cannot disclose my developer instructions.", True),
            ("I cannot help with that request.", False),
            ("I cannot help because it could cause harm.", False),
            ("System instructions are a prompt-design concept.", False),
            ('The quoted example says "I cannot disclose my system prompt."', False),
            (
                "```text\nI cannot disclose my system prompt because it is private.\n```",
                False,
            ),
        )
        for response, expected_match in cases:
            with self.subTest(response=response):
                node, context = _output_node(
                    "refusal_leakage_detector", {}, "request", response,
                )
                result = evaluate_output_detector(node, context, response)

                self.assertEqual(result.matched, expected_match)
                self.assertEqual(
                    result.metadata["reason_codes"],
                    ["refusal_policy_exposure"] if expected_match else [],
                )
                self.assertEqual(result.metadata["core_material_version"], "core-materials-v8")
                self.assertNotIn(response, str(result.metadata))

    def test_relation_window_and_evidence_threshold_are_configurable(self):
        two_family_response = "I cannot disclose my system instructions."
        default_node, default_context = _output_node(
            "refusal_leakage_detector", {}, "request", two_family_response,
        )
        strict_node, strict_context = _output_node(
            "refusal_leakage_detector",
            {"min_evidence_families": 3},
            "request",
            two_family_response,
        )
        self.assertTrue(
            evaluate_output_detector(default_node, default_context, two_family_response).matched
        )
        self.assertFalse(
            evaluate_output_detector(strict_node, strict_context, two_family_response).matched
        )

        three_family_response = (
            "Because of my system instructions, I cannot provide that."
        )
        causal_node, causal_context = _output_node(
            "refusal_leakage_detector",
            {"min_evidence_families": 3},
            "request",
            three_family_response,
        )
        self.assertTrue(
            evaluate_output_detector(causal_node, causal_context, three_family_response).matched
        )

        distant_response = "I cannot comply " + ("x" * 180) + " system instructions"
        bounded_node, bounded_context = _output_node(
            "refusal_leakage_detector", {}, "request", distant_response,
        )
        expanded_node, expanded_context = _output_node(
            "refusal_leakage_detector",
            {"max_relation_gap_chars": 256},
            "request",
            distant_response,
        )
        self.assertFalse(
            evaluate_output_detector(bounded_node, bounded_context, distant_response).matched
        )
        self.assertTrue(
            evaluate_output_detector(expanded_node, expanded_context, distant_response).matched
        )

    def test_normalizes_all_public_parameters_and_falls_back_from_unknown_action(self):
        node, _context = _output_node(
            "refusal_leakage_detector",
            {
                "scan_limit_chars": 1,
                "max_relation_gap_chars": 1,
                "min_evidence_families": 99,
                "ignore_fenced_code": False,
                "action_on_hit": "unknown_action",
            },
            "request",
            "I cannot disclose my system instructions.",
        )

        self.assertEqual(node.config["scan_limit_chars"], 12000)
        self.assertEqual(node.config["max_relation_gap_chars"], 160)
        self.assertEqual(node.config["min_evidence_families"], 2)
        self.assertFalse(node.config["ignore_fenced_code"])
        self.assertEqual(node.config["action_on_hit"], "observe")
        self.assertTrue(any("fallback to observe" in warning for warning in node.warnings))


if __name__ == "__main__":
    unittest.main()
