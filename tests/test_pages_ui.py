import unittest
from pathlib import Path


PAGES_DIR = Path(__file__).resolve().parents[1] / "pages" / "guardrail"


class GuardrailPagesUiTests(unittest.TestCase):
    def test_pages_use_documented_tabs_and_visual_rule_editor(self):
        html = (PAGES_DIR / "index.html").read_text(encoding="utf-8")
        javascript = (PAGES_DIR / "app.js").read_text(encoding="utf-8")

        for label in (
            "总览", "规则库", "策略编排", "访问控制", "知识库经验",
            "会话策略监控", "Token 监控", "系统设置",
        ):
            self.assertIn(label, html)
        self.assertIn('id="rule-list"', html)
        self.assertIn('id="open-rule-editors"', html)
        self.assertIn('id="save-rule-as-dialog"', html)
        self.assertIn('id="cancel-save-rule-as"', html)
        self.assertIn('id="confirm-rule-delete-dialog"', html)
        self.assertIn('id="new-rule"', html)
        self.assertIn('id="rule-creation-dialog"', html)
        self.assertIn('id="rule-library-panel"', html)
        self.assertIn('id="template-options"', html)
        self.assertIn('id="confirm-rule-creation"', html)
        self.assertIn('id="rule-creation-status"', html)
        self.assertIn('id="save-as-rule-status" class="form-status"', html)
        self.assertIn('id="confirm-rule-delete-message" class="danger-notice"', html)
        self.assertIn(".form-status", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn('id="open-rule-editors"', html)
        self.assertNotIn('id="rule-id"', html)
        self.assertNotIn('id="rule-template"', html)
        self.assertIn('id="save-rule-library"', html)
        self.assertIn('apiGet("get_rule_library")', javascript)
        self.assertIn('"save_rule_library"', javascript)
        self.assertIn("expected_revision: currentRevision", javascript)
        self.assertIn("function switchTab", javascript)
        self.assertIn("function renderRuleList", javascript)
        self.assertIn("function hitActionsForTemplate", javascript)
        self.assertIn('action !== "sanitize"', javascript)
        self.assertIn("function createRuleFieldHint", javascript)
        self.assertIn("function createTemplateParameterForm", javascript)
        self.assertIn("function collectTemplateConfig", javascript)
        self.assertIn("templateParameterFields", javascript)
        self.assertNotIn('JSON.parse(editor.querySelector("textarea").value)', javascript)
        for template_key in (
            "plain_keywords", "regex_pattern", "rag_judge",
            "llm_review", "replace_input", "strengthen_prompt", "route_policy",
        ):
            self.assertIn(template_key, javascript)
        rule_template_block = javascript.split("const templates =", 1)[1].split("hitActions", 1)[0]
        self.assertNotIn('"logic_gate"', rule_template_block)
        self.assertIn(".rule-field-hint", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn(".template-parameters", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn(".setting-checkbox:checked", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn("function startRuleCreation", javascript)
        self.assertIn("ruleCreationStatus", javascript)
        self.assertIn('id="rule-creation-dialog"', html)
        self.assertIn("ruleCreationDialog.showModal()", javascript)
        self.assertIn("function renderTemplateOptions", javascript)
        self.assertIn("function openRule", javascript)
        self.assertIn("function openSaveAsDialog", javascript)
        self.assertIn("function saveRuleAs", javascript)
        self.assertIn("function closeRuleEditor", javascript)
        self.assertIn("function saveRuleEditor", javascript)
        self.assertIn("function requestRuleDeletion", javascript)
        self.assertIn("cancelSaveRuleAs.addEventListener", javascript)
        self.assertNotIn("rule.template_key =", javascript)
        self.assertIn("仅记录命中，不改变请求或输出（observe）", javascript)
        self.assertIn('plain_keywords: "关键词匹配"', javascript)
        self.assertIn('id="system-settings"', html)
        self.assertIn('id="policy-list-panel"', html)
        self.assertIn('id="policy-detail-panel"', html)
        self.assertIn('id="policy-list"', html)
        self.assertIn('class="default-policy-card"', html)
        self.assertIn('id="custom-policy-list-heading"', html)
        self.assertNotIn('id="policy-bindings-json"', html)
        self.assertIn('id="policy-name-input"', html)
        self.assertIn('id="policy-description-input"', html)
        self.assertIn('id="policy-graph-canvas"', html)
        self.assertIn('id="policy-graph-step-toggles"', html)
        self.assertIn('id="save-policy"', html)
        self.assertNotIn('id="save-policy-details"', html)
        self.assertIn('id="policy-graph-editor"', html)
        self.assertIn('id="policy-graph-editor-status"', html)
        self.assertNotIn('id="policy-step-settings"', html)
        self.assertNotIn("规则绑定（JSON）", html)
        self.assertIn('id="new-policy"', html)
        self.assertIn('id="create-policy-dialog"', html)
        self.assertIn('id="save-policy-as-dialog"', html)
        self.assertIn('id="confirm-policy-delete-dialog"', html)
        self.assertIn('id="policy-umo-list"', html)
        self.assertIn('id="set-default-policy"', html)
        self.assertIn('id="default-policy-indicator"', html)
        self.assertIn('id="default-policy-summary"', html)
        self.assertIn('取消默认规则', javascript)
        self.assertIn('clearDefault', javascript)
        self.assertIn('clearDefaultPolicyFromList', javascript)
        self.assertNotIn('id="save-policy-session"', html)
        self.assertNotIn('id="policy-detail-bindings"', html)
        self.assertIn('id="back-to-policy-list"', html)
        self.assertIn('id="save-system-settings"', html)
        self.assertIn('id="access-platform-id"', html)
        self.assertIn('id="access-record-list"', html)
        self.assertIn('id="save-access-decision"', html)
        self.assertIn('apiGet("get_system_settings")', javascript)
        self.assertIn('apiGet("get_access_control_records")', javascript)
        self.assertIn('"set_access_control_decision"', javascript)
        self.assertIn('"clear_access_control_decision"', javascript)
        self.assertIn('apiGet("get_policy_library")', javascript)
        self.assertIn('"save_system_settings"', javascript)
        self.assertIn("function collectSystemSettings", javascript)
        self.assertIn("function createUmoTagEditor", javascript)
        self.assertIn("umo-tag-editor", javascript)
        self.assertIn("function createProviderSelector", javascript)
        self.assertIn("手动填写", javascript)
        self.assertIn("function describeSystemSettingOption", javascript)
        self.assertIn("function describeSystemSettingHint", javascript)
        self.assertIn("function refreshAccessControl", javascript)
        self.assertIn("expected_record_revision", javascript)
        self.assertIn("accessRefreshEpoch", javascript)
        self.assertIn("accessPlatformId.disabled = true", javascript)
        self.assertIn("accessSenderId.disabled = true", javascript)
        self.assertIn("accessPlatformId.disabled = false", javascript)
        self.assertIn("accessSenderId.disabled = false", javascript)
        self.assertIn("主体标识已锁定", javascript)
        self.assertIn(".access-form-grid input:disabled", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn("function showPolicyList", javascript)
        self.assertIn("function showPolicyDetail", javascript)
        self.assertIn("function renderPolicyList", javascript)
        self.assertIn("function renderPolicyDetail", javascript)
        self.assertIn("function buildPolicyGraphModel", javascript)
        self.assertIn("function drawPolicyGraph", javascript)
        self.assertIn("function updatePolicyGraphAnimation", javascript)
        self.assertIn("function policyGraphLaneRanks", javascript)
        self.assertIn("function clampPolicyGraphNodesInLane", javascript)
        self.assertIn("is-step-disabled", javascript)
        self.assertIn("hiddenNodeStates", javascript)
        self.assertIn("function isPolicyGraphNodeVisible", javascript)
        self.assertIn("ResizeObserver", javascript)
        self.assertIn("function renderPolicyGraphEditor", javascript)
        self.assertIn("function renderPolicyGraphNodeEditor", javascript)
        self.assertIn("function renderPolicyGraphStepEditor", javascript)
        self.assertIn("function availableRulesForPolicyRail", javascript)
        self.assertIn("function addSelectedPolicyRules", javascript)
        self.assertIn("supportedTemplatesByRail", javascript)
        self.assertIn("function renderPolicyRuleBusinessSummary", javascript)
        self.assertIn('node.state === "unavailable"', javascript)
        self.assertIn("dirtyNodeIds", javascript)
        self.assertIn("node.isDirty || selected", javascript)
        self.assertIn("function policyGraphRailAt", javascript)
        self.assertIn("function beginPolicyDependencySelection", javascript)
        self.assertIn("function policyGraphDependencyCandidates", javascript)
        self.assertIn("function requestPolicyBindingRemoval", javascript)
        self.assertIn("function removePolicyBinding", javascript)
        self.assertIn("function showPolicySaveIssues", javascript)
        self.assertIn("策略暂不能另存为", javascript)
        self.assertIn('id="policy-dependency-mode-dialog"', html)
        self.assertIn('id="policy-rule-picker-dialog"', html)
        self.assertIn('id="policy-component-creation-dialog"', html)
        self.assertIn('id="confirm-policy-binding-remove-dialog"', html)
        self.assertIn('id="policy-save-issues-dialog"', html)
        self.assertNotIn("syncPolicyBindingsJson", javascript)
        self.assertIn("function saveCurrentPolicy", javascript)
        self.assertIn("function createPolicy", javascript)
        self.assertIn("componentDefinitions", javascript)
        self.assertIn("function openPolicyComponentCreation", javascript)
        self.assertIn("function createPolicyComponent", javascript)
        self.assertIn("function updatePolicyComponentConfig", javascript)
        for field_name in (
            "duplicate_line_min_chars",
            "duplicate_line_min_count",
            "min_invisible_chars",
            "max_invisible_ratio",
            "max_lines",
            "detect_log_like_headers",
            "detect_role_reassignment",
            "contains_request_user_id",
            "contains_at_user_id",
            "contains_forward",
            "contains_file",
            "contains_image",
            "contains_record",
            "contains_video",
            "contains_link",
            "user_ids",
        ):
            self.assertIn(field_name, javascript)
        self.assertIn('defaultAction: "observe"', javascript)
        self.assertIn('else if (field.type === "list")', javascript)
        self.assertIn("findPolicyGraphDraftNode", javascript)
        self.assertIn("function savePolicyAsCopy", javascript)
        self.assertIn("function deleteSelectedPolicy", javascript)
        self.assertIn("function saveCurrentPolicy", javascript)
        self.assertNotIn("data-policy-bindings-rail", javascript)
        self.assertNotIn("json-editor", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn('apiPost("save_policy_library"', javascript)
        self.assertIn("function customPolicies() { return policyLibrary.policies; }", javascript)
        self.assertIn("规则命中风险时采用的默认处理方式", javascript)
        self.assertIn("所有群聊进入 Guardrail", javascript)
        for element_id in (
            "session-policy-list-panel",
            "session-policy-detail-panel",
            "session-policy-state-query",
            "refresh-session-policy-states",
            "session-policy-state-list",
            "session-policy-result-summary",
            "session-policy-signal-list",
            "session-policy-route-candidate",
            "session-policy-request-observation",
            "session-policy-target-comparison",
            "session-policy-activity-list",
            "back-to-session-policy-list",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('apiGet("get_session_policy_states"', javascript)
        self.assertIn('apiGet("get_session_policy_state"', javascript)
        self.assertIn("function renderSessionPolicyStateDetail", javascript)
        self.assertIn("function renderSessionPolicySignals", javascript)
        self.assertIn("function sessionPolicyRailOutcomeLabel", javascript)
        self.assertIn("function showSessionPolicyStateDetail", javascript)
        self.assertIn("late_policy_stage_observed", javascript)
        self.assertIn('requestTarget.source === "unavailable"', javascript)
        self.assertIn('return "未观察到目标"', javascript)
        self.assertNotIn("context_current_chat_provider_id", javascript)
        self.assertIn("策略未显式约束模型，因此未比较模型", javascript)
        self.assertIn("观察模式，未参与执行", html)
        self.assertNotIn('apiPost("clear_session_policy', javascript)
        stylesheet = (PAGES_DIR / "style.css").read_text(encoding="utf-8")
        self.assertIn(".session-policy-layout", stylesheet)
        self.assertIn(".session-policy-detail-panel[hidden]", stylesheet)
        self.assertIn("display: none !important", stylesheet)
        self.assertIn("function setSessionPolicyStateView(showDetail)", javascript)
        self.assertIn('sessionPolicyListPanel.style.display = showDetail ? "none" : "grid";', javascript)
        self.assertIn('sessionPolicyDetailPanel.style.display = showDetail ? "grid" : "none";', javascript)
        session_switch_start = javascript.index("function switchTab")
        session_switch_end = javascript.index("\nfunction addSummary", session_switch_start)
        session_list_reset = javascript.index("showSessionPolicyStateList();", session_switch_start)
        self.assertLess(session_list_reset, session_switch_end)
        session_list_view = javascript.split("function showSessionPolicyStateList", 1)[1].split(
            "async function showSessionPolicyStateDetail", 1
        )[0]
        session_detail_view = javascript.split("async function showSessionPolicyStateDetail", 1)[1].split(
            "try {", 1
        )[0]
        self.assertIn("setSessionPolicyStateView(false);", session_list_view)
        self.assertIn("setSessionPolicyStateView(true);", session_detail_view)


if __name__ == "__main__":
    unittest.main()
