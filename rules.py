"""P0 rule evaluators."""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from .config import NormalizedRule
    from .core import (
        RailContext,
        RuleSignal,
        logic_gate_input_specs,
        logic_input_value,
        make_result,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedRule
    from core import (
        RailContext,
        RuleSignal,
        logic_gate_input_specs,
        logic_input_value,
        make_result,
    )


def evaluate_text_rule(
    rule: NormalizedRule, context: RailContext, text: str
):
    if rule.template_key == "plain_keywords":
        return evaluate_plain_keywords(rule, text)
    if rule.template_key == "regex_pattern":
        return evaluate_regex_pattern(rule, text)
    if rule.template_key == "logic_gate":
        return evaluate_logic_gate(rule, context)
    return make_result(
        rule,
        matched=False,
        executed=False,
        skipped_reason="unsupported_template",
    )


def evaluate_plain_keywords(rule: NormalizedRule, text: str):
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
    }
    return make_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        hits=hits,
        metadata={"score": score, "threshold": threshold},
        signal=RuleSignal(value=score, truthy=matched, payload=payload),
    )


def evaluate_regex_pattern(rule: NormalizedRule, text: str):
    source = text or ""
    pattern = rule.config.get("_compiled_pattern")
    if pattern is None:
        return make_result(
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
    }
    return make_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        hits=hits,
        metadata={"hit_count": len(hits)},
        signal=RuleSignal(value=len(hits), truthy=matched, payload=payload),
    )


def evaluate_logic_gate(rule: NormalizedRule, context: RailContext):
    specs = logic_gate_input_specs(rule)
    values = [
        logic_input_value(spec, context.results[spec.target])
        for spec in specs
    ]
    gate = str(rule.config.get("gate", "all"))
    matched = all(values) if gate == "all" else any(values)
    if bool(rule.config.get("invert", False)):
        matched = not matched
    payload = {
        "inputs": {
            spec.raw or spec.target: value
            for spec, value in zip(specs, values, strict=False)
        }
    }
    return make_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        metadata=payload,
        signal=RuleSignal(value=matched, truthy=matched, payload=payload),
    )


def evaluate_llm_review_response(
    rule: NormalizedRule, context: RailContext, response_text: str
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
    return make_result(
        rule,
        matched=matched,
        action_on_hit=str(rule.config.get("action_on_hit", "default")),
        metadata=metadata,
        signal=RuleSignal(value=matched, truthy=matched, payload=payload),
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


def apply_literal_replacements(
    text: str, hits: list[dict[str, Any]], replacement: str
) -> str:
    if not text or not hits:
        return text
    result = text
    values = []
    seen = set()
    for hit in hits:
        value = str(hit.get("value", ""))
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    for value in sorted(values, key=len, reverse=True):
        result = re.sub(re.escape(value), replacement, result, flags=re.IGNORECASE)
    return result


def clip_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text or ""
    source = text or ""
    return source[:max_chars]
