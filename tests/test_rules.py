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

    def test_span_replacements(self):
        text = "abc SECRET def"
        hits = [{"start": 4, "end": 10, "value": "SECRET"}]

        self.assertEqual(apply_span_replacements(text, hits, "[x]"), "abc [x] def")

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
        self.assertEqual(result.signal.payload["matched_evidence_count"], 1)

    def test_rag_judge_matched_text_only_formats_evidence_at_or_above_threshold(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": ["policy"],
                            "min_score": 0.7,
                            "value_item_template": "[${source}] ${value}",
                            "value_separator": "\n---\n",
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]

        result = evaluate_rag_judge_evidence(
            rule,
            [
                {
                    "text": "strong evidence",
                    "score": 0.91,
                    "metadata": {"kb_name": "positive"},
                },
                {
                    "text": "boundary evidence",
                    "score": 0.7,
                    "metadata": {"doc_name": "case.md"},
                },
                {
                    "text": "low evidence must stay out",
                    "score": 0.69,
                    "metadata": {"kb_name": "positive"},
                },
            ],
        )

        payload = result.signal.payload
        self.assertTrue(result.matched)
        self.assertEqual(payload["evidence_count"], 3)
        self.assertEqual(len(payload["evidence"]), 3)
        self.assertEqual(payload["matched_evidence_count"], 2)
        self.assertEqual(
            payload["matched_text"],
            "[positive] strong evidence\n---\n[case.md] boundary evidence",
        )
        self.assertNotIn("low evidence", payload["matched_text"])

    def test_rag_judge_low_scored_evidence_remains_visible_but_not_matched(self):
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
            [{"text": "low evidence", "score": 0.2, "metadata": {}}],
        )

        self.assertFalse(result.matched)
        self.assertEqual(result.signal.payload["evidence_count"], 1)
        self.assertEqual(result.signal.payload["matched_evidence_count"], 0)
        self.assertEqual(result.signal.payload["matched_text"], "")
        self.assertEqual(result.signal.payload["evidence"][0]["text"], "low evidence")

    def test_rag_judge_preserves_all_records_and_full_text(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": ["policy"],
                            "min_score": 0.7,
                            "value_separator": "|",
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]
        for score in (0.9, None):
            with self.subTest(score=score):
                evidence = [
                    {
                        "text": f"item-{index}\n" + "完整证据。" * 150 + f"\nend-{index}",
                        "score": score,
                        "metadata": {"doc_name": f"case-{index}"},
                    }
                    for index in range(10)
                ]

                result = evaluate_rag_judge_evidence(rule, evidence)

                self.assertTrue(result.matched)
                self.assertEqual(result.signal.payload["evidence_count"], 10)
                self.assertEqual(result.signal.payload["evidence"], evidence)
                self.assertEqual(result.metadata["evidence"], evidence)
                self.assertEqual(result.signal.payload["matched_evidence_count"], 10)
                self.assertEqual(
                    result.signal.payload["matched_text"],
                    "|".join(item["text"] for item in evidence),
                )
                self.assertEqual(
                    [hit["value"] for hit in result.hits],
                    [item["text"] for item in evidence],
                )

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
        self.assertEqual(result.signal.payload["matched_evidence_count"], 1)
        self.assertEqual(result.signal.payload["matched_text"], "scoreless evidence")

    def test_rag_judge_excludes_scoreless_items_when_scored_evidence_is_available(self):
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
            [
                {"text": "qualified", "score": 0.8, "metadata": {}},
                {"text": "unknown score", "score": None, "metadata": {}},
            ],
        )

        self.assertTrue(result.matched)
        self.assertEqual(result.signal.payload["matched_evidence_count"], 1)
        self.assertEqual(result.signal.payload["matched_text"], "qualified")

    def test_rag_judge_normalizes_invalid_value_template_and_preserves_separator(self):
        cfg = normalize_config(
            {
                "input_rail": {
                    "rule_list": [
                        {
                            "__template_key": "rag_judge",
                            "rule_id": "rag",
                            "knowledge_bases": ["policy"],
                            "value_item_template": "${score}: ${value}",
                            "value_separator": " | ",
                        }
                    ]
                }
            }
        )
        rule = cfg.rails["input_rail"].rules[0]

        self.assertEqual(rule.config["value_item_template"], "${value}")
        self.assertEqual(rule.config["value_separator"], " | ")
        self.assertTrue(
            any("only supports ${value} and ${source}" in item for item in cfg.warnings)
        )


if __name__ == "__main__":
    unittest.main()
