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
    rename_policy_node,
)


class PolicyLibraryTests(unittest.TestCase):
    def test_binding_id_is_canonical_with_legacy_identity_fallbacks(self):
        rule_binding = PolicyRuleBinding.from_dict(
            {"rule_id": "shared_rule", "rail": "input_rail"}
        )
        component = PolicyComponent.from_dict(
            {
                "component_id": "legacy_gate",
                "component_type": "logic_gate",
                "rail": "input_rail",
            }
        )

        self.assertEqual(rule_binding.node_id, "shared_rule")
        self.assertEqual(rule_binding.to_dict()["binding_id"], "shared_rule")
        self.assertEqual(component.node_id, "legacy_gate")
        self.assertEqual(component.to_dict()["binding_id"], "legacy_gate")
        self.assertEqual(component.to_dict()["component_id"], "legacy_gate")

    def test_component_rejects_conflicting_binding_and_legacy_ids(self):
        library = PolicyLibrary(
            policies=(
                PolicyDefinition(
                    "policy",
                    "Policy",
                    components=(
                        PolicyComponent.from_dict(
                            {
                                "binding_id": "canonical",
                                "component_id": "legacy",
                                "component_type": "random_signal",
                                "rail": "input_rail",
                            }
                        ),
                    ),
                ),
            )
        )

        validation = library.validate()

        self.assertFalse(validation.valid)
        self.assertIn("does not match legacy component_id", validation.fatal_errors[0])

    def test_same_rule_can_have_multiple_policy_bindings(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition(
                    "shared_rule",
                    "plain_keywords",
                    {"keywords": ["risk"]},
                ),
            ),
            policies=(
                PolicyDefinition(
                    "policy",
                    "Policy",
                    bindings=(
                        PolicyRuleBinding(
                            "shared_rule", "input_rail", binding_id="first_check"
                        ),
                        PolicyRuleBinding(
                            "shared_rule", "input_rail", binding_id="second_check"
                        ),
                    ),
                    node_order=("first_check", "second_check"),
                ),
            ),
            active_policy_id="policy",
        )

        raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertTrue(validation.valid)
        self.assertEqual(
            [item["rule_id"] for item in raw["input_rail"]["rule_list"]],
            ["first_check", "second_check"],
        )
        self.assertEqual(
            [item["source_rule_id"] for item in raw["input_rail"]["rule_list"]],
            ["shared_rule", "shared_rule"],
        )

    def test_rename_policy_node_updates_all_structured_references(self):
        policy = PolicyDefinition(
            "policy",
            "Policy",
            bindings=(
                PolicyRuleBinding(
                    "shared_rule",
                    "input_rail",
                    binding_id="source",
                    inspection_template="${source.value} ${sourceful.value}",
                ),
                PolicyRuleBinding(
                    "shared_rule",
                    "request_rail",
                    binding_id="consumer",
                    depend_on="?source",
                    inspection_template="${ source.matched_text }",
                ),
            ),
            components=(
                PolicyComponent(
                    "gate",
                    "logic_gate",
                    "request_rail",
                    config={"inputs": ["!source.value?", "consumer"]},
                    binding_id="gate",
                ),
                PolicyComponent(
                    "echo",
                    "sensitive_echo_detector",
                    "output_rail",
                    depend_on="?gate",
                    config={
                        "skip_source_node_ids": ["source", "consumer"],
                        "template": "${source.value}",
                    },
                    binding_id="echo",
                ),
            ),
            node_order=("source", "consumer", "gate", "echo"),
            rail_settings={
                "request_rail": {"output_redirect_template": "${source.sanitized}"}
            },
        )

        renamed = rename_policy_node(policy, "source", "source_2")

        self.assertEqual(renamed.bindings[0].rule_id, "shared_rule")
        self.assertEqual(renamed.bindings[0].node_id, "source_2")
        self.assertEqual(
            renamed.bindings[0].inspection_template,
            "${source_2.value} ${sourceful.value}",
        )
        self.assertEqual(renamed.bindings[1].depend_on, "?source_2")
        self.assertEqual(
            renamed.bindings[1].inspection_template, "${ source_2.matched_text }"
        )
        self.assertEqual(
            renamed.components[0].config["inputs"],
            ["!source_2.value?", "consumer"],
        )
        self.assertEqual(
            renamed.components[1].config["skip_source_node_ids"],
            ["source_2", "consumer"],
        )
        self.assertEqual(renamed.components[1].config["template"], "${source_2.value}")
        self.assertEqual(
            renamed.rail_settings["request_rail"]["output_redirect_template"],
            "${source_2.sanitized}",
        )
        self.assertEqual(
            renamed.node_order, ("source_2", "consumer", "gate", "echo")
        )

        renamed_component = rename_policy_node(renamed, "gate", "gate_2")

        self.assertEqual(renamed_component.components[0].binding_id, "gate_2")
        self.assertEqual(renamed_component.components[0].component_id, "gate_2")
        self.assertEqual(renamed_component.components[1].depend_on, "?gate_2")
        self.assertEqual(
            renamed_component.node_order,
            ("source_2", "consumer", "gate_2", "echo"),
        )

    def test_rename_policy_node_rejects_collisions_without_mutating_source(self):
        policy = PolicyDefinition(
            "policy",
            "Policy",
            bindings=(
                PolicyRuleBinding("first", "input_rail"),
                PolicyRuleBinding("second", "input_rail"),
            ),
            node_order=("first", "second"),
        )

        with self.assertRaisesRegex(ValueError, "already contains node second"):
            rename_policy_node(policy, "first", "second")

        self.assertEqual(policy.node_order, ("first", "second"))

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

    def test_policy_load_preserves_replacement_text_and_falls_back_actions(self):
        rule = RuleDefinition.from_dict(
            {
                "rule_id": "risk",
                "template_key": "plain_keywords",
                "template_config": {"keywords": ["secret"], "sanitizer": "[x]"},
                "default_action_on_hit": "sanitize",
                "default_action_on_error": "unknown_action",
            }
        )
        binding = PolicyRuleBinding.from_dict(
            {"rule_id": "risk", "rail": "input_rail", "action_on_hit": "sanitize"}
        )

        self.assertEqual(rule.template_config["sanitizer"], "[x]")
        self.assertEqual(rule.default_action_on_hit, "observe")
        self.assertEqual(rule.default_action_on_error, "discard")
        self.assertEqual(binding.action_on_hit, "observe")

    def test_policy_compiles_rule_defaults_and_binding_overrides(self):
        library = PolicyLibrary(
            rules=(
                RuleDefinition(
                    rule_id="risk_words",
                    template_key="plain_keywords",
                    template_config={
                        "keywords": ["secret"],
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
                            action_on_hit="observe",
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
        self.assertEqual(rule.config["action_on_hit"], "observe")
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
            policies=(
                PolicyDefinition("_default", "Default", builtin=True),
                PolicyDefinition(
                    "invalid_step",
                    "Invalid step",
                    components=(
                        PolicyComponent(
                            "strengthen",
                            "strengthen_prompt",
                            "input_rail",
                        ),
                    ),
                ),
            ),
            active_policy_id="invalid_step",
        )

        _raw, validation = compile_policy_to_runtime_config({}, library)

        self.assertFalse(validation.valid)
        self.assertIn("Step 1", validation.fatal_errors[0])

    def test_legacy_strengthen_rule_is_inlined_as_step_four_component(self):
        library = PolicyLibrary.from_dict(
            {
                "rules": [
                    {
                        "rule_id": "strengthen",
                        "template_key": "strengthen_prompt",
                        "template_config": {
                            "insertion_target": "system_suffix",
                            "insertion_text": "${PROMPT_TEXT}",
                        },
                        "default_priority": 80,
                    }
                ],
                "policies": [
                    {
                        "policy_id": "legacy",
                        "name": "Legacy",
                        "bindings": [
                            {
                                "rule_id": "strengthen",
                                "rail": "prompt_rail",
                                "priority": 40,
                                "depend_on": "request_check",
                            }
                        ],
                        "node_order": ["request_check", "strengthen"],
                    }
                ],
            }
        )

        self.assertEqual(library.rules, ())
        component = library.policies[0].components[0]
        self.assertEqual(component.component_id, "strengthen")
        self.assertEqual(component.component_type, "strengthen_prompt")
        self.assertEqual(component.rail, "prompt_rail")
        self.assertEqual(component.priority, 40)
        self.assertEqual(component.depend_on, "request_check")
        self.assertEqual(component.config["insertion_text"], "${PROMPT_TEXT}")
        self.assertEqual(library.policies[0].node_order, ("request_check", "strengthen"))

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
