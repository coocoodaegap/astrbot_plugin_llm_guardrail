import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from components import evaluate_logic_gate
from core import RailContext
from rules import (
    apply_literal_replacements,
    apply_span_replacements,
    evaluate_llm_review_response,
    evaluate_plain_keywords,
    evaluate_rag_judge_evidence,
    evaluate_regex_pattern,
)


class RuleEvaluatorTests(unittest.TestCase):
    def test_plain_keywords_scores_unique_keywords_case_insensitive(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "risk",
                            "keywords": ["Secret", "token"],
                            "keyword_weights": ["Secret:2"],
                            "threshold": 3,
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]
        result = evaluate_plain_keywords(rule, "secret SECRET token")

        self.assertTrue(result.matched)
        self.assertEqual(result.metadata["score"], 3.0)
        self.assertEqual(len(result.hits), 3)

    def test_regex_pattern_records_spans(self):
        cfg = normalize_config(
            {
                "output_rail": {
                    "rule_list": [
                        {
                            "__template_key": "regex_pattern",
                            "rule_id": "digits",
                            "pattern": r"\d+",
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["output_rail"].rules[0]
        result = evaluate_regex_pattern(rule, "abc 123")

        self.assertTrue(result.matched)
        self.assertEqual(result.hits[0]["start"], 4)
        self.assertEqual(result.hits[0]["value"], "123")

    def test_logic_gate_uses_existing_rule_results(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "a",
                            "keywords": ["a"],
                        },
                        {
                            "__template_key": "plain_keywords",
                            "rule_id": "b",
                            "keywords": ["b"],
                        },
                        {
                            "__template_key": "logic_gate",
                            "rule_id": "any_ab",
                            "gate": "any",
                            "inputs": ["a", "b"],
                        },
                    ]
                }
            }
        )
        rail = cfg.rails["input_rail"]
        ctx = RailContext(None, None, None, "", "", "", "")
        ctx.results["a"] = evaluate_plain_keywords(rail.rules[0], "a")
        ctx.results["b"] = evaluate_plain_keywords(rail.rules[1], "x")

        result = evaluate_logic_gate(rail.rules[2], ctx)

        self.assertTrue(result.matched)
        self.assertEqual(result.metadata["inputs"], {"a": True, "b": False})

    def test_replacement_helpers(self):
        text = "abc SECRET def"
        hits = [{"start": 4, "end": 10, "value": "SECRET"}]

        self.assertEqual(apply_span_replacements(text, hits, "[x]"), "abc [x] def")
        self.assertEqual(
            apply_literal_replacements("SECRET secret", hits, ""),
            " ",
        )

    def test_llm_review_response_parses_matched_payload(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "llm_review",
                            "rule_id": "review",
                            "audit_prompt": "Judge risk.",
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]
        ctx = RailContext(None, None, None, "", "", "", "")

        result = evaluate_llm_review_response(
            rule,
            ctx,
            '```json\n{"matched": true, "payload": {"reason": "risk"}}\n```',
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.signal.payload["reason"], "risk")
        self.assertEqual(result.metadata["payload"]["reason"], "risk")

    def test_llm_review_response_requires_boolean_matched(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "llm_review",
                            "rule_id": "review",
                            "audit_prompt": "Judge risk.",
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]
        ctx = RailContext(None, None, None, "", "", "", "")

        with self.assertRaises(ValueError):
            evaluate_llm_review_response(
                rule,
                ctx,
                '{"matched": "true", "payload": {}}',
            )

    def test_rag_judge_evidence_uses_min_score(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": ["policy"],
                            "min_score": 0.7,
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]

        result = evaluate_rag_judge_evidence(
            rule,
            [{"text": "matched evidence", "score": 0.8, "metadata": {}}],
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.signal.payload["max_score"], 0.8)
        self.assertEqual(result.signal.payload["evidence_count"], 1)

    def test_rag_judge_evidence_allows_zero_min_score(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": ["policy"],
                            "min_score": 0,
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]

        result = evaluate_rag_judge_evidence(
            rule,
            [{"text": "low score evidence", "score": 0.1, "metadata": {}}],
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.signal.payload["min_score"], 0.0)

    def test_rag_judge_evidence_without_score_is_still_visible(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": ["policy"],
                            "min_score": 0.99,
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]

        result = evaluate_rag_judge_evidence(
            rule,
            [{"text": "scoreless evidence", "score": None, "metadata": {}}],
        )

        self.assertTrue(result.matched)
        self.assertFalse(result.signal.payload["score_available"])
        self.assertIsNone(result.signal.payload["max_score"])


if __name__ == "__main__":
    unittest.main()
