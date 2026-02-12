import tempfile
import unittest
from pathlib import Path

from src.youtrack_gauge_orchestrator import select_relevant_specs, tokenize


class OrchestratorTests(unittest.TestCase):
    def test_tokenize_filters_short_tokens(self):
        toks = tokenize("Bu bir login checkout testidir")
        self.assertIn("login", toks)
        self.assertNotIn("bu", toks)

    def test_select_relevant_specs_returns_matching_spec(self):
        issue = {"summary": "ürün arama", "description": "kullanıcı elbise arar"}
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "search.spec"
            p2 = Path(td) / "checkout.spec"
            p1.write_text("Arama kutusuna elbise yazılır", encoding="utf-8")
            p2.write_text("ödeme formu doldurulur", encoding="utf-8")

            result = select_relevant_specs(issue, [p1, p2])
            self.assertEqual(result[0].name, "search.spec")


if __name__ == "__main__":
    unittest.main()
