import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import source_cards  # noqa: E402


class SourceCardsTest(unittest.TestCase):
    def test_card_has_the_three_answers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Demo repo\n\nWhat it does.\n", encoding="utf-8")
            (repo / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            entry = {"key": "demo", "url": "https://example.test/demo",
                     "path": str(repo), "type": "repo", "status": "cloned"}
            card = source_cards.build_card(entry)
            self.assertIn("canonical: https://example.test/demo", card)
            self.assertIn("what inside:", card)
            self.assertIn("which file to open:", card)
            self.assertIn("what is absent:", card)
            self.assertIn("README.md", card)
            self.assertIn("data.csv", card)

    def test_missing_path_is_explicit(self):
        entry = {"key": "gone", "url": "https://example.test/gone",
                 "path": "/definitely/not/here", "type": "repo", "status": "error"}
        card = source_cards.build_card(entry)
        self.assertIn("local path missing", card)
        self.assertIn("manifest status: error", card)


if __name__ == "__main__":
    unittest.main()