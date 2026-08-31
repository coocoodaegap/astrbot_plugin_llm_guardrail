import ast
import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from core_materials import (
    CORE_MATERIALS,
    CoreMaterialEntry,
    CoreMaterialSet,
    MAX_ENTRIES_PER_CATEGORY,
    build_core_material_set,
    material_terms,
    material_values,
    validate_core_material_set,
)


class CoreMaterialTests(unittest.TestCase):
    def test_builtin_materials_are_valid_and_immutable(self):
        self.assertEqual(validate_core_material_set(CORE_MATERIALS), ())
        self.assertEqual(CORE_MATERIALS.version, "core-materials-v6")
        self.assertIsInstance(CORE_MATERIALS.entries, tuple)
        self.assertEqual(
            material_terms(CORE_MATERIALS, "intent_override_operation"),
            ("ignore", "bypass", "discard", "disable", "forget", "忽略", "绕过", "废弃", "关闭", "忘记"),
        )
        self.assertEqual(
            material_values(CORE_MATERIALS, "protocol_message_envelope", "role_fields"),
            ("role",),
        )
        self.assertEqual(
            material_values(CORE_MATERIALS, "protocol_chatml_envelope", "start_delimiters"),
            ("<|im_start|>",),
        )
        self.assertEqual(
            material_values(CORE_MATERIALS, "operation_http_fetch_execute", "schemes"),
            ("http", "https"),
        )
        self.assertEqual(
            material_values(CORE_MATERIALS, "encoding_base64_candidate", "padding_chars"),
            ("=",),
        )
        self.assertEqual(
            material_values(
                CORE_MATERIALS,
                "encoding_unicode_format_controls",
                "unicode_categories",
            ),
            ("Cf",),
        )
        self.assertEqual(
            material_values(
                CORE_MATERIALS, "runtime_python_traceback", "frame_labels",
            ),
            ("File",),
        )
        self.assertEqual(
            material_values(
                CORE_MATERIALS, "runtime_error_envelope", "header_labels",
            ),
            ("error", "exception", "错误"),
        )
        self.assertEqual(
            material_values(
                CORE_MATERIALS, "language_target_scripts", "script_classes",
            ),
            ("latin", "han", "japanese", "hangul", "cyrillic", "arabic"),
        )

    def test_builtin_materials_link_to_real_regression_tests(self):
        test_function_ids = {
            node.name
            for path in Path(__file__).parent.glob("test_*.py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig")))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for entry in CORE_MATERIALS.entries:
            with self.subTest(material_id=entry.material_id):
                self.assertIn(entry.test_id, test_function_ids)

    def test_validation_rejects_duplicate_material_ids(self):
        entry = CORE_MATERIALS.entries[0]
        materials = CoreMaterialSet("test-v1", (entry, entry))

        errors = validate_core_material_set(materials)

        self.assertIn("duplicate material id intent_override_operation", errors)

    def test_validation_rejects_entries_without_a_test_identifier(self):
        entry = CoreMaterialEntry(
            "invalid_test_id",
            "intent_slot",
            "test-v1",
            "first_party_design",
            "Exercise validation of a malformed test identifier.",
            "missing_test_name",
            (("terms", ("example",)),),
        )

        with self.assertRaisesRegex(ValueError, "invalid test id"):
            build_core_material_set("test-v1", (entry,))

    def test_validation_requires_an_auditable_purpose(self):
        entry = CoreMaterialEntry(
            "missing_purpose",
            "intent_slot",
            "test-v1",
            "first_party_design",
            "",
            "test_validation_requires_an_auditable_purpose",
            (("terms", ("example",)),),
        )

        with self.assertRaisesRegex(ValueError, "has no purpose"):
            build_core_material_set("test-v1", (entry,))

    def test_validation_enforces_per_category_entry_limit(self):
        entries = tuple(
            CoreMaterialEntry(
                f"slot_{index}",
                "intent_slot",
                "test-v1",
                "first_party_design",
                "Exercise the per-category capacity limit.",
                "test_validation_enforces_per_category_entry_limit",
                (("terms", (f"term_{index}",)),),
            )
            for index in range(MAX_ENTRIES_PER_CATEGORY + 1)
        )

        errors = validate_core_material_set(CoreMaterialSet("test-v1", entries))

        self.assertIn(
            f"intent_slot exceeds {MAX_ENTRIES_PER_CATEGORY} entries", errors
        )


if __name__ == "__main__":
    unittest.main()
