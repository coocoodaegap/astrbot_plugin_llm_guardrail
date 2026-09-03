"""Evaluators for policy-local electronic components."""

from __future__ import annotations

import base64
import binascii
from collections import Counter
import json
import random
import re
import unicodedata

try:
    from .adapters import MessageFactSnapshot
    from .config import NormalizedNode
    from .constants import INTERNAL_MARKER
    from .core_materials import CORE_MATERIALS, material_terms, material_values
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
    from constants import INTERNAL_MARKER
    from core_materials import CORE_MATERIALS, material_terms, material_values
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

OUTPUT_DETECTOR_TEMPLATES = {
    "poor_quality_detector",
    "metadata_leakage_detector",
    "refusal_leakage_detector",
}

_MARKDOWN_IMAGE_PREFIX_PATTERN = re.compile(r"!\[[^\]\r\n]{0,120}\]\(\s*$")

# These slots preserve the current instruction-override boundary.  They live
# in the versioned, code-owned material set so later refinements have a small,
# auditable source of truth rather than another implicit detector wordlist.
_INSTRUCTION_INTENT_MATERIAL_IDS = {
    "override_operation": "intent_override_operation",
    "protected_target": "intent_protected_target",
    "reveal_operation": "intent_reveal_operation",
    "authority_claim": "intent_authority_claim",
    "role_reassignment": "intent_role_reassignment",
    "protected_reference": "intent_protected_reference",
    "override_scope": "intent_override_scope",
}
_INSTRUCTION_INTENT_TERMS = {
    category: material_terms(CORE_MATERIALS, material_id)
    for category, material_id in _INSTRUCTION_INTENT_MATERIAL_IDS.items()
}

_ROLE_HEADER_ROLE_NAMES = material_values(
    CORE_MATERIALS, "protocol_role_header", "role_names",
)
_ROLE_HEADER_OPTIONAL_SUFFIXES = material_values(
    CORE_MATERIALS, "protocol_role_header", "optional_suffixes",
)
_MESSAGE_ENVELOPE_ROLE_FIELDS = material_values(
    CORE_MATERIALS, "protocol_message_envelope", "role_fields",
)
_MESSAGE_ENVELOPE_CONTENT_FIELDS = material_values(
    CORE_MATERIALS, "protocol_message_envelope", "content_fields",
)
_MESSAGE_ENVELOPE_WEAK_ROLE_VALUES = material_values(
    CORE_MATERIALS, "protocol_message_envelope", "weak_role_values",
)
_MESSAGE_ENVELOPE_STRONG_ROLE_VALUES = material_values(
    CORE_MATERIALS, "protocol_message_envelope", "strong_role_values",
)
_TOOL_ENVELOPE_CALL_FIELDS = material_values(
    CORE_MATERIALS, "protocol_tool_envelope", "call_fields",
)
_TOOL_ENVELOPE_WEAK_ARGUMENT_FIELDS = material_values(
    CORE_MATERIALS, "protocol_tool_envelope", "weak_argument_fields",
)
_TOOL_ENVELOPE_STRONG_CALL_FIELDS = material_values(
    CORE_MATERIALS, "protocol_tool_envelope", "strong_call_fields",
)
_TOOL_ENVELOPE_STRONG_NONEMPTY_STRING_FIELDS = material_values(
    CORE_MATERIALS, "protocol_tool_envelope", "strong_nonempty_string_fields",
)
_TOOL_ENVELOPE_STRONG_PRESENCE_FIELDS = material_values(
    CORE_MATERIALS, "protocol_tool_envelope", "strong_presence_fields",
)
_CHATML_START_DELIMITERS = material_values(
    CORE_MATERIALS, "protocol_chatml_envelope", "start_delimiters",
)
_CHATML_STRONG_ROLE_VALUES = material_values(
    CORE_MATERIALS, "protocol_chatml_envelope", "strong_role_values",
)
_RESERVED_DELIMITER_OPENS = material_values(
    CORE_MATERIALS, "protocol_chatml_envelope", "open_delimiters",
)
_RESERVED_DELIMITER_CLOSES = material_values(
    CORE_MATERIALS, "protocol_chatml_envelope", "close_delimiters",
)
_FETCH_ACTION_TERMS = material_terms(CORE_MATERIALS, "operation_external_fetch")
_TRANSFER_ACTION_TERMS = material_terms(
    CORE_MATERIALS, "operation_external_transfer",
)
_PROMPT_TARGET_TERMS = material_terms(
    CORE_MATERIALS, "operation_external_prompt_target",
)
_HTTP_RESOURCE_SCHEMES = material_values(
    CORE_MATERIALS, "operation_http_fetch_execute", "schemes",
)
_FETCH_COMMANDS = material_values(
    CORE_MATERIALS, "operation_http_fetch_execute", "fetch_commands",
)
_FETCH_EXECUTE_INTERPRETERS = material_values(
    CORE_MATERIALS, "operation_http_fetch_execute", "interpreters",
)
_HTTP_SCHEME_ALTERNATION = "|".join(
    re.escape(scheme) for scheme in _HTTP_RESOURCE_SCHEMES
)
_FETCH_COMMAND_ALTERNATION = "|".join(
    re.escape(command) for command in _FETCH_COMMANDS
)
_FETCH_EXECUTE_INTERPRETER_ALTERNATION = "|".join(
    re.escape(interpreter) for interpreter in _FETCH_EXECUTE_INTERPRETERS
)
_HTTP_RESOURCE_PATTERN = re.compile(
    rf"(?i)(?:(?:(?:{_HTTP_SCHEME_ALTERNATION}):)?//[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::\d{{1,5}})?(?:/[^\s<>()\[\]\"']*)?)"
)
_COMMAND_FETCH_PATTERN = re.compile(
    rf"(?im)^\s*(?:{_FETCH_COMMAND_ALTERNATION})\b[^\r\n]*?(?:(?:(?:{_HTTP_SCHEME_ALTERNATION}):)?//)"
)
_COMMAND_EXECUTION_TAIL_PATTERN = re.compile(
    rf"(?i)(?:\||&&)\s*(?:{_FETCH_EXECUTE_INTERPRETER_ALTERNATION})\b"
)
_BASE64_ALPHABET_EXTRAS = material_values(
    CORE_MATERIALS, "encoding_base64_candidate", "alphabet_extras",
)
_BASE64_PADDING_CHARS = material_values(
    CORE_MATERIALS, "encoding_base64_candidate", "padding_chars",
)
_BASE64_ALTCHARS = "".join(material_values(
    CORE_MATERIALS, "encoding_base64_candidate", "decoder_altchars",
)).encode("ascii")
_BASE64_BODY_CHAR_CLASS = "A-Za-z0-9" + "".join(
    re.escape(value) for value in _BASE64_ALPHABET_EXTRAS
)
_BASE64_PADDING_CHAR_CLASS = "".join(
    re.escape(value) for value in _BASE64_PADDING_CHARS
)
_BASE64_DISTINCTIVE_CHARS = _BASE64_ALPHABET_EXTRAS + _BASE64_PADDING_CHARS
_BASE64_PADDING_CHAR = _BASE64_PADDING_CHARS[0]
_BASE64_CANDIDATE_PATTERN = re.compile(
    rf"(?<![{_BASE64_BODY_CHAR_CLASS}])([{_BASE64_BODY_CHAR_CLASS}]{{16,}}[{_BASE64_PADDING_CHAR_CLASS}]{{0,2}})(?![{_BASE64_BODY_CHAR_CLASS}{_BASE64_PADDING_CHAR_CLASS}])"
)
_PERCENT_ESCAPE_PREFIX = material_values(
    CORE_MATERIALS, "encoding_percent_escape", "prefixes",
)[0]
_PERCENT_ESCAPE_HEX_WIDTH = int(material_values(
    CORE_MATERIALS, "encoding_percent_escape", "hex_widths",
)[0])
_PERCENT_ESCAPE_UNIT_PATTERN = (
    rf"{re.escape(_PERCENT_ESCAPE_PREFIX)}[0-9A-Fa-f]{{{_PERCENT_ESCAPE_HEX_WIDTH}}}"
)
_PERCENT_ESCAPE_PATTERN = re.compile(rf"(?:{_PERCENT_ESCAPE_UNIT_PATTERN})+")
_UNICODE_ESCAPE_SHORT_PREFIX = material_values(
    CORE_MATERIALS, "encoding_unicode_escape", "short_prefixes",
)[0]
_UNICODE_ESCAPE_SHORT_HEX_WIDTH = int(material_values(
    CORE_MATERIALS, "encoding_unicode_escape", "short_hex_widths",
)[0])
_UNICODE_ESCAPE_LONG_PREFIX = material_values(
    CORE_MATERIALS, "encoding_unicode_escape", "long_prefixes",
)[0]
_UNICODE_ESCAPE_LONG_HEX_WIDTH = int(material_values(
    CORE_MATERIALS, "encoding_unicode_escape", "long_hex_widths",
)[0])
_UNICODE_ESCAPE_UNIT_PATTERN = re.compile(
    rf"{re.escape(_UNICODE_ESCAPE_SHORT_PREFIX)}[0-9A-Fa-f]{{{_UNICODE_ESCAPE_SHORT_HEX_WIDTH}}}|{re.escape(_UNICODE_ESCAPE_LONG_PREFIX)}[0-9A-Fa-f]{{{_UNICODE_ESCAPE_LONG_HEX_WIDTH}}}"
)
_UNICODE_ESCAPE_PATTERN = re.compile(
    rf"(?:{_UNICODE_ESCAPE_UNIT_PATTERN.pattern})+"
)
_HEX_BYTE_OPTIONAL_PREFIXES = material_values(
    CORE_MATERIALS, "encoding_hex_bytes", "optional_prefixes",
)
_HEX_BYTE_WIDTH = int(material_values(
    CORE_MATERIALS, "encoding_hex_bytes", "byte_hex_widths",
)[0])
_HEX_BYTE_SEPARATOR_TOKENS = material_values(
    CORE_MATERIALS, "encoding_hex_bytes", "separators",
)
_HEX_BYTE_PREFIX_ALTERNATION = "|".join(
    re.escape(prefix) for prefix in _HEX_BYTE_OPTIONAL_PREFIXES
)
_HEX_BYTE_SEPARATOR_CLASS = "".join(
    r"\s" if token == "whitespace" else re.escape(token)
    for token in _HEX_BYTE_SEPARATOR_TOKENS
)
_HEX_BYTE_PATTERN = re.compile(
    rf"(?<![0-9A-Fa-f])(?:{_HEX_BYTE_PREFIX_ALTERNATION})?[0-9A-Fa-f]{{{_HEX_BYTE_WIDTH}}}(?:[{_HEX_BYTE_SEPARATOR_CLASS}]+[0-9A-Fa-f]{{{_HEX_BYTE_WIDTH}}})+(?![0-9A-Fa-f])"
)
_ROT13_LABELS = material_values(
    CORE_MATERIALS, "encoding_rot13_wrapper", "labels",
)
_ROT13_COLON_WRAPPERS = material_values(
    CORE_MATERIALS, "encoding_rot13_wrapper", "colon_wrappers",
)
_ROT13_OPEN_WRAPPERS = material_values(
    CORE_MATERIALS, "encoding_rot13_wrapper", "open_wrappers",
)
_ROT13_CLOSE_WRAPPERS = material_values(
    CORE_MATERIALS, "encoding_rot13_wrapper", "close_wrappers",
)
_ROT13_LABEL_ALTERNATION = "|".join(re.escape(label) for label in _ROT13_LABELS)
_ROT13_COLON_ALTERNATION = "|".join(
    re.escape(wrapper) for wrapper in _ROT13_COLON_WRAPPERS
)
_ROT13_OPEN_ALTERNATION = "|".join(
    re.escape(wrapper) for wrapper in _ROT13_OPEN_WRAPPERS
)
_ROT13_CLOSE_ALTERNATION = "|".join(
    re.escape(wrapper) for wrapper in _ROT13_CLOSE_WRAPPERS
)
_ROT13_WRAPPER_PATTERN = re.compile(
    rf"\b(?:{_ROT13_LABEL_ALTERNATION})\s*(?:{_ROT13_COLON_ALTERNATION})\s*([A-Za-z]{{8,}})\b|\b(?:{_ROT13_LABEL_ALTERNATION})\s*(?:{_ROT13_OPEN_ALTERNATION})\s*([A-Za-z]{{8,}})\s*(?:{_ROT13_CLOSE_ALTERNATION})",
    re.IGNORECASE,
)
_ZERO_WIDTH_UNICODE_CATEGORIES = material_values(
    CORE_MATERIALS, "encoding_unicode_format_controls", "unicode_categories",
)
_PYTHON_TRACEBACK_HEADERS = material_values(
    CORE_MATERIALS, "runtime_python_traceback", "headers",
)
_PYTHON_TRACEBACK_HEADER_PREFIXES = tuple(
    prefix.casefold()
    for prefix in material_values(
        CORE_MATERIALS, "runtime_python_traceback", "header_prefixes",
    )
)
_PYTHON_TRACEBACK_FRAME_LABELS = material_values(
    CORE_MATERIALS, "runtime_python_traceback", "frame_labels",
)
_PYTHON_TRACEBACK_EXCEPTION_SUFFIXES = material_values(
    CORE_MATERIALS, "runtime_python_traceback", "exception_suffixes",
)
_PYTHON_TRACEBACK_EXCEPTION_NAMES = material_values(
    CORE_MATERIALS, "runtime_python_traceback", "exception_names",
)
_PYTHON_TRACEBACK_FRAME_LABEL_ALTERNATION = "|".join(
    re.escape(label) for label in _PYTHON_TRACEBACK_FRAME_LABELS
)
_PYTHON_TRACEBACK_EXCEPTION_SUFFIX_ALTERNATION = "|".join(
    re.escape(suffix) for suffix in _PYTHON_TRACEBACK_EXCEPTION_SUFFIXES
)
_PYTHON_TRACEBACK_EXCEPTION_NAME_ALTERNATION = "|".join(
    re.escape(name) for name in _PYTHON_TRACEBACK_EXCEPTION_NAMES
)
_PYTHON_TRACEBACK_FRAME_PATTERN = re.compile(
    rf'^(?:{_PYTHON_TRACEBACK_FRAME_LABEL_ALTERNATION}) "[^"\\n]{{1,512}}", '
    r"line \d+(?:, in .+)?$"
)
_PYTHON_EXCEPTION_LINE_PATTERN = re.compile(
    rf"^(?:[A-Za-z_]\w*\.)*(?:[A-Za-z_]\w*"
    rf"(?:{_PYTHON_TRACEBACK_EXCEPTION_SUFFIX_ALTERNATION})|"
    rf"{_PYTHON_TRACEBACK_EXCEPTION_NAME_ALTERNATION})(?::.*)?$"
)
_RUNTIME_TOOL_METHOD_FIELDS = material_values(
    CORE_MATERIALS, "runtime_tool_call_envelope", "method_fields",
)
_RUNTIME_TOOL_PARAMETER_FIELDS = material_values(
    CORE_MATERIALS, "runtime_tool_call_envelope", "parameter_fields",
)
_RUNTIME_TOOL_NAME_FIELDS = material_values(
    CORE_MATERIALS, "runtime_tool_call_envelope", "name_fields",
)
_RUNTIME_TOOL_ARGUMENT_FIELDS = material_values(
    CORE_MATERIALS, "runtime_tool_call_envelope", "argument_fields",
)
_RUNTIME_TOOL_FUNCTION_FIELDS = material_values(
    CORE_MATERIALS, "runtime_tool_call_envelope", "function_fields",
)
_RUNTIME_TOOL_CALLS_FIELDS = material_values(
    CORE_MATERIALS, "runtime_tool_call_envelope", "tool_calls_fields",
)
_RUNTIME_ERROR_OBJECT_FIELDS = frozenset(
    field.casefold()
    for field in material_values(
        CORE_MATERIALS, "runtime_error_envelope", "object_error_fields",
    )
)
_RUNTIME_ERROR_OBJECT_STRUCTURE_FIELDS = frozenset(
    field.casefold()
    for field in material_values(
        CORE_MATERIALS, "runtime_error_envelope", "object_structure_fields",
    )
)
_RUNTIME_ERROR_HEADER_LABELS = material_values(
    CORE_MATERIALS, "runtime_error_envelope", "header_labels",
)
_RUNTIME_ERROR_STATUS_HUNDREDS = material_values(
    CORE_MATERIALS, "runtime_error_envelope", "http_error_hundreds",
)
_RUNTIME_ERROR_EXCEPTION_SUFFIXES = material_values(
    CORE_MATERIALS, "runtime_error_envelope", "exception_suffixes",
)
_RUNTIME_ERROR_HEADER_ALTERNATION = "|".join(
    re.escape(label) for label in _RUNTIME_ERROR_HEADER_LABELS
)
_RUNTIME_ERROR_STATUS_HUNDREDS_CLASS = "".join(
    re.escape(value) for value in _RUNTIME_ERROR_STATUS_HUNDREDS
)
_RUNTIME_ERROR_EXCEPTION_SUFFIX_ALTERNATION = "|".join(
    re.escape(suffix) for suffix in _RUNTIME_ERROR_EXCEPTION_SUFFIXES
)
_RUNTIME_ERROR_HEADER_PATTERN = re.compile(
    rf"^(?:{_RUNTIME_ERROR_HEADER_ALTERNATION})\s*[:\[]", re.IGNORECASE,
)
_RUNTIME_ERROR_STATUS_PATTERN = re.compile(
    rf"\b(?:HTTP\s*)?[{_RUNTIME_ERROR_STATUS_HUNDREDS_CLASS}]\d{{2}}\b",
    re.IGNORECASE,
)
_RUNTIME_ERROR_EXCEPTION_LINE_PATTERN = re.compile(
    rf"^[A-Za-z_][A-Za-z0-9_]*(?:{_RUNTIME_ERROR_EXCEPTION_SUFFIX_ALTERNATION})\s*:",
)
_RUNTIME_ERROR_TRACEBACK_FRAME_PATTERN = re.compile(
    rf'^(?:{_PYTHON_TRACEBACK_FRAME_LABEL_ALTERNATION}) ".+", line \d+',
)
_LANGUAGE_DIRECTIVE_PREFIXES = tuple(
    phrase.casefold()
    for phrase in material_values(
        CORE_MATERIALS, "language_response_directive", "directive_prefixes",
    )
)
_LANGUAGE_DIRECTIVE_SUFFIXES = tuple(
    phrase.casefold()
    for phrase in material_values(
        CORE_MATERIALS, "language_response_directive", "directive_suffixes",
    )
)
_LANGUAGE_CODE_MARKERS = tuple(
    marker.casefold()
    for marker in material_values(
        CORE_MATERIALS, "language_response_directive", "code_markers",
    )
)
_LANGUAGE_COORDINATION_MARKERS = tuple(
    marker.casefold()
    for marker in material_values(
        CORE_MATERIALS, "language_response_directive", "coordination_markers",
    )
)
_LANGUAGE_SCRIPT_CLASSES = material_values(
    CORE_MATERIALS, "language_target_scripts", "script_classes",
)
_LANGUAGE_TARGET_ALIASES = {
    script: tuple(
        alias.casefold()
        for alias in material_values(
            CORE_MATERIALS, "language_target_scripts", f"{script}_aliases",
        )
    )
    for script in _LANGUAGE_SCRIPT_CLASSES
}
_LANGUAGE_TECHNICAL_TOKENS = material_terms(
    CORE_MATERIALS, "language_ignored_technical_tokens",
)
_LANGUAGE_CODE_MARKER_ALTERNATION = "|".join(
    re.escape(marker) for marker in _LANGUAGE_CODE_MARKERS
)
_LANGUAGE_TECHNICAL_TOKEN_ALTERNATION = "|".join(
    re.escape(token) for token in _LANGUAGE_TECHNICAL_TOKENS
)
_LANGUAGE_CODE_MARKER_PATTERN = re.compile(
    rf"(?:{_LANGUAGE_CODE_MARKER_ALTERNATION})\s*[:=]\s*$", re.IGNORECASE,
)
_LANGUAGE_TECHNICAL_TOKEN_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9_])(?:{_LANGUAGE_TECHNICAL_TOKEN_ALTERNATION})(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_LANGUAGE_INLINE_CODE_PATTERN = re.compile(r"`[^`\r\n]{0,1024}`")
_LANGUAGE_QUOTED_TEXT_PATTERN = re.compile(
    r'(?:"[^"\r\n]{1,512}"|“[^”\r\n]{1,512}”)'
)
_LANGUAGE_URL_PATTERN = re.compile(
    r"\b(?:https?://|www\.)[^\s<>()\[\]{}]{1,2048}", re.IGNORECASE,
)
_FORMAT_DIRECTIVE_PREFIXES = tuple(
    phrase.casefold()
    for phrase in material_values(
        CORE_MATERIALS, "format_response_directive", "directive_prefixes",
    )
)
_FORMAT_DIRECTIVE_SUFFIXES = tuple(
    phrase.casefold()
    for phrase in material_values(
        CORE_MATERIALS, "format_response_directive", "directive_suffixes",
    )
)
_FORMAT_CONTRACT_TERMS = {
    "json_object": material_values(
        CORE_MATERIALS, "format_verifiable_contracts", "json_object_terms",
    ),
    "json_array": material_values(
        CORE_MATERIALS, "format_verifiable_contracts", "json_array_terms",
    ),
    "single_line": material_values(
        CORE_MATERIALS, "format_verifiable_contracts", "single_line_terms",
    ),
    "plain_text_no_markdown": (
        material_values(
            CORE_MATERIALS, "format_verifiable_contracts", "plain_text_terms",
        )
        + material_values(
            CORE_MATERIALS,
            "format_verifiable_contracts",
            "plain_text_negative_terms",
        )
    ),
    "code_fence_required": material_values(
        CORE_MATERIALS,
        "format_verifiable_contracts",
        "code_fence_required_terms",
    ),
    "code_fence_forbidden": material_values(
        CORE_MATERIALS,
        "format_verifiable_contracts",
        "code_fence_forbidden_terms",
    ),
}
_FORMAT_SELF_DIRECTIVE_TERMS = frozenset(
    term.casefold()
    for term in (
        material_values(
            CORE_MATERIALS,
            "format_verifiable_contracts",
            "plain_text_negative_terms",
        )
        + material_values(
            CORE_MATERIALS,
            "format_verifiable_contracts",
            "code_fence_forbidden_terms",
        )
    )
)
_MARKDOWN_LINK_PATTERN = re.compile(r"!?(?:\[[^\]\r\n]{1,256}\])\([^\)\r\n]{1,1024}\)")
_MARKDOWN_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_REFUSAL_STANCE_TERMS = material_terms(CORE_MATERIALS, "refusal_response_stance")
_REFUSAL_BOUNDARY_TERMS = material_terms(
    CORE_MATERIALS, "refusal_protected_boundary",
)
_REFUSAL_CAUSAL_TERMS = material_terms(CORE_MATERIALS, "refusal_causal_connector")
_REFUSAL_SENTENCE_BREAK_PATTERN = re.compile(r"[.!?。！？\r\n]")

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
    payload["core_material_version"] = CORE_MATERIALS.version
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
            if not any(char in candidate for char in _BASE64_DISTINCTIVE_CHARS):
                continue
            valid, limited = _validate_base64_candidate(
                candidate, int(config["max_decode_bytes"]),
            )
            decode_limited = decode_limited or limited
            if valid:
                add_candidate("base64", match.start(1), match.end(1))

    if config["detect_percent_encoding"]:
        for match in _PERCENT_ESCAPE_PATTERN.finditer(scanned):
            if match.group(0).count(_PERCENT_ESCAPE_PREFIX) >= int(config["min_percent_escape_count"]):
                add_candidate("percent_escape", match.start(), match.end())

    if config["detect_unicode_escape"]:
        for match in _UNICODE_ESCAPE_PATTERN.finditer(scanned):
            escape_count = len(
                _UNICODE_ESCAPE_UNIT_PATTERN.findall(match.group(0))
            )
            if escape_count >= int(config["min_unicode_escape_count"]):
                add_candidate("unicode_escape", match.start(), match.end())

    if config["detect_hex"]:
        for match in _HEX_BYTE_PATTERN.finditer(scanned):
            byte_count = len(re.findall(
                rf"[0-9A-Fa-f]{{{_HEX_BYTE_WIDTH}}}", match.group(0),
            ))
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
            1 for char in scanned
            if unicodedata.category(char) in _ZERO_WIDTH_UNICODE_CATEGORIES
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


def evaluate_output_detector(
    node: NormalizedNode, context: RailContext, text: str,
):
    """Evaluate one deterministic, policy-local Step 5 detector."""

    if node.template_key == "poor_quality_detector":
        matched, payload = _evaluate_poor_quality(node.config, text)
    elif node.template_key == "metadata_leakage_detector":
        matched, payload = _evaluate_metadata_leakage(node.config, text)
    elif node.template_key == "language_drift_detector":
        matched, payload = _evaluate_language_drift(
            node.config, context.current_input, text,
        )
    elif node.template_key == "format_violation_detector":
        matched, payload = _evaluate_format_violation(
            node.config, context.current_input, text,
        )
    elif node.template_key == "refusal_leakage_detector":
        matched, payload = _evaluate_refusal_leakage(node.config, text)
    else:
        raise ValueError(f"unsupported output detector {node.template_key}")
    payload["detector"] = node.template_key
    payload["core_material_version"] = CORE_MATERIALS.version
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "default")),
        metadata=payload,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


def evaluate_random_signal(node: NormalizedNode):
    """Sample one independent boolean signal for a policy graph node."""

    probability = float(node.config.get("probability", 0.5))
    roll = random.random()
    matched = roll < probability
    payload = {
        "component": "random_signal",
        "probability": probability,
        "roll": roll,
        "sampled": matched,
    }
    return make_node_result(
        node,
        matched=matched,
        action_on_hit=str(node.config.get("action_on_hit", "observe")),
        metadata=payload,
        signal=NodeSignal(value=matched, truthy=matched, payload=payload),
    )


def prepare_sensitive_echo_text(config: dict, text: str) -> tuple[str, bool]:
    """Return the bounded, optional-code-free output view for virtual rechecks."""

    scanned, truncated = _normalized_window(
        text, int(config["scan_limit_chars"]), casefold=False,
    )
    if bool(config.get("ignore_fenced_code", True)):
        scanned = _without_fenced_code(scanned)
    return scanned, truncated


def _validate_base64_candidate(value: str, max_decode_bytes: int) -> tuple[bool, bool]:
    unpadded = value.rstrip(_BASE64_PADDING_CHAR)
    if (
        not unpadded
        or _BASE64_PADDING_CHAR in unpadded
        or len(unpadded) % 4 == 1
    ):
        return False, False
    estimated_size = (len(unpadded) * 3) // 4
    if estimated_size > max_decode_bytes:
        return True, True
    padded = unpadded + _BASE64_PADDING_CHAR * (-len(unpadded) % 4)
    try:
        base64.b64decode(padded, altchars=_BASE64_ALTCHARS, validate=True)
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


def _evaluate_poor_quality(config: dict, text: str) -> tuple[bool, dict]:
    """Detect clear generation failures without judging response usefulness."""

    scanned, truncated = _normalized_window(
        text, int(config["scan_limit_chars"]), casefold=False,
    )
    analysis_text = (
        _without_fenced_code(scanned)
        if bool(config["ignore_fenced_code"])
        else scanned
    )
    raw_visible_count = sum(
        1 for char in scanned
        if not char.isspace() and not unicodedata.category(char).startswith("C")
    )
    visible = [
        char for char in analysis_text
        if not char.isspace() and not unicodedata.category(char).startswith("C")
    ]
    visible_count = len(visible)
    punctuation_count = sum(
        1 for char in visible if unicodedata.category(char).startswith("P")
    )
    punctuation_ratio = punctuation_count / max(1, visible_count)
    reason_codes: list[str] = []
    if not truncated and raw_visible_count < int(config["min_visible_chars"]):
        reason_codes.append("empty_output")
    if (
        not truncated
        and visible_count >= int(config["min_visible_chars"])
        and punctuation_ratio >= float(config["max_punctuation_ratio"])
    ):
        reason_codes.append("punctuation_only")
    repeat_run = _longest_repeat_run(analysis_text)
    if repeat_run >= int(config["min_repeat_run"]):
        reason_codes.append("repeat_run")
    duplicate_count, duplicate_ratio = _duplicate_line_stats(
        analysis_text, int(config["duplicate_line_min_chars"]),
    )
    if duplicate_count >= int(config["duplicate_line_min_count"]):
        reason_codes.append("duplicate_lines")
    error_envelope = (
        _has_unformatted_error_envelope(analysis_text)
        if bool(config["detect_unformatted_error_envelope"])
        else False
    )
    if error_envelope:
        reason_codes.append("unformatted_error_envelope")

    matched = len(reason_codes) >= int(config["min_signal_families"])
    score = 0
    if "empty_output" in reason_codes:
        score = max(score, 90)
    if "unformatted_error_envelope" in reason_codes:
        score = max(score, 85)
    if "punctuation_only" in reason_codes:
        score = max(score, 80)
    if "repeat_run" in reason_codes:
        score = max(score, min(80, 60 + repeat_run // 8))
    if "duplicate_lines" in reason_codes:
        score = max(score, min(80, 55 + duplicate_count * 5))
    if len(reason_codes) > 1:
        score = min(100, score + (len(reason_codes) - 1) * 5)

    return matched, {
        "reason_codes": reason_codes,
        "score": score,
        "raw_char_count": len(text or ""),
        "scanned_char_count": len(scanned),
        "raw_visible_char_count": raw_visible_count,
        "visible_char_count": visible_count,
        "punctuation_ratio": round(punctuation_ratio, 4),
        "max_repeat_run": repeat_run,
        "duplicate_line_count": duplicate_count,
        "duplicate_line_ratio": round(duplicate_ratio, 4),
        "error_envelope_detected": error_envelope,
        "scan_truncated": truncated,
    }


def _evaluate_metadata_leakage(config: dict, text: str) -> tuple[bool, dict]:
    """Find complete runtime artefact shapes without retaining their contents."""

    scanned, truncated = _normalized_window(
        text, int(config["scan_limit_chars"]), casefold=False,
    )
    analysis_text = (
        _without_fenced_code(scanned)
        if bool(config["ignore_fenced_code"])
        else scanned
    )
    reason_codes: list[str] = []
    artifact_spans: list[tuple[int, int]] = []
    traceback_spans = _python_traceback_spans(analysis_text)
    if traceback_spans:
        reason_codes.append("traceback_envelope")
        artifact_spans.extend(traceback_spans)
    tool_spans, structure_scan_limited = _tool_call_envelope_spans(
        analysis_text, int(config["max_structures"]),
    )
    if tool_spans:
        reason_codes.append("tool_call_envelope")
        artifact_spans.extend(tool_spans)
    marker_count = analysis_text.count(INTERNAL_MARKER)
    if marker_count:
        reason_codes.append("internal_control_marker")
        marker_length = len(INTERNAL_MARKER)
        start = 0
        for _ in range(marker_count):
            start = analysis_text.find(INTERNAL_MARKER, start)
            if start < 0:
                break
            artifact_spans.append((start, start + marker_length))
            start += marker_length

    visible_count = sum(
        1 for char in analysis_text
        if not char.isspace() and not unicodedata.category(char).startswith("C")
    )
    artifact_char_count = _merged_span_length(artifact_spans)
    coverage = artifact_char_count / max(1, visible_count)
    score = 0
    if "internal_control_marker" in reason_codes:
        score = max(score, 100)
    if "traceback_envelope" in reason_codes:
        score = max(score, 90)
    if "tool_call_envelope" in reason_codes:
        score = max(score, 85)
    if len(reason_codes) > 1:
        score = min(100, score + (len(reason_codes) - 1) * 5)

    return bool(reason_codes), {
        "reason_codes": reason_codes,
        "score": score,
        "raw_char_count": len(text or ""),
        "scanned_char_count": len(scanned),
        "artifact_count": len(artifact_spans),
        "artifact_coverage_bucket": _coverage_bucket(coverage),
        "structure_scan_limited": structure_scan_limited,
        "scan_truncated": truncated,
    }


def _evaluate_language_drift(
    config: dict, request_text: str, response_text: str,
) -> tuple[bool, dict]:
    """Find strong script drift without treating language quality as a verdict."""

    request_scanned, request_truncated = _normalized_window(
        request_text, int(config["scan_limit_chars"]), casefold=False,
    )
    response_scanned, response_truncated = _normalized_window(
        response_text, int(config["scan_limit_chars"]), casefold=False,
    )
    intent_text = _language_intent_text(request_scanned, config)
    explicit_script, explicit_candidate_count = _explicit_language_script(intent_text)
    request_analysis, request_ignored_segments = _language_analysis_text(
        request_scanned, config,
    )
    response_analysis, response_ignored_segments = _language_analysis_text(
        response_scanned, config,
    )
    request_counts = _language_script_counts(request_analysis)
    response_counts = _language_script_counts(response_analysis)
    request_analyzable_chars = sum(request_counts.values())
    response_analyzable_chars = sum(response_counts.values())
    request_primary, request_primary_ratio = _language_primary_script(request_counts)
    response_primary, response_primary_ratio = _language_primary_script(response_counts)

    minimum = int(config["min_analyzable_chars"])
    baseline_script = ""
    expectation_source = "unavailable"
    if explicit_script:
        baseline_script = explicit_script
        expectation_source = "explicit"
    elif (
        request_analyzable_chars >= minimum
        and request_primary
        and request_primary_ratio >= float(config["dominant_script_ratio"])
    ):
        baseline_script = request_primary
        expectation_source = "inferred"

    baseline_count = _language_baseline_count(response_counts, baseline_script)
    baseline_ratio = baseline_count / max(1, response_analyzable_chars)
    output_is_foreign = bool(
        response_primary
        and not _language_script_is_compatible(baseline_script, response_primary)
    )
    dominant_drift = bool(
        baseline_script
        and response_analyzable_chars >= minimum
        and output_is_foreign
        and response_primary_ratio >= float(config["dominant_script_ratio"])
        and baseline_ratio <= float(config["max_baseline_script_ratio"])
    )
    foreign_run_count = 0
    if (
        baseline_script
        and response_analyzable_chars >= minimum
        and baseline_ratio >= float(config["dominant_script_ratio"])
    ):
        foreign_run_count = _foreign_script_run_count(
            response_analysis,
            baseline_script,
            int(config["min_foreign_script_run_chars"]),
        )

    reason_codes: list[str] = []
    if dominant_drift:
        reason_codes.append("dominant_script_drift")
    if foreign_run_count:
        reason_codes.append("foreign_script_contamination")
    score = 0
    if dominant_drift:
        score = max(score, 85)
    if foreign_run_count:
        score = max(score, min(80, 65 + min(foreign_run_count, 3) * 5))
    if len(reason_codes) > 1:
        score = min(100, score + 10)

    return bool(reason_codes), {
        "reason_codes": reason_codes,
        "score": score,
        "expectation_source": expectation_source,
        "request_script_class": request_primary or "unknown",
        "output_script_class": response_primary or "unknown",
        "explicit_language_candidate_count": explicit_candidate_count,
        "request_analyzable_char_count": request_analyzable_chars,
        "output_analyzable_char_count": response_analyzable_chars,
        "baseline_script_ratio_bucket": _ratio_bucket(baseline_ratio),
        "dominant_script_ratio_bucket": _ratio_bucket(response_primary_ratio),
        "foreign_script_run_count": foreign_run_count,
        "ignored_segment_count": request_ignored_segments + response_ignored_segments,
        "request_raw_char_count": len(request_text or ""),
        "output_raw_char_count": len(response_text or ""),
        "scan_truncated": request_truncated or response_truncated,
    }


def _evaluate_format_violation(
    config: dict, request_text: str, response_text: str,
) -> tuple[bool, dict]:
    """Compare only explicit, locally verifiable format contracts with output."""

    request_scanned, request_truncated = _normalized_window(
        request_text, int(config["scan_limit_chars"]), casefold=False,
    )
    response_scanned, response_truncated = _normalized_window(
        response_text, int(config["scan_limit_chars"]), casefold=False,
    )
    contracts, candidate_count, candidate_limited = _extract_format_contracts(
        _format_intent_text(request_scanned),
        int(config["max_contract_candidates"]),
    )
    response_view = (
        response_scanned.strip()
        if bool(config["allow_surrounding_whitespace"])
        else response_scanned
    )
    visible_line_count = (
        sum(1 for line in response_view.splitlines() if line.strip())
        if bool(config["allow_surrounding_whitespace"])
        else len(response_view.splitlines())
    )
    complete_fence_count = _complete_code_fence_count(response_view)
    code_fence_present = _has_code_fence_marker(response_view)
    markdown_structure_count = _markdown_structure_count(response_view)
    reason_codes: list[str] = []
    for contract in contracts:
        if contract in {"json_object", "json_array"}:
            json_reason = _json_contract_reason(
                response_view,
                contract,
                allow_surrounding_whitespace=bool(config["allow_surrounding_whitespace"]),
            )
            if json_reason and json_reason not in reason_codes:
                reason_codes.append(json_reason)
        elif contract == "single_line" and visible_line_count > 1:
            reason_codes.append("requested_single_line_multiline")
        elif contract == "plain_text_no_markdown" and markdown_structure_count:
            reason_codes.append("requested_plain_text_markdown")
        elif contract == "code_fence_required" and not complete_fence_count:
            reason_codes.append("requested_fence_missing")
        elif contract == "code_fence_forbidden" and code_fence_present:
            reason_codes.append("requested_fence_present")

    score = 0
    if "requested_json_invalid" in reason_codes:
        score = max(score, 80)
    if "requested_json_wrong_top_level" in reason_codes:
        score = max(score, 75)
    if set(reason_codes) & {
        "requested_single_line_multiline",
        "requested_plain_text_markdown",
        "requested_fence_missing",
        "requested_fence_present",
    }:
        score = max(score, 65)
    if len(reason_codes) > 1:
        score = min(100, score + (len(reason_codes) - 1) * 5)

    return bool(reason_codes), {
        "reason_codes": reason_codes,
        "score": score,
        "contract_kinds": contracts,
        "contract_candidate_count": candidate_count,
        "contract_candidate_limited": candidate_limited,
        "active_contract_count": len(contracts),
        "visible_line_count": visible_line_count,
        "markdown_structure_count": markdown_structure_count,
        "complete_code_fence_count": complete_fence_count,
        "request_raw_char_count": len(request_text or ""),
        "output_raw_char_count": len(response_text or ""),
        "scan_truncated": request_truncated or response_truncated,
    }


def _evaluate_refusal_leakage(config: dict, text: str) -> tuple[bool, dict]:
    """Find a bounded refusal explanation of a protected internal boundary."""

    scanned, truncated = _normalized_window(
        text, int(config["scan_limit_chars"]), casefold=False,
    )
    analysis_text = scanned
    if bool(config["ignore_fenced_code"]):
        analysis_text = _without_fenced_code(analysis_text)
    # A quotation is commonly a teaching, reporting, or translation example;
    # it is not this assistant's refusal explanation.
    analysis_text = _LANGUAGE_QUOTED_TEXT_PATTERN.sub(" ", analysis_text)
    normalized = analysis_text.casefold()
    refusal_spans = _refusal_term_spans(normalized, _REFUSAL_STANCE_TERMS)
    boundary_spans = _refusal_term_spans(normalized, _REFUSAL_BOUNDARY_TERMS)
    causal_spans = _refusal_term_spans(normalized, _REFUSAL_CAUSAL_TERMS)
    relations = _refusal_relations(
        normalized,
        refusal_spans,
        boundary_spans,
        causal_spans,
        int(config["max_relation_gap_chars"]),
    )
    best_relation = max(
        relations,
        key=lambda item: (item[0], -item[1]),
        default=None,
    )
    evidence_family_count = best_relation[0] if best_relation else 0
    relation_gap = best_relation[1] if best_relation else None
    matched = bool(
        best_relation
        and evidence_family_count >= int(config["min_evidence_families"])
    )
    score = 0
    if matched:
        score = 90 if evidence_family_count >= 3 else 80
        score = min(100, score + min(max(0, len(relations) - 1), 2) * 5)

    return matched, {
        "reason_codes": ["refusal_policy_exposure"] if matched else [],
        "score": score,
        "evidence_family_count": evidence_family_count,
        "refusal_evidence_count": len(refusal_spans),
        "boundary_evidence_count": len(boundary_spans),
        "causal_evidence_count": len(causal_spans),
        "relation_candidate_count": len(relations),
        "relation_gap_bucket": _refusal_relation_gap_bucket(
            relation_gap, int(config["max_relation_gap_chars"]),
        ),
        "raw_char_count": len(text or ""),
        "scanned_char_count": len(scanned),
        "scan_truncated": truncated,
    }


def _refusal_term_spans(
    text: str, terms: tuple[str, ...],
) -> list[tuple[int, int]]:
    """Return the longest non-overlapping material matches in stable order."""

    matches = sorted(
        (
            (position, position + len(term.casefold()))
            for term in terms
            for position in _semantic_term_positions(text, (term.casefold(),))
        ),
        key=lambda item: (item[0], -(item[1] - item[0])),
    )
    spans: list[tuple[int, int]] = []
    for start, end in matches:
        if any(start < other_end and end > other_start for other_start, other_end in spans):
            continue
        spans.append((start, end))
    return spans


def _refusal_relations(
    text: str,
    refusal_spans: list[tuple[int, int]],
    boundary_spans: list[tuple[int, int]],
    causal_spans: list[tuple[int, int]],
    maximum_gap: int,
) -> list[tuple[int, int]]:
    """Return relation evidence-family counts and anchor gaps without text."""

    relations: list[tuple[int, int]] = []
    for refusal_start, refusal_end in refusal_spans:
        for boundary_start, boundary_end in boundary_spans:
            gap = _span_gap(
                refusal_start,
                refusal_end,
                boundary_start,
                boundary_end,
            )
            if gap > maximum_gap:
                continue
            relation_start = min(refusal_start, boundary_start)
            relation_end = max(refusal_end, boundary_end)
            same_sentence = _REFUSAL_SENTENCE_BREAK_PATTERN.search(
                text[relation_start:relation_end]
            ) is None
            if same_sentence:
                sentence_start = _refusal_sentence_start(text, relation_start)
                sentence_end = _refusal_sentence_end(text, relation_end)
                causal_linked = any(
                    causal_start >= sentence_start and causal_end <= sentence_end
                    for causal_start, causal_end in causal_spans
                )
            else:
                causal_linked = any(
                    causal_start <= relation_end and causal_end >= relation_start
                    for causal_start, causal_end in causal_spans
                )
            if not (same_sentence or causal_linked):
                continue
            relations.append((2 + int(causal_linked), gap))
    return relations


def _refusal_sentence_start(text: str, position: int) -> int:
    latest = -1
    for match in _REFUSAL_SENTENCE_BREAK_PATTERN.finditer(text, 0, position):
        latest = match.end()
    return latest


def _refusal_sentence_end(text: str, position: int) -> int:
    match = _REFUSAL_SENTENCE_BREAK_PATTERN.search(text, position)
    return match.start() if match else len(text)


def _span_gap(first_start: int, first_end: int, second_start: int, second_end: int) -> int:
    if first_end < second_start:
        return second_start - first_end
    if second_end < first_start:
        return first_start - second_end
    return 0


def _refusal_relation_gap_bucket(gap: int | None, maximum_gap: int) -> str:
    if gap is None:
        return "none"
    if gap <= 8:
        return "adjacent"
    if gap <= min(32, maximum_gap):
        return "near"
    return "within_limit"


def _extract_format_contracts(
    text: str, maximum: int,
) -> tuple[list[str], int, bool]:
    """Return non-conflicting command-qualified format kinds without source text."""

    normalized = text.casefold()
    matches: list[tuple[int, int, str]] = []
    for contract, terms in _FORMAT_CONTRACT_TERMS.items():
        for term in terms:
            normalized_term = term.casefold()
            for position in _semantic_term_positions(normalized, (normalized_term,)):
                end = position + len(normalized_term)
                if (
                    normalized_term not in _FORMAT_SELF_DIRECTIVE_TERMS
                    and not _has_format_directive(normalized, position, end)
                ):
                    continue
                matches.append((position, end, contract))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    candidate_limited = len(matches) > maximum
    accepted_spans: list[tuple[int, int]] = []
    contracts: list[str] = []
    for start, end, contract in matches[:maximum]:
        if any(start < other_end and end > other_start for other_start, other_end in accepted_spans):
            continue
        accepted_spans.append((start, end))
        if contract not in contracts:
            contracts.append(contract)

    contract_set = set(contracts)
    if {"json_object", "json_array"} <= contract_set:
        contracts = [
            contract
            for contract in contracts
            if contract not in {"json_object", "json_array"}
        ]
    if {"code_fence_required", "code_fence_forbidden"} <= set(contracts):
        contracts = [
            contract
            for contract in contracts
            if contract not in {"code_fence_required", "code_fence_forbidden"}
        ]
    return contracts, min(len(matches), maximum), candidate_limited


def _has_format_directive(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 80):start].rstrip()
    before_without_article = re.sub(r"\s+(?:a|an|the)\s*$", "", before)
    after = text[end:end + 48].lstrip()
    if any(
        before.endswith(prefix) or before_without_article.endswith(prefix)
        for prefix in _FORMAT_DIRECTIVE_PREFIXES
    ) or any(after.startswith(suffix) for suffix in _FORMAT_DIRECTIVE_SUFFIXES):
        return True

    # A single explicit command may join two format anchors: for example,
    # "reply only in a JSON object and JSON array".  Carry the command
    # qualifier across that short coordination so contradictory contracts can
    # fail open instead of silently treating the first format as authoritative.
    return any(
        re.search(
            rf"{re.escape(prefix)}\s+[^.!?;:\n]{{0,64}}(?:\band\b|\bor\b|,)\s*$",
            before,
        )
        for prefix in _FORMAT_DIRECTIVE_PREFIXES
    )


def _format_intent_text(text: str) -> str:
    """Exclude quoted and code examples from request-format extraction."""

    intent_text = _without_fenced_code(text)
    intent_text = _LANGUAGE_INLINE_CODE_PATTERN.sub(" ", intent_text)
    return _LANGUAGE_QUOTED_TEXT_PATTERN.sub(" ", intent_text)


def _json_contract_reason(
    text: str, contract: str, *, allow_surrounding_whitespace: bool,
) -> str:
    if not allow_surrounding_whitespace and text != text.strip():
        return "requested_json_invalid"
    try:
        value = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return "requested_json_invalid"
    if contract == "json_object" and not isinstance(value, dict):
        return "requested_json_wrong_top_level"
    if contract == "json_array" and not isinstance(value, list):
        return "requested_json_wrong_top_level"
    return ""


def _complete_code_fence_count(text: str) -> int:
    fence = ""
    complete_count = 0
    for line in text.splitlines():
        marker = line.lstrip()
        if not fence and marker.startswith(("```", "~~~")):
            fence = marker[:3]
        elif fence and marker.startswith(fence):
            complete_count += 1
            fence = ""
    return complete_count


def _has_code_fence_marker(text: str) -> bool:
    return any(
        line.lstrip().startswith(("```", "~~~")) for line in text.splitlines()
    )


def _markdown_structure_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if (
            stripped.startswith(("#", "```", "~~~", "|"))
            or _MARKDOWN_LIST_PATTERN.match(line)
            or _MARKDOWN_LINK_PATTERN.search(line)
        ):
            count += 1
    return count


def _explicit_language_script(text: str) -> tuple[str, int]:
    """Return one unambiguous, directive-qualified language script, if any."""

    normalized = text.casefold()
    matched_scripts: list[str] = []
    candidate_count = 0
    for script, aliases in _LANGUAGE_TARGET_ALIASES.items():
        for alias in aliases:
            for position in _semantic_term_positions(normalized, (alias,)):
                end = position + len(alias)
                before = normalized[max(0, position - 80):position].rstrip()
                after = normalized[end:end + 48].lstrip()
                prefix_matches = any(
                    before.endswith(prefix) for prefix in _LANGUAGE_DIRECTIVE_PREFIXES
                )
                suffix_matches = any(
                    after.startswith(suffix) for suffix in _LANGUAGE_DIRECTIVE_SUFFIXES
                )
                code_marker_matches = bool(
                    alias.isascii()
                    and len(alias) <= 3
                    and _LANGUAGE_CODE_MARKER_PATTERN.search(before)
                )
                if not (prefix_matches or suffix_matches or code_marker_matches):
                    continue
                coordinated_scripts = _coordinated_language_scripts(normalized, end)
                candidate_count = min(
                    8, candidate_count + 1 + len(coordinated_scripts),
                )
                matched_scripts.append(script)
                matched_scripts.extend(coordinated_scripts)
    unique_scripts = tuple(dict.fromkeys(matched_scripts))
    if len(unique_scripts) == 1:
        return unique_scripts[0], candidate_count
    return "", candidate_count


def _coordinated_language_scripts(text: str, start: int) -> list[str]:
    """Collect immediately coordinated language targets as an ambiguity guard."""

    following = text[start:start + 48]
    scripts: list[str] = []
    for script, aliases in _LANGUAGE_TARGET_ALIASES.items():
        for alias in aliases:
            for position in _semantic_term_positions(following, (alias,)):
                marker = following[:position].strip()
                if marker in _LANGUAGE_COORDINATION_MARKERS:
                    scripts.append(script)
    return scripts


def _language_analysis_text(text: str, config: dict) -> tuple[str, int]:
    """Remove known non-natural-language segments from a bounded scan window."""

    analysis = text
    ignored_segments = 0
    if bool(config["ignore_fenced_code"]):
        fenced_line_count = sum(
            1
            for line in analysis.splitlines()
            if line.lstrip().startswith(("```", "~~~"))
        )
        ignored_segments += fenced_line_count // 2
        analysis = _without_fenced_code(analysis)
    if bool(config["ignore_inline_code"]):
        analysis, count = _LANGUAGE_INLINE_CODE_PATTERN.subn(" ", analysis)
        ignored_segments += count
    analysis, count = _LANGUAGE_URL_PATTERN.subn(" ", analysis)
    ignored_segments += count
    analysis, count = _LANGUAGE_TECHNICAL_TOKEN_PATTERN.subn(" ", analysis)
    ignored_segments += count
    ignored_segments += sum(
        1
        for line in analysis.splitlines()
        if line.strip() and not any(_language_char_script(char) for char in line)
    )
    return analysis, ignored_segments


def _language_intent_text(text: str, config: dict) -> str:
    """Discard quoted and code examples before extracting a response directive."""

    intent_text = text
    if bool(config["ignore_fenced_code"]):
        intent_text = _without_fenced_code(intent_text)
    if bool(config["ignore_inline_code"]):
        intent_text = _LANGUAGE_INLINE_CODE_PATTERN.sub(" ", intent_text)
    return _LANGUAGE_QUOTED_TEXT_PATTERN.sub(" ", intent_text)


def _language_script_counts(text: str) -> dict[str, int]:
    counts = {script: 0 for script in _LANGUAGE_SCRIPT_CLASSES}
    for char in text:
        script = _language_char_script(char)
        if script in counts:
            counts[script] += 1
    return counts


def _language_char_script(char: str) -> str:
    codepoint = ord(char)
    if 0x3040 <= codepoint <= 0x30FF or 0x31F0 <= codepoint <= 0x31FF:
        return "japanese"
    if (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    ):
        return "han"
    if 0xAC00 <= codepoint <= 0xD7AF or 0x1100 <= codepoint <= 0x11FF:
        return "hangul"
    if 0x0400 <= codepoint <= 0x052F:
        return "cyrillic"
    if 0x0600 <= codepoint <= 0x06FF or 0x0750 <= codepoint <= 0x077F:
        return "arabic"
    if char.isalpha() and "LATIN" in unicodedata.name(char, ""):
        return "latin"
    return ""


def _language_primary_script(counts: dict[str, int]) -> tuple[str, float]:
    total = sum(counts.values())
    if not total:
        return "", 0.0
    candidates = dict(counts)
    if counts.get("japanese", 0) >= 2:
        candidates["japanese"] = counts["japanese"] + counts.get("han", 0)
        candidates["han"] = 0
    script, amount = max(candidates.items(), key=lambda item: item[1])
    return (script, amount / total) if amount else ("", 0.0)


def _language_baseline_count(counts: dict[str, int], baseline_script: str) -> int:
    if not baseline_script:
        return 0
    if baseline_script == "japanese":
        return counts.get("japanese", 0) + counts.get("han", 0)
    if baseline_script == "han" and counts.get("japanese", 0) >= 2:
        return 0
    return counts.get(baseline_script, 0)


def _language_script_is_compatible(baseline_script: str, script: str) -> bool:
    return bool(
        baseline_script
        and (baseline_script == script or (baseline_script == "japanese" and script == "han"))
    )


def _foreign_script_run_count(
    text: str, baseline_script: str, minimum_length: int,
) -> int:
    count = 0
    run_script = ""
    run_length = 0

    def finish_run() -> None:
        nonlocal count, run_script, run_length
        if run_script and run_length >= minimum_length:
            count += 1
        run_script = ""
        run_length = 0

    for char in text:
        script = _language_char_script(char)
        if not script or _language_script_is_compatible(baseline_script, script):
            finish_run()
        elif script == run_script:
            run_length += 1
        else:
            finish_run()
            run_script = script
            run_length = 1
    finish_run()
    return count


def _ratio_bucket(ratio: float) -> str:
    if ratio >= 0.8:
        return "80_100"
    if ratio >= 0.6:
        return "60_79"
    if ratio >= 0.4:
        return "40_59"
    if ratio >= 0.2:
        return "20_39"
    return "0_19"


def _python_traceback_spans(text: str) -> list[tuple[int, int]]:
    """Recognize canonical Python tracebacks by layout, not exception words."""

    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    spans: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if line.strip() not in _PYTHON_TRACEBACK_HEADERS:
            continue
        frame_count = 0
        end_index: int | None = None
        for candidate_index in range(index + 1, min(len(lines), index + 65)):
            candidate = lines[candidate_index].strip()
            if _PYTHON_TRACEBACK_FRAME_PATTERN.fullmatch(candidate):
                frame_count += 1
                continue
            if frame_count and _PYTHON_EXCEPTION_LINE_PATTERN.fullmatch(candidate):
                end_index = candidate_index + 1
                break
        if frame_count and end_index is not None:
            start = offsets[index]
            end = offsets[end_index] if end_index < len(offsets) else len(text)
            spans.append((start, end))
    return spans


def _tool_call_envelope_spans(text: str, max_structures: int) -> tuple[list[tuple[int, int]], bool]:
    spans: list[tuple[int, int]] = []
    candidates, limited = _balanced_json_object_spans(text, max_structures)
    for start, end in candidates:
        try:
            value = json.loads(text[start:end])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if _is_tool_call_envelope(value):
            spans.append((start, end))
    return spans, limited


def _balanced_json_object_spans(text: str, max_structures: int) -> tuple[list[tuple[int, int]], bool]:
    """Extract bounded balanced JSON-object candidates without regex harvesting."""

    spans: list[tuple[int, int]] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
                if len(spans) >= max_structures:
                    return spans, True
                start = None
            elif depth < 0:
                start = None
                depth = 0
    return spans, False


def _is_tool_call_envelope(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    for method_field in _RUNTIME_TOOL_METHOD_FIELDS:
        method = value.get(method_field)
        for parameter_field in _RUNTIME_TOOL_PARAMETER_FIELDS:
            parameters = value.get(parameter_field)
            if (
                isinstance(method, str)
                and method.strip()
                and isinstance(parameters, (dict, list))
            ):
                return True
    for name_field in _RUNTIME_TOOL_NAME_FIELDS:
        name = value.get(name_field)
        for argument_field in _RUNTIME_TOOL_ARGUMENT_FIELDS:
            arguments = value.get(argument_field)
            if (
                isinstance(name, str)
                and name.strip()
                and isinstance(arguments, (dict, list, str))
            ):
                return True
    for function_field in _RUNTIME_TOOL_FUNCTION_FIELDS:
        function = value.get(function_field)
        if isinstance(function, dict):
            return _is_tool_call_envelope(function)
    for tool_calls_field in _RUNTIME_TOOL_CALLS_FIELDS:
        tool_calls = value.get(tool_calls_field)
        if isinstance(tool_calls, list):
            return any(_is_tool_call_envelope(item) for item in tool_calls)
    return False


def _merged_span_length(spans: list[tuple[int, int]]) -> int:
    if not spans:
        return 0
    total = 0
    previous_start, previous_end = sorted(spans)[0]
    for start, end in sorted(spans)[1:]:
        if start > previous_end:
            total += previous_end - previous_start
            previous_start, previous_end = start, end
        else:
            previous_end = max(previous_end, end)
    return total + previous_end - previous_start


def _coverage_bucket(coverage: float) -> str:
    if coverage >= 0.9:
        return "90_100"
    if coverage >= 0.6:
        return "60_89"
    if coverage >= 0.3:
        return "30_59"
    return "0_29"


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
        category: _positions(scanned, terms)
        for category, terms in _INSTRUCTION_INTENT_TERMS.items()
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


def _without_fenced_code(text: str) -> str:
    """Remove fenced code content while preserving non-code line boundaries."""

    kept: list[str] = []
    fence = ""
    for line in text.splitlines(keepends=True):
        marker = line.lstrip()
        if not fence and (marker.startswith("```") or marker.startswith("~~~")):
            fence = marker[:3]
            kept.append("\n" if line.endswith("\n") else "")
            continue
        if fence:
            if marker.startswith(fence):
                fence = ""
            kept.append("\n" if line.endswith("\n") else "")
            continue
        kept.append(line)
    return "".join(kept)


def _has_unformatted_error_envelope(text: str) -> bool:
    """Recognize complete error artefacts without retaining their contents."""

    stripped = text.strip()
    if not stripped:
        return False
    parsed = _parse_json_object(stripped)
    if isinstance(parsed, dict):
        keys = {str(key).casefold() for key in parsed}
        if (
            bool(keys & _RUNTIME_ERROR_OBJECT_FIELDS)
            and bool(keys & _RUNTIME_ERROR_OBJECT_STRUCTURE_FIELDS)
        ):
            return True

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    has_traceback = first_line.casefold().startswith(
        _PYTHON_TRACEBACK_HEADER_PREFIXES
    ) and any(
        _RUNTIME_ERROR_TRACEBACK_FRAME_PATTERN.match(line) for line in lines[1:]
    )
    if has_traceback:
        return True
    has_error_header = bool(_RUNTIME_ERROR_HEADER_PATTERN.match(first_line))
    has_status = bool(_RUNTIME_ERROR_STATUS_PATTERN.search(stripped))
    has_exception_type = bool(_RUNTIME_ERROR_EXCEPTION_LINE_PATTERN.match(first_line))
    return has_exception_type or (has_error_header and has_status)


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
    name = name.strip()
    for suffix in _ROLE_HEADER_OPTIONAL_SUFFIXES:
        name = name.removesuffix(suffix)
    return bool(separator and content.strip() and name in _ROLE_HEADER_ROLE_NAMES)


def _looks_like_message_envelope(text: str) -> bool:
    fields = _MESSAGE_ENVELOPE_ROLE_FIELDS + _MESSAGE_ENVELOPE_CONTENT_FIELDS
    return all(f'"{field}"' in text for field in fields) and any(
        f'"{role}"' in text for role in _MESSAGE_ENVELOPE_WEAK_ROLE_VALUES
    )


def _looks_like_tool_envelope(text: str) -> bool:
    return any(token in text for token in _TOOL_ENVELOPE_CALL_FIELDS) and any(
        token in text for token in _TOOL_ENVELOPE_WEAK_ARGUMENT_FIELDS
    )


def _is_complete_message_envelope(text: str) -> bool:
    parsed = _parse_json_object(text)
    if not isinstance(parsed, dict):
        return False
    role = parsed.get(_MESSAGE_ENVELOPE_ROLE_FIELDS[0])
    content = parsed.get(_MESSAGE_ENVELOPE_CONTENT_FIELDS[0])
    return (
        isinstance(role, str)
        and role.casefold() in _MESSAGE_ENVELOPE_STRONG_ROLE_VALUES
        and isinstance(content, str)
        and bool(content.strip())
    )


def _is_complete_tool_envelope(text: str) -> bool:
    parsed = _parse_json_object(text)
    if not isinstance(parsed, dict):
        return False
    call = parsed.get(_TOOL_ENVELOPE_STRONG_CALL_FIELDS[0])
    return (
        isinstance(call, dict)
        and all(
            isinstance(call.get(field), str) and bool(call[field].strip())
            for field in _TOOL_ENVELOPE_STRONG_NONEMPTY_STRING_FIELDS
        )
        and all(field in call for field in _TOOL_ENVELOPE_STRONG_PRESENCE_FIELDS)
    )


def _is_complete_chatml_envelope(text: str) -> bool:
    prefix = _CHATML_START_DELIMITERS[0]
    if not text.startswith(prefix):
        return False
    remainder = text[len(prefix):].lstrip()
    role, separator, content = remainder.partition("\n")
    return bool(
        separator
        and role.strip() in _CHATML_STRONG_ROLE_VALUES
        and content.strip()
    )


def _parse_json_object(text: str):
    try:
        return json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _has_reserved_delimiters(text: str) -> bool:
    return any(
        opening in text and closing in text
        for opening, closing in zip(
            _RESERVED_DELIMITER_OPENS, _RESERVED_DELIMITER_CLOSES,
        )
    )


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
