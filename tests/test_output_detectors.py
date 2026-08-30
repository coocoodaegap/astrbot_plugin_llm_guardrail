import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from components import evaluate_output_detector
from config import normalize_config
from core import RailContext


def _node(config, text):
    normalized = normalize_config(
        {
            "output_rail": {
                "rule_list": [
                    {
                        "__template_key": "poor_quality_detector",
                        "rule_id": "detector",
                        **config,
                    }
                ]
            }
        }
    )
    node = normalized.rails["output_rail"].nodes[0]
    context = RailContext(None, None, None, "test:umo", "request", "request", text)
    return node, context


class PoorQualityDetectorTests(unittest.TestCase):
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

    def test_rejects_sanitize_and_bounds_parameters(self):
        node, _context = _node(
            {
                "action_on_hit": "sanitize",
                "min_signal_families": 99,
                "max_punctuation_ratio": 0,
            },
            "hello",
        )

        self.assertEqual(node.config["action_on_hit"], "default")
        self.assertEqual(node.config["min_signal_families"], 1)
        self.assertEqual(node.config["max_punctuation_ratio"], 0.95)
        self.assertTrue(any("sanitize is only supported" in warning for warning in node.warnings))


if __name__ == "__main__":
    unittest.main()
