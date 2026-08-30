"""Evaluators for policy-local electronic components."""

from __future__ import annotations

import base64
import binascii
from collections import Counter
import json
import re
import unicodedata

try:
    from .adapters import MessageFactSnapshot
    from .config import NormalizedNode
    from .core import (
        NodeSignal,
        RailContext,
        logic_gate_input_specs,
        logic_input_value,
        logic_gate_payload_value,
        make_node_result,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from adapters import MessageFactSnapshot
    from config import NormalizedNode
    from core import (
        NodeSignal,
        RailContext,
        logic_gate_input_specs,
        logic_input_value,
        logic_gate_payload_value,
        make_node_result,
    )


def evaluate_logic_gate(node: NormalizedNode, context: RailContext):
    """Evaluate a boolean gate and its restricted, ordered payload outputs."""

    specs = logic_gate_input_specs(node)
    input_states: dict[str, bool] = {}
    payload_values: list[tuple[str, object]] = []
    values: list[bool] = []
    for spec in specs:
        result = context.results[spec.target]
        is_satisfied = logic_input_value(spec, result)
        values.append(is_satisfied)
        input_states[spec.raw or spec.target] = is_satisfied
        if not is_satisfied or not spec.payload_path:
            continue
        value = logic_gate_payload_value(spec, result)
        if value is not None:
            payload_values.append((spec.target, value))
    gate = str(node.config.get("gate", "all"))
    matched = all(values) if gate == "all" else any(values)
    if bool(node.config.get("invert", False)):
        matched = not matched
    payload: dict[str, object] = {}
    if matched:
        payload["first_value"] = payload_values[0][1] if payload_values else None
        payload["joined_string"] = _join_logic_gate_payload_values(node, payload_values)
    metadata = {"inputs": input_states}
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "default")),
        metadata=metadata,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


def _join_logic_gate_payload_values(
    node: NormalizedNode, payload_values: list[tuple[str, object]],
) -> str:
    if not payload_values:
        return ""
    item_template = str(node.config.get("value_item_template", "${value}"))
    separator = str(node.config.get("value_separator", "\n"))
    return separator.join(
        item_template
        .replace("${value}", _logic_gate_value_to_text(value))
        .replace("${source}", source)
        for source, value in payload_values
    )


def _logic_gate_value_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


INPUT_DETECTOR_TEMPLATES = {
    "encoded_payload_detector",
    "length_anomaly_detector",
    "role_marker_spoofing_detector",
    "external_fetch_detector",
    "instruction_override_detector",
}

_BASE64_CANDIDATE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+/_-])([A-Za-z0-9+/_-]{16,}={0,2})(?![A-Za-z0-9+/_=-])"
)
_PERCENT_ESCAPE_PATTERN = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
_UNICODE_ESCAPE_PATTERN = re.compile(r"(?:\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8})+")
_HEX_BYTE_PATTERN = re.compile(
    r"(?<![0-9A-Fa-f])(?:0x)?[0-9A-Fa-f]{2}(?:[\s,:-]+[0-9A-Fa-f]{2})+(?![0-9A-Fa-f])"
)
_ROT13_WRAPPER_PATTERN = re.compile(
    r"\brot13\s*:\s*([A-Za-z]{8,})\b|\brot13\s*\(\s*([A-Za-z]{8,})\s*\)",
    re.IGNORECASE,
)
_HTTP_RESOURCE_PATTERN = re.compile(
    r"(?i)(?:(?:https?:)?//[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::\d{1,5})?(?:/[^\s<>()\[\]\"']*)?)"
)
_MARKDOWN_IMAGE_PREFIX_PATTERN = re.compile(r"!\[[^\]\r\n]{0,120}\]\(\s*$")
_COMMAND_FETCH_PATTERN = re.compile(
    r"(?im)^\s*(?:curl|wget|invoke-webrequest|iwr)\b[^\r\n]*?(?:(?:https?:)?//)"
)
_COMMAND_EXECUTION_TAIL_PATTERN = re.compile(
    r"(?i)(?:\||&&)\s*(?:sh|bash|zsh|python3?|pwsh|powershell|iex)\b"
)
_FETCH_ACTION_TERMS = (
    "fetch", "retrieve", "download", "load", "read", "open", "import",
    "获取", "抓取", "下载", "读取", "加载", "打开", "导入",
)
_TRANSFER_ACTION_TERMS = (
    "send", "upload", "post", "forward", "exfiltrate",
    "发送", "上传", "转发", "外传",
)
_PROMPT_TARGET_TERMS = (
    "prompt", "instruction", "system prompt", "提示词", "指令", "系统提示",
)

MESSAGE_FACT_TEMPLATES = {
    "contains_request_user_id",
    "contains_forward",
    "contains_file",
    "contains_image",
    "contains_record",
    "contains_video",
}

MESSAGE_FACT_COMPONENT_TEMPLATES = (
    MESSAGE_FACT_TEMPLATES - {"contains_request_user_id"}
)

_MESSAGE_KIND_BY_TEMPLATE = {
    "contains_forward": "forward",
    "contains_file": "file",
    "contains_image": "image",
    "contains_record": "record",
    "contains_video": "video",
}


def evaluate_input_detector(
    node: NormalizedNode, context: RailContext, text: str,
):
    """Evaluate one local input detector without external I/O."""

    if node.template_key == "encoded_payload_detector":
        matched, payload = _evaluate_encoded_payload(node.config, text)
    elif node.template_key == "length_anomaly_detector":
        matched, payload = _evaluate_length_anomaly(node.config, text)
    elif node.template_key == "role_marker_spoofing_detector":
        matched, payload = _evaluate_role_marker_spoofing(node.config, text)
    elif node.template_key == "external_fetch_detector":
        matched, payload = _evaluate_external_fetch(node.config, text)
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


def evaluate_message_fact_component(
    node: NormalizedNode, snapshot: MessageFactSnapshot,
):
    """Evaluate one P2 message fact template from an adapter snapshot only."""

    payload: dict[str, object] = {
        "component": node.template_key,
        "message_chain_available": snapshot.message_chain_available,
        "outline_available": snapshot.outline_available,
    }
    if node.template_key == "contains_request_user_id":
        configured = {str(value).strip() for value in node.config.get("user_ids", [])}
        request_id = snapshot.request_user_id
        matched = bool(request_id and request_id in configured)
        payload.update(
            {
                "configured_user_count": len(configured),
                "matched_user_ids": [_redact_identifier(request_id)] if matched else [],
                "component_count": 0,
                "component_indices": [],
            }
        )
    else:
        message_kind = _MESSAGE_KIND_BY_TEMPLATE.get(node.template_key)
        if not message_kind:
            raise ValueError(f"unsupported message fact component {node.template_key}")
        matches = [
            component
            for component in snapshot.components
            if component.kind == message_kind
            or (
                message_kind == "video"
                and component.kind == "file"
                and component.media_category == "video"
            )
        ]
        matched = bool(matches)
        payload.update(
            {
                "message_kind": message_kind,
                "component_count": len(matches),
                "component_indices": [component.index for component in matches],
            }
        )
    payload["score"] = 100 if matched else 0
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "observe")),
        metadata=payload,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


def _redact_identifier(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return f"***{normalized[-4:]}" if len(normalized) > 4 else "***"


def _evaluate_encoded_payload(config: dict, text: str) -> tuple[bool, dict]:
    scanned, truncated = _normalized_window(
        text, int(config["scan_limit_chars"]), casefold=False,
    )
    candidates: list[tuple[str, int, int]] = []
    decode_limited = False
    candidate_limit = int(config["max_candidate_segments"])

    def add_candidate(code: str, start: int, end: int) -> None:
        if len(candidates) < candidate_limit:
            candidates.append((code, start, end))

    if config["detect_base64"]:
        for match in _BASE64_CANDIDATE_PATTERN.finditer(scanned):
            candidate = match.group(1)
            if len(candidate) < int(config["min_base64_chars"]):
                continue
            if len(set(candidate.rstrip("="))) < int(config["min_base64_distinct_chars"]):
                continue
            if not any(char in candidate for char in "+/=_-"):
                continue
            valid, limited = _validate_base64_candidate(
                candidate, int(config["max_decode_bytes"]),
            )
            decode_limited = decode_limited or limited
            if valid:
                add_candidate("base64", match.start(1), match.end(1))

    if config["detect_percent_encoding"]:
        for match in _PERCENT_ESCAPE_PATTERN.finditer(scanned):
            if match.group(0).count("%") >= int(config["min_percent_escape_count"]):
                add_candidate("percent_escape", match.start(), match.end())

    if config["detect_unicode_escape"]:
        for match in _UNICODE_ESCAPE_PATTERN.finditer(scanned):
            escape_count = len(
                re.findall(r"\\u[0-9A-Fa-f]{4}|\\U[0-9A-Fa-f]{8}", match.group(0))
            )
            if escape_count >= int(config["min_unicode_escape_count"]):
                add_candidate("unicode_escape", match.start(), match.end())

    if config["detect_hex"]:
        for match in _HEX_BYTE_PATTERN.finditer(scanned):
            byte_count = len(re.findall(r"[0-9A-Fa-f]{2}", match.group(0)))
            if byte_count >= int(config["min_hex_bytes"]):
                add_candidate("hex_bytes", match.start(), match.end())

    if config["detect_rot13_wrapper"]:
        for match in _ROT13_WRAPPER_PATTERN.finditer(scanned):
            start, end = match.span(1 if match.group(1) is not None else 2)
            if end - start >= int(config["min_rot13_chars"]):
                add_candidate("rot13_wrapper", start, end)

    zero_width_count = 0
    if config["detect_zero_width"]:
        zero_width_count = sum(
            1 for char in scanned if unicodedata.category(char) == "Cf"
        )
    zero_width_ratio = zero_width_count / max(1, len(scanned))
    zero_width_match = (
        zero_width_count >= int(config["min_zero_width_chars"])
        and zero_width_ratio >= float(config["min_zero_width_ratio"])
    )

    encoding_codes = list(dict.fromkeys(code for code, _start, _end in candidates))
    if zero_width_match:
        encoding_codes.append("zero_width")
    encoded_chars = _merged_range_length(
        [(start, end) for _code, start, end in candidates]
    ) + zero_width_count
    encoded_ratio = min(1.0, encoded_chars / max(1, len(scanned)))
    strongest_candidate = max(
        (end - start for _code, start, end in candidates), default=0,
    )
    strong_candidate = any(
        (end - start) >= _encoded_strong_length(code, config)
        and (end - start) / max(1, len(scanned)) >= float(config["min_encoded_ratio"])
        for code, start, end in candidates
    )
    strong_match = zero_width_match or strong_candidate
    matched = strong_match or len(encoding_codes) >= int(config["min_signal_families"])
    base_score = min(
        79,
        len(encoding_codes) * 24 + round(encoded_ratio * 30),
    ) if encoding_codes else 0
    score = max(80 if strong_match else 0, base_score)
    return matched, {
        "encoding_codes": encoding_codes,
        "score": min(100, score),
        "candidate_segment_count": len(candidates),
        "max_candidate_chars": strongest_candidate,
        "encoded_ratio": round(encoded_ratio, 4),
        "zero_width_count": zero_width_count,
        "zero_width_ratio": round(zero_width_ratio, 4),
        "scan_truncated": truncated,
        "decode_limited": decode_limited,
    }


def _validate_base64_candidate(value: str, max_decode_bytes: int) -> tuple[bool, bool]:
    unpadded = value.rstrip("=")
    if not unpadded or "=" in unpadded or len(unpadded) % 4 == 1:
        return False, False
    estimated_size = (len(unpadded) * 3) // 4
    if estimated_size > max_decode_bytes:
        return True, True
    padded = unpadded + "=" * (-len(unpadded) % 4)
    try:
        base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        return False, False
    return True, False


def _encoded_strong_length(code: str, config: dict) -> int:
    minimums = {
        "base64": int(config["min_base64_chars"]),
        "percent_escape": int(config["min_percent_escape_count"]) * 3,
        "unicode_escape": int(config["min_unicode_escape_count"]) * 6,
        "hex_bytes": int(config["min_hex_bytes"]) * 3,
        "rot13_wrapper": int(config["min_rot13_chars"]),
    }
    return minimums.get(code, 1000000) * 2


def _merged_range_length(ranges: list[tuple[int, int]]) -> int:
    total = 0
    latest_end = -1
    for start, end in sorted(ranges):
        if end <= latest_end:
            continue
        total += end - max(start, latest_end)
        latest_end = end
    return total


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


def _evaluate_external_fetch(config: dict, text: str) -> tuple[bool, dict]:
    scanned, truncated = _normalized_window(
        text, int(config["scan_limit_chars"]), casefold=False,
    )
    resources, resource_scan_limited = _external_resources(
        scanned,
        int(config["max_resources"]),
        detect_http_resources=bool(config["detect_http_resources"]),
        detect_markdown_remote_image=bool(config["detect_markdown_remote_image"]),
    )
    action_gap = int(config["max_action_gap_chars"])
    fetch_positions = _semantic_term_positions(scanned, _FETCH_ACTION_TERMS)
    transfer_positions = _semantic_term_positions(scanned, _TRANSFER_ACTION_TERMS)
    prompt_positions = _semantic_term_positions(scanned, _PROMPT_TARGET_TERMS)
    fetch_pairs = _resource_action_pair_count(resources, fetch_positions, action_gap)
    transfer_pairs = (
        _resource_action_pair_count(resources, transfer_positions, action_gap)
        if config["detect_external_transfer"] else 0
    )
    prompt_import_pairs = (
        _prompt_import_pair_count(
            resources, fetch_positions, prompt_positions, action_gap,
        )
        if config["detect_prompt_import"] else 0
    )
    command_fetch_execute_count = (
        _command_fetch_execute_count(scanned)
        if config["detect_command_fetch"] else 0
    )
    remote_image_count = sum(1 for _start, _end, is_image in resources if is_image)
    evidence_codes: list[str] = []
    if resources:
        evidence_codes.append("http_resource")
    if remote_image_count:
        evidence_codes.append("markdown_remote_image")
    if fetch_pairs:
        evidence_codes.append("fetch_intent")
    if prompt_import_pairs:
        evidence_codes.append("prompt_import")
    if transfer_pairs:
        evidence_codes.append("external_transfer")
    if command_fetch_execute_count:
        evidence_codes.append("command_fetch_execute")

    relationship_count = (
        int(bool(resources))
        + int(bool(fetch_pairs))
        + int(bool(prompt_import_pairs))
        + int(bool(transfer_pairs))
    )
    matched = command_fetch_execute_count > 0 or (
        bool(resources)
        and relationship_count >= int(config["min_evidence"])
        and (fetch_pairs > 0 or prompt_import_pairs > 0 or transfer_pairs > 0)
    )
    ordinary_score = min(
        79,
        int(bool(resources)) * 15
        + int(bool(fetch_pairs)) * 25
        + int(bool(prompt_import_pairs)) * 18
        + int(bool(transfer_pairs)) * 20
        + min(16, (fetch_pairs + prompt_import_pairs + transfer_pairs) * 4),
    )
    score = max(85 if command_fetch_execute_count else 0, ordinary_score)
    return matched, {
        "evidence_codes": evidence_codes,
        "score": min(100, score),
        "resource_count": len(resources),
        "remote_image_count": remote_image_count,
        "command_fetch_execute_count": command_fetch_execute_count,
        "nearby_action_pair_count": fetch_pairs + prompt_import_pairs + transfer_pairs,
        "scan_truncated": truncated,
        "resource_scan_limited": resource_scan_limited,
    }


def _external_resources(
    text: str,
    maximum: int,
    *,
    detect_http_resources: bool,
    detect_markdown_remote_image: bool,
) -> tuple[list[tuple[int, int, bool]], bool]:
    resources: list[tuple[int, int, bool]] = []
    limited = False
    for match in _HTTP_RESOURCE_PATTERN.finditer(text):
        start, end = match.span()
        while end > start and text[end - 1] in ".,;:!?":
            end -= 1
        is_markdown_image = bool(
            _MARKDOWN_IMAGE_PREFIX_PATTERN.search(text[max(0, start - 256):start])
        )
        if not detect_http_resources and not (
            detect_markdown_remote_image and is_markdown_image
        ):
            continue
        if len(resources) >= maximum:
            limited = True
            break
        resources.append((start, end, is_markdown_image))
    return resources, limited


def _semantic_term_positions(text: str, terms: tuple[str, ...]) -> list[int]:
    positions: list[int] = []
    for term in terms:
        if term.isascii():
            pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", re.IGNORECASE)
            positions.extend(match.start() for match in pattern.finditer(text))
        else:
            positions.extend(_all_positions(text, term))
    return positions


def _resource_action_pair_count(
    resources: list[tuple[int, int, bool]], action_positions: list[int], gap: int,
) -> int:
    return sum(
        1
        for start, end, _is_image in resources
        if any(_position_near_range(position, start, end, gap) for position in action_positions)
    )


def _prompt_import_pair_count(
    resources: list[tuple[int, int, bool]],
    fetch_positions: list[int],
    prompt_positions: list[int],
    gap: int,
) -> int:
    return sum(
        1
        for start, end, _is_image in resources
        if any(_position_near_range(position, start, end, gap) for position in fetch_positions)
        and any(_position_near_range(position, start, end, gap) for position in prompt_positions)
    )


def _position_near_range(position: int, start: int, end: int, gap: int) -> bool:
    return start - gap <= position <= end + gap


def _command_fetch_execute_count(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if _COMMAND_FETCH_PATTERN.search(line)
        and _COMMAND_EXECUTION_TAIL_PATTERN.search(line)
    )


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


def _normalized_window(
    text: str, limit: int, *, casefold: bool = True,
) -> tuple[str, bool]:
    raw = text or ""
    truncated = len(raw) > limit
    normalized = unicodedata.normalize("NFKC", raw[:limit]).replace("\r\n", "\n").replace("\r", "\n")
    return normalized.casefold() if casefold else normalized, truncated


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
