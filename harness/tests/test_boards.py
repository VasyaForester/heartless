import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import os  # noqa: E402
import json  # noqa: E402

import acceptance  # noqa: E402
import arena  # noqa: E402
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

class ThirdBoardTest(unittest.TestCase):
    """Axis-10 of Grok's board-universality item: a third board is ONE JSON file.

    The profile must pass the existing schema check, resolve to an adapter through
    the existing autoload convention, and require no Python change anywhere — and
    the supervisor's state paths must not depend on the board at all.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        # a schema and one existing profile, then a THIRD board added as data
        (self.dir / "schema.json").write_text(
            (boards.BOARD_DIR / "schema.json").read_text(encoding="utf-8"), encoding="utf-8")
        (self.dir / "lucky-break-payday.json").write_text(
            (boards.BOARD_DIR / "lucky-break-payday.json").read_text(encoding="utf-8"),
            encoding="utf-8")
        (self.dir / "third-lab.json").write_text(json.dumps({
            "name": "third-lab", "board": "Third Lab", "match": "third-lab",
            "url": "sandbox://third-lab", "scenario_selector": "card",
            "model_confirm": "Attacking:", "win_string": "SOLVED",
            "cost": {"message": 1, "judge": 1}, "sandbox": True,
            "_note": "test-only profile: proves a new board is data, not code",
            "models": ["Model A"], "platform": "fake",
            "scenario_titles": {"third-scenario": "Third Scenario"},
            "models_by_scenario": {"third-scenario": ["Model A"]},
        }, ensure_ascii=False), encoding="utf-8")
        self._old = (boards.BOARD_DIR, boards.SCHEMA_PATH)
        boards.BOARD_DIR = self.dir
        boards.SCHEMA_PATH = self.dir / "schema.json"
        boards.profile_schema.cache_clear()

    def tearDown(self):
        boards.BOARD_DIR, boards.SCHEMA_PATH = self._old
        boards.profile_schema.cache_clear()
        self.tmp.cleanup()

    def test_one_json_file_is_the_whole_registration(self):
        self.assertIn("third-lab", boards.list_boards())
        profile = boards.load_board("third-lab")          # validates against the schema
        self.assertEqual(profile["name"], "third-lab")
        adapter = arena.get_adapter(profile)               # autoload convention
        self.assertEqual(adapter.name(), "fake")
        units = adapter.units()
        self.assertTrue(units, "a data-only board must yield units")
        self.assertEqual(units[0]["id"], adapter.unit_id("third-scenario", "Model A"))

    def test_the_state_paths_do_not_depend_on_the_board(self):
        import subprocess
        import sys as _sys
        ws = Path(__file__).resolve().parent.parent.parent  # the real workspace
        for lane, want in (("main", "supervisor.lock"), ("demo", "supervisor-demo.lock")):
            env = dict(os.environ, HERMES_LANE=lane, HERMES_BOARD="fake-arena")
            out = subprocess.run(
                [_sys.executable, "-c",
                 "import sys; sys.path.insert(0, 'harness'); import supervisor as s;"
                 " print(s.LOCK.name)"],
                cwd=str(ws), env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(out.stdout.strip(), want, out.stderr[-300:])
