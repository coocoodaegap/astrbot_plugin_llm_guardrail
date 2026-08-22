import sys
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from config import normalize_config
from policy_library import (
    PolicyDefinition,
    PolicyLibrary,
    PolicyRuleBinding,
    RuleDefinition,
    compile_policy_to_legacy_config,
    import_legacy_rule_list,
)


class PolicyLibraryTests(unittest.TestCase):
    def test_rule_description_is_serialized_without_affecting_runtime_config(self):
        rule = RuleDefinition(
            rule_id="risk_words",
            template_key="plain_keywords",
            description="拦截敏感词",
            template_config={"keywords": ["secret"]},
        )

        restored = RuleDefinition.from_dict(rule.to_dict())

        self.assertEqual(restored.description, "拦截敏感词")
        self.assertNotIn("description", restored.template_config)

    def test_legacy_hit_action_aliases_are_canonicalized_in_new_library_data(self):
        rule = RuleDefinition.from_dict(
            {
                "rule_id": "legacy",
                "template_key": "plain_keywords",
                "default_action_on_hit": "sanitize_input",
            }
        )
        binding = PolicyRuleBinding.from_dict(
            {"rule_id": "legacy", "rail": "output_rail", "action_on_hit": "sanitize_output"}
        )

        self.assertEqual(rule.to_dict()["default_action_on_hit"], "sanitize")
        self.assertEqual(binding.to_dict()["action_on_hit"], "sanitize")

    def test_policy_compiles_rule_defaults_and_binding_overrides(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition(
                    rule_id="risk_words",
                    template_key="plain_keywords",
                    template_config={
                        "keywords": ["secret"],
                        "sanitizer": "[redacted]",
                        "threshold": 2,
                    },
                    default_priority=100,
                    default_action_on_hit="block",
                    default_action_on_error="record",
                ),
            ),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "safe_input",
                    "Safe Input",
                    bindings=(
                        PolicyRuleBinding(
                            rule_id="risk_words",
                            rail="input_rail",
                            priority=10,
                            action_on_hit="sanitize",
                        ),
                    ),
                ),
            ),
            active_policy_id="safe_input",
        )

        raw, validation = compile_policy_to_legacy_config(
            {"input_rail": {"max_text_chars": 123}}, library
        )
        normalized = normalize_config(raw)
        rule = normalized.rails["input_rail"].rules[0]

        self.assertTrue(validation.valid)
        self.assertEqual(raw["input_rail"]["max_text_chars"], 123)
        self.assertEqual(rule.priority, 10)
        self.assertEqual(rule.config["action_on_hit"], "sanitize")
        self.assertEqual(rule.config["threshold"], 2.0)
        self.assertEqual(rule.config["action_on_error"], "record")

    def test_rule_can_be_reused_by_different_policies(self):
        rule = RuleDefinition(
            rule_id="review",
            template_key="plain_keywords",
            template_config={"keywords": ["review"]},
        )
        library = PolicyLibrary(
            rules=(rule,),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "observe_policy",
                    "Observe",
                    bindings=(
                        PolicyRuleBinding("review", "input_rail", action_on_hit="observe"),
                    ),
                ),
                PolicyDefinition(
                    "block_policy",
                    "Block",
                    bindings=(
                        PolicyRuleBinding("review", "request_rail", action_on_hit="block"),
                    ),
                ),
            ),
            active_policy_id="observe_policy",
        )

        observed, first_validation = compile_policy_to_legacy_config(
            {}, library, "observe_policy"
        )
        blocked, second_validation = compile_policy_to_legacy_config(
            {}, library, "block_policy"
        )

        self.assertTrue(first_validation.valid)
        self.assertTrue(second_validation.valid)
        self.assertEqual(observed["input_rail"]["rule_list"][0]["action_on_hit"], "observe")
        self.assertEqual(blocked["request_rail"]["rule_list"][0]["action_on_hit"], "block")

    def test_imports_legacy_rule_list_without_runtime_metadata(self):
        legacy = {
            "input_rail": {
                "rule_list": [
                    {
                        "__template_key": "regex_pattern",
                        "rule_id": "legacy_regex",
                        "pattern": "secret",
                        "priority": 5,
                        "action_on_hit": "block",
                        "_compiled_pattern": "must_not_persist",
                    }
                ]
            }
        }

        library, diagnostics = import_legacy_rule_list(legacy)
        raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertEqual(diagnostics, [])
        self.assertTrue(validation.valid)
        self.assertEqual(library.active_policy_id, "legacy_import")
        self.assertNotIn("_compiled_pattern", library.rules[0].template_config)
        self.assertEqual(raw["input_rail"]["rule_list"][0]["pattern"], "secret")

    def test_missing_rule_binding_is_fatal(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "broken",
                    "Broken",
                    bindings=(PolicyRuleBinding("missing", "input_rail"),),
                ),
            ),
            active_policy_id="broken",
        )

        _raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("references missing rule missing", validation.fatal_errors[0])

    def test_known_template_cannot_be_bound_to_an_unsupported_step(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("replace", "replace_input", {}),),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "invalid_step",
                    "Invalid step",
                    bindings=(PolicyRuleBinding("replace", "input_rail"),),
                ),
            ),
            active_policy_id="invalid_step",
        )

        _raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("Step 1", validation.fatal_errors[0])

    def test_sanitize_is_rejected_for_non_matching_rule_templates(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("gate", "logic_gate", {}),),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "invalid_action",
                    "Invalid action",
                    bindings=(PolicyRuleBinding("gate", "input_rail", action_on_hit="sanitize"),),
                ),
            ),
            active_policy_id="invalid_action",
        )

        _raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("only available", validation.fatal_errors[0])

    def test_rule_library_rejects_invalid_default_sanitize_without_a_binding(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("review", "llm_review", {}, default_action_on_hit="sanitize"),),
            policies=(PolicyDefinition("none", "None", builtin=True),),
            active_policy_id="none",
        )

        _raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("only available", validation.fatal_errors[0])

    def test_retry_generation_warns_outside_step_five_without_rejecting_rule(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("retry", "plain_keywords", {"keywords": ["retry"]}, default_action_on_hit="retry_generation"),),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "early_retry",
                    "Early retry",
                    bindings=(PolicyRuleBinding("retry", "input_rail"),),
                ),
            ),
            active_policy_id="early_retry",
        )

        _raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertTrue(validation.valid)
        self.assertTrue(any("outside Step 5" in warning for warning in validation.warnings))

    def test_retry_generation_error_action_warns_outside_step_five(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("retry", "plain_keywords", {"keywords": ["retry"]}, default_action_on_error="retry_generation"),),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "early_retry",
                    "Early retry",
                    bindings=(PolicyRuleBinding("retry", "input_rail"),),
                ),
            ),
            active_policy_id="early_retry",
        )

        _raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertTrue(validation.valid)
        self.assertTrue(any("error action outside Step 5" in warning for warning in validation.warnings))

    def test_unsupported_legacy_template_is_preserved_as_warning(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("future_rule", "preset_encoded_payload", {}),
            ),
            policies=(
                PolicyDefinition("none", "None", builtin=True),
                PolicyDefinition(
                    "future",
                    "Future",
                    bindings=(PolicyRuleBinding("future_rule", "input_rail"),),
                ),
            ),
            active_policy_id="future",
        )

        raw, validation = compile_policy_to_legacy_config({}, library)

        self.assertTrue(validation.valid)
        self.assertTrue(validation.warnings)
        self.assertEqual(raw["input_rail"]["rule_list"][0]["__template_key"], "preset_encoded_payload")

    def test_template_specific_threshold_is_not_a_rule_or_policy_default(self):
        rule = RuleDefinition(
            "keywords",
            "plain_keywords",
            {"keywords": ["secret"], "threshold": 3},
        )
        binding = PolicyRuleBinding("keywords", "input_rail")

        self.assertNotIn("default_threshold", rule.to_dict())
        self.assertNotIn("threshold", binding.to_dict())
        compiled = compile_policy_to_legacy_config(
            {},
            PolicyLibrary(
                rules=(rule,),
                policies=(
                    PolicyDefinition("none", "None", builtin=True),
                    PolicyDefinition("active", "Active", bindings=(binding,)),
                ),
                active_policy_id="active",
            ),
        )[0]
        self.assertEqual(compiled["input_rail"]["rule_list"][0]["threshold"], 3)


if __name__ == "__main__":
    unittest.main()
