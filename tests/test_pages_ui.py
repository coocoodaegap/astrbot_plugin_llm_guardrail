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
        self.assertIn('id="rule-editor"', html)
        self.assertIn('id="new-rule"', html)
        self.assertIn('id="rule-description"', html)
        self.assertIn('id="save-rule-library"', html)
        self.assertIn('apiGet("get_rule_library")', javascript)
        self.assertIn('"save_rule_library"', javascript)
        self.assertIn("expected_revision: currentRevision", javascript)
        self.assertIn("function switchTab", javascript)
        self.assertIn("function renderRuleList", javascript)
        self.assertIn('ruleTemplate.disabled = true', javascript)
        self.assertIn("仅记录命中，不改变请求或输出（observe）", javascript)
        self.assertIn('id="system-settings"', html)
        self.assertIn('id="save-system-settings"', html)
        self.assertIn('apiGet("get_system_settings")', javascript)
        self.assertIn('"save_system_settings"', javascript)
        self.assertIn("function collectSystemSettings", javascript)
        self.assertIn("function createUmoTagEditor", javascript)
        self.assertIn("umo-tag-editor", javascript)
        self.assertIn("function createProviderSelector", javascript)
        self.assertIn("手动填写", javascript)
        self.assertIn("function describeSystemSettingOption", javascript)
        self.assertIn("function describeSystemSettingHint", javascript)
        self.assertIn("规则命中风险时采用的默认处理方式", javascript)
        self.assertIn("所有群聊进入 Guardrail", javascript)


if __name__ == "__main__":
    unittest.main()
