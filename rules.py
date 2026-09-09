"""Evaluators for reusable business-rule templates."""

from __future__ import annotations

import json
from typing import Any

try:
    from .config import NormalizedNode
    from .core import (
        RailContext,
        NodeSignal,
        NodeResult,
        make_node_result,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedNode
    from core import (
        RailContext,
        NodeSignal,
        NodeResult,
        make_node_result,
    )


def evaluate_text_rule(
    rule: NormalizedNode, context: RailContext, text: str
):
    if rule.template_key == "plain_keywords":
        return evaluate_plain_keywords(rule, text)
    if rule.template_key == "regex_pattern":
        return evaluate_regex_pattern(rule, text)
    return make_node_result(
        rule,
        matched=False,
        executed=False,
        skipped_reason="unsupported_template",
    )


def evaluate_plain_keywords(rule: NormalizedNode, text: str):
    source = text or ""
    folded = source.casefold()
    hits: list[dict[str, Any]] = []
    score = 0.0
    matched_keyword_keys: set[str] = set()
    weight_map = rule.config.get("_keyword_weight_map", {})
    if not isinstance(weight_map, dict):
        weight_map = {}

    for keyword in rule.config.get("keywords", []):
        keyword_text = str(keyword)
        if not keyword_text:
            continue
        key = keyword_text.casefold()
        start = 0
        keyword_matched = False
        while True:
            index = folded.find(key, start)
            if index < 0:
                break
            end = index + len(keyword_text)
            weight = float(weight_map.get(key, 1.0))
            hits.append(
                {
                    "kind": "keyword",
                    "value": source[index:end],
                    "keyword": keyword_text,
                    "start": index,
                    "end": end,
                    "weight": weight,
                }
            )
            keyword_matched = True
            start = max(end, index + 1)
        if keyword_matched and key not in matched_keyword_keys:
            score += float(weight_map.get(key, 1.0))
            matched_keyword_keys.add(key)

    threshold = float(rule.config.get("threshold", 1.0))
    matched = score >= threshold
    payload = {
        "score": score,
        "threshold": threshold,
        "matched_text": " ".join(hit["value"] for hit in hits[:10]),
        "sanitized": apply_span_replacements(
            source, hits, str(rule.config.get("sanitizer", ""))
        ),
    }
    return make_node_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        hits=hits,
        metadata={"score": score, "threshold": threshold},
        signal=NodeSignal(value=score, truthy=matched, payload=payload),
    )


def evaluate_regex_pattern(rule: NormalizedNode, text: str):
    source = text or ""
    pattern = rule.config.get("_compiled_pattern")
    if pattern is None:
        return make_node_result(
            rule,
            matched=False,
            executed=False,
            skipped_reason="invalid_regex",
        )

    hits: list[dict[str, Any]] = []
    for match in pattern.finditer(source):
        hits.append(
            {
                "kind": "regex",
                "value": match.group(0),
                "pattern": str(rule.config.get("pattern", "")),
                "start": match.start(),
                "end": match.end(),
            }
        )
    matched = bool(hits)
    payload = {
        "matched_text": " ".join(hit["value"] for hit in hits[:10]),
        "pattern": str(rule.config.get("pattern", "")),
        "sanitized": apply_span_replacements(
            source, hits, str(rule.config.get("sanitizer", ""))
        ),
    }
    return make_node_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        hits=hits,
        metadata={"hit_count": len(hits)},
        signal=NodeSignal(value=len(hits), truthy=matched, payload=payload),
    )


def evaluate_llm_review_response(
    rule: NormalizedNode, context: RailContext, response_text: str
):
    parsed = _parse_llm_review_json(response_text)
    matched = parsed.get("matched")
    if not isinstance(matched, bool):
        raise ValueError("llm_review response matched must be boolean")

    payload = parsed.get("payload", {})
    if not isinstance(payload, dict):
        context.warnings.append(
            f"{rule.rule_id}.payload is not an object; stored as raw_payload"
        )
        payload = {"raw_payload": payload}

    metadata = {
        "payload": payload,
        "raw_response": clip_text(response_text, 2000),
    }
    return make_node_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        metadata=metadata,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


def _parse_llm_review_json(response_text: str) -> dict[str, Any]:
    text = (response_text or "").strip()
    if not text:
        raise ValueError("llm_review response is empty")
    start = text.find("{")
    if start < 0:
        raise ValueError("llm_review response has no JSON object")
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"llm_review response JSON parse failed: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("llm_review response JSON must be an object")
    return value


def evaluate_rag_judge_evidence(
    rule: NormalizedNode, evidence: list[dict[str, Any]]
) -> NodeResult:
    try:
        min_score = float(rule.config.get("min_score", 0.72))
    except (TypeError, ValueError):
        min_score = 0.72
    score_values = [
        float(item["score"])
        for item in evidence
        if isinstance(item.get("score"), (int, float))
    ]
    score_available = bool(score_values)
    max_score = max(score_values) if score_values else None
    normalized_evidence = [
        {
            "text": str(item.get("text", "") or ""),
            "score": item.get("score"),
            "metadata": item.get("metadata", {}),
        }
        for item in evidence
    ]
    matched_evidence = [
        item
        for item in normalized_evidence
        if (
            not score_available
            or (
                isinstance(item.get("score"), (int, float))
                and float(item["score"]) >= min_score
            )
        )
    ]
    matched = bool(matched_evidence)
    # top_k is applied by the adapter; downstream payloads retain complete records.
    payload = {
        "evidence_count": len(evidence),
        "evidence": normalized_evidence,
        "matched_evidence_count": len(matched_evidence),
        "matched_text": _format_rag_matched_text(rule, matched_evidence),
        "score_available": score_available,
        "max_score": max_score,
        "min_score": min_score,
    }
    hits = [
        {
            "kind": "rag_evidence",
            "value": item["text"],
            "score": item.get("score"),
            "metadata": item.get("metadata", {}),
        }
        for item in normalized_evidence
    ]
    signal_value = max_score if max_score is not None else len(evidence)
    return make_node_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        hits=hits,
        metadata=payload,
        signal=NodeSignal(
            value=signal_value,
            truthy=matched,
            payload=payload,
        ),
    )


def _format_rag_matched_text(
    rule: NormalizedNode,
    evidence: list[dict[str, Any]],
) -> str:
    item_template = str(rule.config.get("value_item_template", "${value}"))
    separator = str(rule.config.get("value_separator", " "))
    return separator.join(
        item_template
        .replace("${value}", str(item.get("text", "") or ""))
        .replace("${source}", _rag_evidence_source(item.get("metadata")))
        for item in evidence
    )


def _rag_evidence_source(metadata: Any) -> str:
    if not isinstance(metadata, dict):
        return ""
    for key in ("kb_name", "kb_id", "doc_name", "doc_id", "source"):
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def apply_span_replacements(
    text: str, hits: list[dict[str, Any]], replacement: str
) -> str:
    if not text or not hits:
        return text
    result = text
    last_start = len(result) + 1
    for hit in sorted(hits, key=lambda item: int(item.get("start", -1)), reverse=True):
        try:
            start = int(hit.get("start", -1))
            end = int(hit.get("end", -1))
        except (TypeError, ValueError):
            continue
        if start < 0 or end < start or end > len(result):
            continue
        if end > last_start:
            continue
        result = result[:start] + replacement + result[end:]
        last_start = start
    return result


def clip_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text or ""
    source = text or ""
    return source[:max_chars]
