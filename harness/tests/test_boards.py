import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import acceptance  # noqa: E402
import boards  # noqa: E402


class BoardsTest(unittest.TestCase):
    def test_payday_profile(self):
        p = boards.load_board("lucky-break-payday")
        self.assertEqual(p["match"], "lucky-break-payday")
        self.assertEqual(p["win_string"], "SCENARIO SOLVED")
        self.assertEqual(len(p["scenario_titles"]), 5)
        self.assertTrue(p["_profile_hash"])

    def test_proving_ground_profile(self):
        p = boards.load_board("proving-ground")
        self.assertEqual(p["scenario_selector"], "behaviorId")
        self.assertEqual(p["win_string"], "Break Successful!")

    def test_payday_matches_live_lbp(self):
        ok, detail = acceptance.check_boards()
        self.assertTrue(ok, detail)

    def test_profile_hash_changes_with_content(self):
        p = boards.load_board("lucky-break-payday")
        q = dict(p)
        q["win_string"] = "OTHER"
        self.assertNotEqual(p["_profile_hash"], boards.hashlib.sha256(
            boards.json.dumps(q, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16])


if __name__ == "__main__":
    unittest.main()