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
        self.assertIn('id="rule-creation-panel"', html)
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
            "plain_keywords", "regex_pattern", "logic_gate", "rag_judge",
            "llm_review", "replace_input", "strengthen_prompt", "route_policy",
        ):
            self.assertIn(template_key, javascript)
        self.assertIn(".rule-field-hint", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn(".template-parameters", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn(".setting-checkbox:checked", (PAGES_DIR / "style.css").read_text(encoding="utf-8"))
        self.assertIn("function startRuleCreation", javascript)
        self.assertIn("ruleCreationStatus", javascript)
        self.assertIn("ruleLibraryPanel.hidden = true", javascript)
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
        self.assertIn('id="back-to-policy-list"', html)
        self.assertIn('id="save-system-settings"', html)
        self.assertIn('apiGet("get_system_settings")', javascript)
        self.assertIn('apiGet("get_policy_library")', javascript)
        self.assertIn('"save_system_settings"', javascript)
        self.assertIn("function collectSystemSettings", javascript)
        self.assertIn("function createUmoTagEditor", javascript)
        self.assertIn("umo-tag-editor", javascript)
        self.assertIn("function createProviderSelector", javascript)
        self.assertIn("手动填写", javascript)
        self.assertIn("function describeSystemSettingOption", javascript)
        self.assertIn("function describeSystemSettingHint", javascript)
        self.assertIn("function showPolicyList", javascript)
        self.assertIn("function showPolicyDetail", javascript)
        self.assertIn("function renderPolicyList", javascript)
        self.assertIn("function renderPolicyDetail", javascript)
        self.assertIn("规则命中风险时采用的默认处理方式", javascript)
        self.assertIn("所有群聊进入 Guardrail", javascript)


if __name__ == "__main__":
    unittest.main()
