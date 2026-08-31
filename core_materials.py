"""Versioned, code-owned facts used by local detector implementations.

The core material set is intentionally small.  It records protocol and intent
facts needed by deterministic structural checks; it is not a configurable
keyword list, a RAG corpus, or a standalone risk decision engine.
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
}
_ALLOWED_SOURCE_KINDS = {
    "public_standard",
    "first_party_observation",
    "first_party_design",
}
MAX_ENTRIES_PER_CATEGORY = 64
MAX_SERIALIZED_BYTES = 32 * 1024


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

    return materials.entry(material_id).values("terms")


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
    "core-materials-v1",
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
    ),
)
