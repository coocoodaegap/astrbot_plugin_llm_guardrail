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
    PolicyComponent,
    PolicyRuleBinding,
    RuleDefinition,
    compile_policy_to_runtime_config,
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
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "safe_input",
                    "Safe Input",
                    bindings=(
                        PolicyRuleBinding(
                            rule_id="risk_words",
                            rail="input_rail",
                            priority=10,
                            action_on_hit="sanitize",
                            inspection_template="${event_origin}",
                        ),
                    ),
                ),
            ),
            active_policy_id="safe_input",
        )

        raw, validation = compile_policy_to_runtime_config(
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
        self.assertEqual(rule.config["inspection_template"], "${event_origin}")
        self.assertNotIn("inspection_template", library.rules[0].template_config)

    def test_rule_can_be_reused_by_different_policies(self):
        rule = RuleDefinition(
            rule_id="review",
            template_key="plain_keywords",
            template_config={"keywords": ["review"]},
        )
        library = PolicyLibrary(
            rules=(rule,),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
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

        observed, first_validation = compile_policy_to_runtime_config(
            {}, library, "observe_policy"
        )
        blocked, second_validation = compile_policy_to_runtime_config(
            {}, library, "block_policy"
        )

        self.assertTrue(first_validation.valid)
        self.assertTrue(second_validation.valid)
        self.assertEqual(observed["input_rail"]["rule_list"][0]["action_on_hit"], "observe")
        self.assertEqual(blocked["request_rail"]["rule_list"][0]["action_on_hit"], "block")

    def test_policy_step_settings_override_system_rail_settings(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "custom",
                    "Custom",
                    rail_settings={
                        "input_rail": {
                            "enabled": False,
                            "max_text_chars": 120,
                            "default_action_on_hit": "observe",
                        }
                    },
                ),
            ),
            active_policy_id="custom",
        )

        raw, validation = compile_policy_to_runtime_config(
            {"input_rail": {"max_text_chars": 6000}}, library
        )
        config = normalize_config(raw)

        self.assertTrue(validation.valid)
        self.assertFalse(config.rails["input_rail"].enabled)
        self.assertEqual(config.rails["input_rail"].settings["max_text_chars"], 120)
        self.assertEqual(config.rails["input_rail"].settings["default_action_on_hit"], "observe")

    def test_umo_override_uses_first_usable_policy_then_default(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "broken",
                    "Broken",
                    bindings=(PolicyRuleBinding("missing", "input_rail"),),
                    umo_list=("umo:shared",),
                ),
                PolicyDefinition("first", "First", umo_list=("umo:shared",)),
                PolicyDefinition("second", "Second", umo_list=("umo:shared",)),
                PolicyDefinition("fallback", "Fallback"),
            ),
            active_policy_id="fallback",
        )

        self.assertEqual(library.select_usable_policy_for_umo("umo:shared").policy_id, "first")
        self.assertEqual(library.select_usable_policy_for_umo("umo:other").policy_id, "fallback")

    def test_explicit_umo_selection_overrides_membership_and_round_trips(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("matched", "Matched", umo_list=("umo:one",)),
                PolicyDefinition("manual", "Manual"),
            ),
            active_policy_id="matched",
            umo_policy_selections=(("umo:one", "manual"),),
        )

        resolution = library.resolve_usable_policy_for_umo("umo:one")
        restored = PolicyLibrary.from_dict(library.to_dict())

        self.assertEqual(resolution.policy.policy_id, "manual")
        self.assertEqual(resolution.source, "explicit")
        self.assertEqual(restored.explicit_policy_id_for_umo("umo:one"), "manual")

    def test_unusable_explicit_selection_only_falls_back_to_matching_umo_policy(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("matched", "Matched", umo_list=("umo:one",)),
                PolicyDefinition("global", "Global"),
            ),
            active_policy_id="global",
            umo_policy_selections=(
                ("umo:one", "deleted_policy"),
                ("umo:two", "deleted_policy"),
            ),
        )

        matching = library.resolve_usable_policy_for_umo("umo:one")
        no_match = library.resolve_usable_policy_for_umo("umo:two")

        self.assertEqual(matching.policy.policy_id, "matched")
        self.assertEqual(matching.source, "explicit_fallback_umo_list")
        self.assertIsNone(no_match.policy)
        self.assertEqual(no_match.source, "explicit_fallback_system")
        self.assertEqual(no_match.explicit_policy_id, "deleted_policy")

    def test_missing_rule_binding_is_fatal(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "broken",
                    "Broken",
                    bindings=(PolicyRuleBinding("missing", "input_rail"),),
                ),
            ),
            active_policy_id="broken",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("references missing rule missing", validation.fatal_errors[0])

    def test_known_template_cannot_be_bound_to_an_unsupported_step(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("strengthen", "strengthen_prompt", {}),),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "invalid_step",
                    "Invalid step",
                    bindings=(PolicyRuleBinding("strengthen", "input_rail"),),
                ),
            ),
            active_policy_id="invalid_step",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("Step 1", validation.fatal_errors[0])

    def test_sanitize_is_rejected_for_policy_component(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "invalid_action",
                    "Invalid action",
                    components=(
                        PolicyComponent(
                            "gate",
                            "logic_gate",
                            "input_rail",
                            action_on_hit="sanitize",
                            config={"inputs": ["source"]},
                        ),
                    ),
                ),
            ),
            active_policy_id="invalid_action",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertFalse(validation.valid)
        self.assertTrue(any("only available" in error for error in validation.fatal_errors))

    def test_rule_library_rejects_invalid_default_sanitize_without_a_binding(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("review", "llm_review", {}, default_action_on_hit="sanitize"),),
            policies=(PolicyDefinition("_default", "Default", builtin=True),),
            active_policy_id="_default",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("only available", validation.fatal_errors[0])

    def test_retry_generation_warns_outside_step_five_without_rejecting_rule(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("retry", "plain_keywords", {"keywords": ["retry"]}, default_action_on_hit="retry_generation"),),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "early_retry",
                    "Early retry",
                    bindings=(PolicyRuleBinding("retry", "input_rail"),),
                ),
            ),
            active_policy_id="early_retry",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        self.assertTrue(any("outside Step 5" in warning for warning in validation.warnings))

    def test_retry_generation_error_action_always_warns(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("retry", "plain_keywords", {"keywords": ["retry"]}, default_action_on_error="retry_generation"),),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "early_retry",
                    "Early retry",
                    bindings=(PolicyRuleBinding("retry", "input_rail"),),
                ),
            ),
            active_policy_id="early_retry",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        self.assertTrue(any("uses retry_generation as its error action" in warning for warning in validation.warnings))

    def test_unsupported_legacy_template_is_preserved_as_warning(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("future_rule", "future_detector", {}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "future",
                    "Future",
                    bindings=(PolicyRuleBinding("future_rule", "input_rail"),),
                ),
            ),
            active_policy_id="future",
        )

        raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        self.assertTrue(validation.warnings)
        self.assertEqual(raw["input_rail"]["rule_list"][0]["__template_key"], "future_detector")

    def test_template_specific_threshold_is_not_a_rule_or_policy_default(self):
        rule = RuleDefinition(
            "keywords",
            "plain_keywords",
            {"keywords": ["secret"], "threshold": 3},
        )
        binding = PolicyRuleBinding("keywords", "input_rail")

        self.assertNotIn("default_threshold", rule.to_dict())
        self.assertNotIn("threshold", binding.to_dict())
        compiled = compile_policy_to_runtime_config(
            {},
            PolicyLibrary(
                rules=(rule,),
                policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                    PolicyDefinition("active", "Active", bindings=(binding,)),
                ),
                active_policy_id="active",
            ),
        )[0]
        self.assertEqual(compiled["input_rail"]["rule_list"][0]["threshold"], 3)

    def test_policy_rejects_dependency_on_a_later_step(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("early", "plain_keywords", {"keywords": ["early"]}),
                RuleDefinition("late", "plain_keywords", {"keywords": ["late"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "invalid_order",
                    "Invalid order",
                    bindings=(
                        PolicyRuleBinding("early", "input_rail", depend_on="late"),
                        PolicyRuleBinding("late", "request_rail"),
                    ),
                ),
            ),
            active_policy_id="invalid_order",
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertTrue(any("cannot depend on late in later Step 3" in error for error in validation.fatal_errors))

    def test_policy_rejects_cyclic_dependencies(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("first", "plain_keywords", {"keywords": ["first"]}),
                RuleDefinition("second", "plain_keywords", {"keywords": ["second"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "cycle",
                    "Cycle",
                    bindings=(
                        PolicyRuleBinding("first", "input_rail", depend_on="second"),
                        PolicyRuleBinding("second", "input_rail", depend_on="first"),
                    ),
                ),
            ),
            active_policy_id="cycle",
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertTrue(any("has cyclic dependency" in error for error in validation.fatal_errors))

    def test_policy_rejects_dependency_on_disabled_node(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("source", "plain_keywords", {"keywords": ["source"]}),
                RuleDefinition("dependent", "plain_keywords", {"keywords": ["dependent"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "disabled_dependency",
                    "Disabled dependency",
                    bindings=(
                        PolicyRuleBinding("source", "input_rail", enabled=False),
                        PolicyRuleBinding("dependent", "request_rail", depend_on="source"),
                    ),
                ),
            ),
            active_policy_id="disabled_dependency",
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertTrue(any("references disabled node source" in error for error in validation.fatal_errors))

    def test_logic_gate_inputs_obey_policy_dependency_step_order(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition("source", "plain_keywords", {"keywords": ["source"]}),
            ),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "invalid_gate_order",
                    "Invalid gate order",
                    bindings=(
                        PolicyRuleBinding("source", "request_rail"),
                    ),
                    components=(
                        PolicyComponent("gate", "logic_gate", "input_rail", config={"inputs": ["source"]}),
                    ),
                ),
            ),
            active_policy_id="invalid_gate_order",
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertTrue(any("gate in Step 1 cannot depend on source in later Step 3" in error for error in validation.fatal_errors))

    def test_logic_gate_payload_input_references_its_source_node(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("source", "plain_keywords", {"keywords": ["source"]}),),
            policies=(
                PolicyDefinition(
                    "with_payload_gate",
                    "With payload gate",
                    bindings=(PolicyRuleBinding("source", "input_rail"),),
                    components=(
                        PolicyComponent(
                            "gate",
                            "logic_gate",
                            "input_rail",
                            config={"inputs": ["source.sanitized?"]},
                        ),
                    ),
                ),
            ),
            active_policy_id="with_payload_gate",
        )

        self.assertTrue(library.validate().valid)

    def test_logic_gate_rejects_malformed_payload_input(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("source", "plain_keywords", {"keywords": ["source"]}),),
            policies=(
                PolicyDefinition(
                    "bad_payload_gate",
                    "Bad payload gate",
                    bindings=(PolicyRuleBinding("source", "input_rail"),),
                    components=(
                        PolicyComponent(
                            "gate",
                            "logic_gate",
                            "input_rail",
                            config={"inputs": ["source.", "source?"]},
                        ),
                    ),
                ),
            ),
            active_policy_id="bad_payload_gate",
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertTrue(any("invalid logic gate input" in error for error in validation.fatal_errors))

    def test_policy_component_compiles_as_runtime_logic_gate(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("source", "plain_keywords", {"keywords": ["source"]}),),
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "with_gate",
                    "With gate",
                    bindings=(PolicyRuleBinding("source", "input_rail"),),
                    components=(
                        PolicyComponent(
                            "gate",
                            "logic_gate",
                            "input_rail",
                            priority=110,
                            config={"gate": "all", "invert": False, "inputs": ["source"]},
                        ),
                    ),
                    node_order=("source", "gate"),
                ),
            ),
            active_policy_id="with_gate",
        )

        raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        compiled_gate = raw["input_rail"]["rule_list"][1]
        self.assertEqual(compiled_gate["__template_key"], "logic_gate")
        self.assertEqual(compiled_gate["rule_id"], "gate")
        self.assertEqual(compiled_gate["inputs"], ["source"])

    def test_rule_library_rejects_component_types(self):
        library = PolicyLibrary(
            rules=(RuleDefinition("gate", "logic_gate", {}),),
            policies=(PolicyDefinition("_default", "Default", builtin=True),),
            active_policy_id="_default",
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertTrue(any("components may only be stored" in error for error in validation.fatal_errors))


if __name__ == "__main__":
    unittest.main()
