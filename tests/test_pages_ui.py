import unittest
from pathlib import Path


PAGES_DIR = Path(__file__).resolve().parents[1] / "pages" / "guardrail"


class GuardrailPagesUiTests(unittest.TestCase):
    def test_rule_and_policy_editors_use_separate_revisioned_apis(self):
        html = (PAGES_DIR / "index.html").read_text(encoding="utf-8")
        javascript = (PAGES_DIR / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="rule-library"', html)
        self.assertIn('id="save-rule-library"', html)
        self.assertIn('id="policy-library"', html)
        self.assertIn('id="save-policy-library"', html)
        self.assertIn('apiGet("get_rule_library")', javascript)
        self.assertIn('apiGet("get_policy_library")', javascript)
        self.assertIn('"save_rule_library"', javascript)
        self.assertIn('"save_policy_library"', javascript)
        self.assertIn("expected_revision: currentRevision", javascript)


if __name__ == "__main__":
    unittest.main()
