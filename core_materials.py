"""Versioned, code-owned facts used by local detector implementations.

The core material set is intentionally small.  It records protocol, intent,
and runtime-artifact facts needed by deterministic structural checks; it is
not a configurable keyword list, a RAG corpus, or a standalone risk decision
engine.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Literal


MaterialCategory = Literal[
    "protocol",
    "intent_slot",
    "operation_grammar",
    "encoding_format",
    "runtime_artifact",
    "language_intent",
    "format_contract",
    "refusal_structure",
]
MaterialSourceKind = Literal[
    "public_standard",
    "first_party_observation",
    "first_party_design",
]

_MATERIAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FACT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_CATEGORIES = {
    "protocol",
    "intent_slot",
    "operation_grammar",
    "encoding_format",
    "runtime_artifact",
    "language_intent",
    "format_contract",
    "refusal_structure",
}
_ALLOWED_SOURCE_KINDS = {
    "public_standard",
    "first_party_observation",
    "first_party_design",
}
MAX_ENTRIES_PER_CATEGORY = 32
MAX_SERIALIZED_BYTES = 16 * 1024


@dataclass(frozen=True)
class CoreMaterialEntry:
    """One auditable detector fact with only immutable string values."""

    material_id: str
    category: MaterialCategory
    introduced_in: str
    source_kind: MaterialSourceKind
    purpose: str
    test_id: str
    facts: tuple[tuple[str, tuple[str, ...]], ...]

    def values(self, name: str) -> tuple[str, ...]:
        for fact_name, fact_values in self.facts:
            if fact_name == name:
                return fact_values
        return ()


@dataclass(frozen=True)
class CoreMaterialSet:
    """A validated, immutable collection of code-owned detector facts."""

    version: str
    entries: tuple[CoreMaterialEntry, ...]

    def entry(self, material_id: str) -> CoreMaterialEntry:
        for entry in self.entries:
            if entry.material_id == material_id:
                return entry
        raise KeyError(f"unknown core material {material_id}")


def material_terms(materials: CoreMaterialSet, material_id: str) -> tuple[str, ...]:
    """Return a material's explicit term tuple without exposing mutable state."""

    return material_values(materials, material_id, "terms")


def material_values(
    materials: CoreMaterialSet, material_id: str, fact_name: str,
) -> tuple[str, ...]:
    """Return one named immutable fact from a material entry."""

    return materials.entry(material_id).values(fact_name)


def validate_core_material_set(materials: CoreMaterialSet) -> tuple[str, ...]:
    """Return deterministic validation errors for a proposed material set."""

    errors: list[str] = []
    if not isinstance(materials.version, str) or not materials.version.strip():
        errors.append("core material version is empty")

    seen_ids: set[str] = set()
    category_counts: dict[str, int] = {}
    for entry in materials.entries:
        if _MATERIAL_ID_PATTERN.fullmatch(entry.material_id) is None:
            errors.append(f"invalid material id {entry.material_id!r}")
        elif entry.material_id in seen_ids:
            errors.append(f"duplicate material id {entry.material_id}")
        seen_ids.add(entry.material_id)
        if entry.category not in _ALLOWED_CATEGORIES:
            errors.append(f"{entry.material_id} has invalid category {entry.category!r}")
        category_counts[entry.category] = category_counts.get(entry.category, 0) + 1
        if entry.source_kind not in _ALLOWED_SOURCE_KINDS:
            errors.append(
                f"{entry.material_id} has invalid source kind {entry.source_kind!r}"
            )
        if not isinstance(entry.introduced_in, str) or not entry.introduced_in.strip():
            errors.append(f"{entry.material_id} has no introduction version")
        if not isinstance(entry.purpose, str) or not entry.purpose.strip():
            errors.append(f"{entry.material_id} has no purpose")
        if not isinstance(entry.test_id, str) or not entry.test_id.startswith("test_"):
            errors.append(f"{entry.material_id} has invalid test id {entry.test_id!r}")
        fact_names: set[str] = set()
        if not entry.facts:
            errors.append(f"{entry.material_id} has no facts")
        for name, values in entry.facts:
            if _FACT_NAME_PATTERN.fullmatch(name) is None:
                errors.append(f"{entry.material_id} has invalid fact name {name!r}")
            elif name in fact_names:
                errors.append(f"{entry.material_id} repeats fact name {name}")
            fact_names.add(name)
            if not values or any(not isinstance(value, str) or not value for value in values):
                errors.append(f"{entry.material_id}.{name} has invalid values")
    for category, count in category_counts.items():
        if count > MAX_ENTRIES_PER_CATEGORY:
            errors.append(f"{category} exceeds {MAX_ENTRIES_PER_CATEGORY} entries")
    if _serialized_size(materials) > MAX_SERIALIZED_BYTES:
        errors.append(f"core material set exceeds {MAX_SERIALIZED_BYTES} bytes")
    return tuple(errors)


def build_core_material_set(
    version: str, entries: tuple[CoreMaterialEntry, ...],
) -> CoreMaterialSet:
    """Construct a set only when all audit and size constraints are satisfied."""

    materials = CoreMaterialSet(version=version, entries=tuple(entries))
    errors = validate_core_material_set(materials)
    if errors:
        raise ValueError("invalid core material set: " + "; ".join(errors))
    return materials


def _serialized_size(materials: CoreMaterialSet) -> int:
    canonical = {
        "version": materials.version,
        "entries": [
            {
                "material_id": entry.material_id,
                "category": entry.category,
                "introduced_in": entry.introduced_in,
                "source_kind": entry.source_kind,
                "purpose": entry.purpose,
                "test_id": entry.test_id,
                "facts": [[name, list(values)] for name, values in entry.facts],
            }
            for entry in materials.entries
        ],
    }
    return len(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode())


CORE_MATERIALS = build_core_material_set(
    "core-materials-v5",
    (
        CoreMaterialEntry(
            "intent_override_operation",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Locate operations that ask to override existing control content.",
            "test_instruction_override_requires_operation_and_protected_target",
            (("terms", ("ignore", "bypass", "discard", "disable", "forget", "忽略", "绕过", "废弃", "关闭", "忘记")),),
        ),
        CoreMaterialEntry(
            "intent_protected_target",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Identify instruction-like control content in an intent relation.",
            "test_instruction_override_requires_operation_and_protected_target",
            (("terms", ("instruction", "rule", "prompt", "policy", "system", "指令", "规则", "提示词", "系统")),),
        ),
        CoreMaterialEntry(
            "intent_reveal_operation",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Locate requests to expose protected control content.",
            "test_instruction_override_requires_operation_and_protected_target",
            (("terms", ("reveal", "show", "expose", "泄露", "展示", "公开")),),
        ),
        CoreMaterialEntry(
            "intent_authority_claim",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Recognize authority assertions that can strengthen confirmed intent.",
            "test_instruction_override_requires_operation_and_protected_target",
            (("terms", ("administrator", "admin", "highest authority", "管理员", "最高权限")),),
        ),
        CoreMaterialEntry(
            "intent_role_reassignment",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Recognize role reassignment that can strengthen confirmed intent.",
            "test_instruction_override_requires_operation_and_protected_target",
            (("terms", ("you are now", "become", "act as", "你现在是", "改为", "扮演")),),
        ),
        CoreMaterialEntry(
            "intent_protected_reference",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Require an explicit reference to existing protected control content.",
            "test_instruction_override_does_not_block_generic_product_documentation",
            (("terms", ("your", "previous", "prior", "above", "hidden", "internal", "private", "secret", "你的", "此前", "之前", "上文", "隐藏", "内部", "私密")),),
        ),
        CoreMaterialEntry(
            "intent_override_scope",
            "intent_slot",
            "core-materials-v1",
            "first_party_design",
            "Qualify a confirmed override relationship without standing alone.",
            "test_instruction_override_does_not_block_generic_product_documentation",
            (("terms", ("all", "every", "全部", "所有")),),
        ),
        CoreMaterialEntry(
            "protocol_role_header",
            "protocol",
            "core-materials-v2",
            "first_party_design",
            "Describe the reserved role names and optional header suffix.",
            "test_role_marker_protocol_facts_preserve_current_boundaries",
            (
                ("role_names", ("system", "developer", "assistant", "tool", "function", "系统", "开发者", "助手", "工具")),
                ("optional_suffixes", (" message",)),
            ),
        ),
        CoreMaterialEntry(
            "protocol_message_envelope",
            "protocol",
            "core-materials-v2",
            "first_party_design",
            "Describe the minimum serialized message envelope relationship.",
            "test_role_marker_protocol_facts_preserve_current_boundaries",
            (
                ("role_fields", ("role",)),
                ("content_fields", ("content",)),
                ("weak_role_values", ("system", "developer", "assistant", "tool")),
                ("strong_role_values", ("system", "developer")),
            ),
        ),
        CoreMaterialEntry(
            "protocol_tool_envelope",
            "protocol",
            "core-materials-v2",
            "first_party_design",
            "Describe the current tool-call envelope fields without payload values.",
            "test_role_marker_protocol_facts_preserve_current_boundaries",
            (
                ("call_fields", ("function_call", "tool_call", "tool_use")),
                ("weak_argument_fields", ("arguments", "parameters", "name")),
                ("strong_call_fields", ("function_call",)),
                ("strong_nonempty_string_fields", ("name",)),
                ("strong_presence_fields", ("arguments",)),
            ),
        ),
        CoreMaterialEntry(
            "protocol_chatml_envelope",
            "protocol",
            "core-materials-v2",
            "first_party_design",
            "Describe the current reserved delimiter and ChatML header structure.",
            "test_role_marker_protocol_facts_preserve_current_boundaries",
            (
                ("start_delimiters", ("<|im_start|>",)),
                ("strong_role_values", ("system", "developer", "tool")),
                ("open_delimiters", ("<|", "<<")),
                ("close_delimiters", ("|>", ">>")),
            ),
        ),
        CoreMaterialEntry(
            "operation_external_fetch",
            "operation_grammar",
            "core-materials-v3",
            "first_party_design",
            "Locate explicit actions that request a nearby external resource.",
            "test_external_fetch_materials_preserve_current_boundaries",
            (
                ("terms", ("fetch", "retrieve", "download", "load", "read", "open", "import", "获取", "抓取", "下载", "读取", "加载", "打开", "导入")),
            ),
        ),
        CoreMaterialEntry(
            "operation_external_transfer",
            "operation_grammar",
            "core-materials-v3",
            "first_party_design",
            "Locate explicit actions that transfer content to a nearby resource.",
            "test_external_fetch_materials_preserve_current_boundaries",
            (
                ("terms", ("send", "upload", "post", "forward", "exfiltrate", "发送", "上传", "转发", "外传")),
            ),
        ),
        CoreMaterialEntry(
            "operation_external_prompt_target",
            "operation_grammar",
            "core-materials-v3",
            "first_party_design",
            "Identify prompt-like targets in an established fetch relationship.",
            "test_external_fetch_materials_preserve_current_boundaries",
            (
                ("terms", ("prompt", "instruction", "system prompt", "提示词", "指令", "系统提示")),
            ),
        ),
        CoreMaterialEntry(
            "operation_http_fetch_execute",
            "operation_grammar",
            "core-materials-v3",
            "first_party_design",
            "Describe the current HTTP fetch-to-interpreter command relationship.",
            "test_external_fetch_materials_preserve_current_boundaries",
            (
                ("schemes", ("http", "https")),
                ("fetch_commands", ("curl", "wget", "invoke-webrequest", "iwr")),
                ("interpreters", ("sh", "bash", "zsh", "python", "python3", "pwsh", "powershell", "iex")),
            ),
        ),
        CoreMaterialEntry(
            "encoding_base64_candidate",
            "encoding_format",
            "core-materials-v4",
            "public_standard",
            "Describe the accepted Base64 alphabet and URL-safe decoder variant.",
            "test_encoded_payload_materials_preserve_current_boundaries",
            (
                ("alphabet_extras", ("+", "/", "_", "-")),
                ("padding_chars", ("=",)),
                ("decoder_altchars", ("-", "_")),
            ),
        ),
        CoreMaterialEntry(
            "encoding_percent_escape",
            "encoding_format",
            "core-materials-v4",
            "public_standard",
            "Describe a percent-prefixed hexadecimal escape unit.",
            "test_encoded_payload_materials_preserve_current_boundaries",
            (
                ("prefixes", ("%",)),
                ("hex_widths", ("2",)),
            ),
        ),
        CoreMaterialEntry(
            "encoding_unicode_escape",
            "encoding_format",
            "core-materials-v4",
            "public_standard",
            "Describe the supported short and long Unicode escape units.",
            "test_encoded_payload_materials_preserve_current_boundaries",
            (
                ("short_prefixes", ("\\u",)),
                ("short_hex_widths", ("4",)),
                ("long_prefixes", ("\\U",)),
                ("long_hex_widths", ("8",)),
            ),
        ),
        CoreMaterialEntry(
            "encoding_hex_bytes",
            "encoding_format",
            "core-materials-v4",
            "public_standard",
            "Describe the byte-pair prefix and separators accepted by the parser.",
            "test_encoded_payload_materials_preserve_current_boundaries",
            (
                ("optional_prefixes", ("0x",)),
                ("byte_hex_widths", ("2",)),
                ("separators", ("whitespace", ",", ":", "-")),
            ),
        ),
        CoreMaterialEntry(
            "encoding_rot13_wrapper",
            "encoding_format",
            "core-materials-v4",
            "public_standard",
            "Describe the explicit ROT13 label and supported wrapper punctuation.",
            "test_encoded_payload_materials_preserve_current_boundaries",
            (
                ("labels", ("rot13",)),
                ("colon_wrappers", (":",)),
                ("open_wrappers", ("(",)),
                ("close_wrappers", (")",)),
            ),
        ),
        CoreMaterialEntry(
            "encoding_unicode_format_controls",
            "encoding_format",
            "core-materials-v4",
            "public_standard",
            "Identify Unicode general categories counted as format controls.",
            "test_encoded_payload_materials_preserve_current_boundaries",
            (
                ("unicode_categories", ("Cf",)),
            ),
        ),
        CoreMaterialEntry(
            "runtime_python_traceback",
            "runtime_artifact",
            "core-materials-v5",
            "public_standard",
            "Describe the canonical Python traceback header, frame label, and exception terminators.",
            "test_metadata_leakage_materials_preserve_current_boundaries",
            (
                ("headers", ("Traceback (most recent call last):",)),
                ("header_prefixes", ("traceback",)),
                ("frame_labels", ("File",)),
                ("exception_suffixes", ("Error", "Exception", "Exit")),
                ("exception_names", ("KeyboardInterrupt",)),
            ),
        ),
        CoreMaterialEntry(
            "runtime_tool_call_envelope",
            "runtime_artifact",
            "core-materials-v5",
            "first_party_design",
            "Describe closed JSON relationships that represent a callable tool or function envelope.",
            "test_metadata_leakage_materials_preserve_current_boundaries",
            (
                ("method_fields", ("method",)),
                ("parameter_fields", ("params",)),
                ("name_fields", ("name",)),
                ("argument_fields", ("arguments", "args")),
                ("function_fields", ("function",)),
                ("tool_calls_fields", ("tool_calls",)),
            ),
        ),
        CoreMaterialEntry(
            "runtime_error_envelope",
            "runtime_artifact",
            "core-materials-v5",
            "first_party_design",
            "Describe the bounded error-object and textual-error relationships used for generation-failure detection.",
            "test_poor_quality_error_envelope_materials_preserve_current_boundaries",
            (
                ("object_error_fields", ("error",)),
                ("object_structure_fields", ("code", "status", "type")),
                ("header_labels", ("error", "exception", "错误")),
                ("http_error_hundreds", ("4", "5")),
                ("exception_suffixes", ("Error", "Exception")),
            ),
        ),
    ),
)
