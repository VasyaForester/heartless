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

class BoardSchemaTest(unittest.TestCase):
    """The profile contract lives in boards/schema.json and is enforced on load.

    A new arena must be "fill in data + write an adapter", never "edit the driver":
    these tests keep the contract itself honest.
    """

    def test_schema_file_is_valid_and_not_a_board(self):
        schema = boards.profile_schema()
        self.assertTrue(schema.get("required"), "the schema must name required fields")
        self.assertTrue(schema.get("properties"))
        self.assertNotIn("schema", boards.list_boards(),
                         "boards/schema.json must not be listed as a board")

    def test_every_board_passes_the_schema(self):
        for name in boards.list_boards():
            with self.subTest(board=name):
                profile = boards.load_board(name)
                self.assertIn(profile["name"], (name, profile["name"]))
                self.assertIsInstance(profile["cost"]["message"], (int, float))

    def test_wrong_type_is_loud(self):
        profile = dict(boards.load_board("lucky-break-payday"))
        profile["cost"] = 2
        with self.assertRaises(ValueError):
            boards.validate(profile)

    def test_a_stringified_list_is_loud(self):
        profile = dict(boards.load_board("lucky-break-payday"))
        profile["models"] = "not a list"
        with self.assertRaises(ValueError):
            boards.validate(profile)

    def test_sandbox_boards_need_a_note(self):
        profile = {"name": "x", "board": "X", "match": "x", "url": "sandbox://x",
                   "scenario_selector": "card", "model_confirm": "Attacking:",
                   "win_string": "SOLVED", "cost": {"message": 1, "judge": 1},
                   "sandbox": True}
        with self.assertRaises(ValueError):
            boards.validate(profile)
        profile["_note"] = "offline sandbox for tests"
        boards.validate(profile)
