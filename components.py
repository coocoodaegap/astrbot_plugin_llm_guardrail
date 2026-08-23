"""Evaluators for policy-local electronic components."""

from __future__ import annotations

from collections import Counter
import json
import re
import unicodedata

try:
    from .config import NormalizedNode
    from .core import (
        NodeSignal,
        RailContext,
        logic_gate_input_specs,
        logic_input_value,
        make_node_result,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from config import NormalizedNode
    from core import (
        NodeSignal,
        RailContext,
        logic_gate_input_specs,
        logic_input_value,
        make_node_result,
    )


def evaluate_logic_gate(node: NormalizedNode, context: RailContext):
    """Evaluate the P1 boolean logic-gate component."""

    specs = logic_gate_input_specs(node)
    values = [
        logic_input_value(spec, context.results[spec.target])
        for spec in specs
    ]
    gate = str(node.config.get("gate", "all"))
    matched = all(values) if gate == "all" else any(values)
    if bool(node.config.get("invert", False)):
        matched = not matched
    payload = {
        "inputs": {
            spec.raw or spec.target: value
            for spec, value in zip(specs, values, strict=False)
        }
    }
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "default")),
        metadata=payload,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


INPUT_DETECTOR_TEMPLATES = {
    "length_anomaly_detector",
    "role_marker_spoofing_detector",
    "instruction_override_detector",
}


def evaluate_input_detector(
    node: NormalizedNode, context: RailContext, text: str,
):
    """Evaluate one P1 local input detector without external I/O."""

    if node.template_key == "length_anomaly_detector":
        matched, payload = _evaluate_length_anomaly(node.config, text)
    elif node.template_key == "role_marker_spoofing_detector":
        matched, payload = _evaluate_role_marker_spoofing(node.config, text)
    elif node.template_key == "instruction_override_detector":
        matched, payload = _evaluate_instruction_override(node.config, text)
    else:
        raise ValueError(f"unsupported input detector {node.template_key}")
    payload["detector"] = node.template_key
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "default")),
        metadata=payload,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


def _evaluate_length_anomaly(config: dict, text: str) -> tuple[bool, dict]:
    raw_text = text or ""
    raw_length = len(raw_text)
    hard_max = int(config["hard_max_chars"])
    limit = int(config["scan_limit_chars"])
    scanned = raw_text[:limit]
    codes: list[str] = []
    if raw_length >= hard_max:
        codes.append("hard_length")

    fence_pairs = scanned.count("```") // 2
    if fence_pairs > int(config["max_code_fence_pairs"]):
        codes.append("many_code_fences")
    repeat_run = _longest_repeat_run(scanned)
    if repeat_run > int(config["max_repeat_run"]):
        codes.append("repeat_run")
    separator_run = _longest_separator_run(scanned)
    if separator_run > int(config["max_separator_run"]):
        codes.append("separator_run")
    duplicate_count, duplicate_ratio = _duplicate_line_stats(
        scanned,
        int(config["duplicate_line_min_chars"]),
    )
    if (
        duplicate_count >= int(config["duplicate_line_min_count"])
        and duplicate_ratio >= float(config["duplicate_line_ratio"])
    ):
        codes.append("duplicate_lines")
    invisible_count = sum(1 for char in scanned if unicodedata.category(char) == "Cf")
    invisible_ratio = invisible_count / max(1, len(scanned))
    if (
        invisible_count >= int(config["min_invisible_chars"])
        and invisible_ratio >= float(config["max_invisible_ratio"])
    ):
        codes.append("invisible_ratio")

    structural_count = len(codes) - (1 if "hard_length" in codes else 0)
    matched = "hard_length" in codes or structural_count >= int(config["min_structural_signals"])
    score = min(100, (70 if "hard_length" in codes else 0) + structural_count * 18)
    return matched, {
        "reason_codes": codes,
        "score": score,
        "raw_char_count": raw_length,
        "scanned_char_count": len(scanned),
        "scan_truncated": raw_length > len(scanned),
        "code_fence_pairs": fence_pairs,
        "max_repeat_run": repeat_run,
        "max_separator_run": separator_run,
        "duplicate_line_count": duplicate_count,
        "duplicate_line_ratio": round(duplicate_ratio, 4),
        "invisible_char_count": invisible_count,
        "invisible_ratio": round(invisible_ratio, 4),
    }


def _evaluate_role_marker_spoofing(config: dict, text: str) -> tuple[bool, dict]:
    scanned, truncated = _normalized_window(text, int(config["scan_limit_chars"]))
    lines = scanned.splitlines()[: int(config["max_lines"])]
    indicators: list[str] = []
    strong_structure_codes: list[str] = []
    role_headers = sum(1 for line in lines if _looks_like_role_header(line))
    if role_headers:
        indicators.append("role_header")
    compact = " ".join(lines)
    if config["detect_serialized_message_envelope"] and _looks_like_message_envelope(compact):
        indicators.append("message_envelope")
        if _is_complete_message_envelope(scanned):
            strong_structure_codes.append("complete_message_envelope")
    if config["detect_tool_invocation_envelope"] and _looks_like_tool_envelope(compact):
        indicators.append("tool_envelope")
        if _is_complete_tool_envelope(scanned):
            strong_structure_codes.append("complete_tool_envelope")
    if config["detect_reserved_delimiters"] and _has_reserved_delimiters(compact):
        indicators.append("reserved_delimiters")
        if _is_complete_chatml_envelope(scanned):
            strong_structure_codes.append("complete_chatml_envelope")
    if config["detect_log_like_headers"] and role_headers and _has_log_like_header(lines):
        indicators.append("log_like_header")
    matched = bool(strong_structure_codes) or len(indicators) >= int(config["min_indicators"])
    return matched, {
        "indicator_codes": indicators,
        "strong_structure_codes": strong_structure_codes,
        "score": max(
            90 if strong_structure_codes else 0,
            min(100, len(indicators) * 30 + min(role_headers, 2) * 5),
        ),
        "role_header_count": role_headers,
        "scanned_line_count": len(lines),
        "scan_truncated": truncated,
    }


def _evaluate_instruction_override(config: dict, text: str) -> tuple[bool, dict]:
    scanned, truncated = _normalized_window(text, int(config["scan_limit_chars"]))
    gap = int(config["max_token_gap"]) * 8
    categories = {
        "override_operation": _positions(scanned, ("ignore", "bypass", "discard", "disable", "forget", "忽略", "绕过", "废弃", "关闭", "忘记")),
        "protected_target": _positions(scanned, ("instruction", "rule", "prompt", "policy", "system", "指令", "规则", "提示词", "系统")),
        "reveal_operation": _positions(scanned, ("reveal", "show", "expose", "泄露", "展示", "公开")),
        "authority_claim": _positions(scanned, ("administrator", "admin", "highest authority", "管理员", "最高权限")),
        "role_reassignment": _positions(scanned, ("you are now", "become", "act as", "你现在是", "改为", "扮演")),
        "protected_reference": _positions(scanned, ("your", "previous", "prior", "above", "hidden", "internal", "private", "secret", "你的", "此前", "之前", "上文", "隐藏", "内部", "私密")),
        "override_scope": _positions(scanned, ("all", "every", "全部", "所有")),
    }
    evidence: list[str] = []
    protected_target_referenced = _near(
        categories["protected_target"], categories["protected_reference"], gap
    )
    operation_targets_protected_content = _near(
        categories["override_operation"], categories["protected_target"], gap
    )
    override_scope_is_explicit = _near(
        categories["override_operation"], categories["override_scope"], gap
    ) and _near(categories["override_scope"], categories["protected_target"], gap)
    override_intent = operation_targets_protected_content and (
        protected_target_referenced or override_scope_is_explicit
    )
    reveal_intent = _near(
        categories["reveal_operation"], categories["protected_target"], gap
    ) and protected_target_referenced
    if config["detect_instruction_replacement"] and override_intent:
        evidence.extend(("override_intent", "protected_reference"))
    if config["detect_hidden_content_request"] and reveal_intent:
        evidence.extend(("hidden_content_request", "protected_reference"))
    if config["detect_authority_claim"] and categories["authority_claim"] and (override_intent or reveal_intent):
        evidence.append("authority_claim")
    if config["detect_role_reassignment"] and categories["role_reassignment"] and override_intent:
        evidence.append("role_reassignment")
    unique_evidence = list(dict.fromkeys(evidence))
    matched = len(unique_evidence) >= int(config["min_evidence"])
    return matched, {
        "evidence_codes": unique_evidence,
        "score": min(100, len(unique_evidence) * 32),
        "language_supported": bool(scanned),
        "scan_truncated": truncated,
    }


def _normalized_window(text: str, limit: int) -> tuple[str, bool]:
    raw = text or ""
    truncated = len(raw) > limit
    normalized = unicodedata.normalize("NFKC", raw[:limit]).replace("\r\n", "\n").replace("\r", "\n")
    return normalized.casefold(), truncated


def _longest_repeat_run(text: str) -> int:
    longest = current = 0
    previous = ""
    for char in text:
        if char == previous and not char.isspace():
            current += 1
        else:
            current = 1
            previous = char
        longest = max(longest, current)
    return longest


def _longest_separator_run(text: str) -> int:
    longest = current = 0
    for char in text:
        if char in "-_~=*#|/\\":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _duplicate_line_stats(text: str, minimum_length: int) -> tuple[int, float]:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if len(line) >= minimum_length]
    if not lines:
        return 0, 0.0
    counts = Counter(lines)
    duplicate_count = max(counts.values())
    return duplicate_count, duplicate_count / len(lines)


def _looks_like_role_header(line: str) -> bool:
    stripped = line.strip().strip("[]<>{} ").casefold()
    name, separator, content = stripped.partition(":")
    name = name.strip().removesuffix(" message")
    return bool(separator and content.strip() and name in {"system", "developer", "assistant", "tool", "function", "系统", "开发者", "助手", "工具"})


def _looks_like_message_envelope(text: str) -> bool:
    return all(token in text for token in ('"role"', '"content"')) and any(
        token in text for token in ('"system"', '"developer"', '"assistant"', '"tool"')
    )


def _looks_like_tool_envelope(text: str) -> bool:
    return any(token in text for token in ("function_call", "tool_call", "tool_use")) and any(
        token in text for token in ("arguments", "parameters", "name")
    )


def _is_complete_message_envelope(text: str) -> bool:
    parsed = _parse_json_object(text)
    if not isinstance(parsed, dict):
        return False
    role = parsed.get("role")
    content = parsed.get("content")
    return isinstance(role, str) and role.casefold() in {"system", "developer"} and isinstance(content, str) and bool(content.strip())


def _is_complete_tool_envelope(text: str) -> bool:
    parsed = _parse_json_object(text)
    if not isinstance(parsed, dict):
        return False
    call = parsed.get("function_call")
    return isinstance(call, dict) and isinstance(call.get("name"), str) and bool(call["name"].strip()) and "arguments" in call


def _is_complete_chatml_envelope(text: str) -> bool:
    prefix = "<|im_start|>"
    if not text.startswith(prefix):
        return False
    remainder = text[len(prefix):].lstrip()
    role, separator, content = remainder.partition("\n")
    return bool(
        separator
        and role.strip() in {"system", "developer", "tool"}
        and content.strip()
    )


def _parse_json_object(text: str):
    try:
        return json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _has_reserved_delimiters(text: str) -> bool:
    return ("<|" in text and "|>" in text) or ("<<" in text and ">>" in text)


def _has_log_like_header(lines: list[str]) -> bool:
    return any(re.match(r"^\s*\[[^\]]{1,32}\]\s*", line) for line in lines)


def _positions(text: str, terms: tuple[str, ...]) -> list[int]:
    return [position for term in terms for position in _all_positions(text, term)]


def _all_positions(text: str, term: str) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = text.find(term, start)
        if position < 0:
            return positions
        positions.append(position)
        start = position + len(term)


def _near(left: list[int], right: list[int], max_gap: int) -> bool:
    return any(abs(first - second) <= max_gap for first in left for second in right)
