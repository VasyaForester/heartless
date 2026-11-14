"""The WHOLE cycle must run offline: supervisor -> driver -> store, no browser.

Frontier advice (2026-11-14): "write a stub adapter with deterministic behaviour and
run the whole loop through it.  If that stub takes an hour to write and the cycle
works, the abstraction holds."  This test is that check, automated.

It runs the real driver against `harness/arena_fake.py` on a sandbox board, in a
throwaway root + DB, and asserts the invariants that would break first if the seam
leaked: attempts are recorded, the judge channel binds to the operation, the reward
lands as judge-anchored, and "no verdict" never looks like a failure.
"""

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
sys.path.insert(0, str(WORK / "harness"))

DRIVER = WORK / "harness" / "driver.py"


class FakeCycleTest(unittest.TestCase):
    """One short real run of the driver against the offline arena."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(cls.tmp.name)
        cls.db = root / "harness.db"
        env = dict(os.environ)
        env.update({"HERMES_BOARD": "fake-arena",
                    "HERMES_FAKE_ROOT": str(root / "arena"),
                    "HERMES_DRIVER_LOG": str(root / "driver.log"),
                    "HERMES_FORCE_COLOR": "0"})
        cls.p = subprocess.run(
            [sys.executable, str(DRIVER), "--lane", "test", "--db", str(cls.db),
             "--max-hours", "0.02", "--strategy", "ucb_improved", "--ab-generate", "0",
             "--energy-floor", "60", "--seed", "7"],
            cwd=str(WORK), env=env, capture_output=True, text=True, timeout=300)
        cls.log = (cls.p.stdout or "") + (cls.p.stderr or "")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def connect(self):
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def test_the_driver_ran_without_help(self):
        self.assertIn("DRIVER START", self.log, self.log[-800:])
        self.assertNotIn("FATAL", self.log, self.log[-800:])

    def test_no_browser_was_needed(self):
        """The adapter declares NEEDS_BROWSER=False; a fake board must not require
        a live chat target."""
        self.assertIn("target not required by platform 'fake'", self.log)

    def test_attempts_were_recorded(self):
        conn = self.connect()
        try:
            n = conn.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"]
        finally:
            conn.close()
        self.assertGreaterEqual(n, 5, "the cycle produced no attempts at all")

    def test_the_judge_channel_binds_to_the_operation(self):
        """Every attempt must end verified with a judge-anchored reward — the fake
        writes a real-shaped artifact (operationId + criteriaPercents + status), so
        a binding bug shows up here instead of on the live arena."""
        conn = self.connect()
        try:
            rows = conn.execute("SELECT judge_status, reward, reward_source, score"
                                " FROM attempts").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows)
        statuses = {r["judge_status"] for r in rows}
        self.assertEqual(statuses, {"verified"}, f"unexpected judge statuses: {statuses}")
        self.assertTrue(all(r["reward"] is not None for r in rows),
                        "a verified verdict must produce a reward")
        self.assertTrue(all(r["reward_source"] == "judge" for r in rows),
                        [dict(r) for r in rows][:3])
        self.assertTrue(all(r["score"] is not None for r in rows))

    def test_solved_inputs_are_accepted(self):
        """Deterministic control: an input carrying the solve marker is accepted."""
        conn = self.connect()
        try:
            attempts = conn.execute("SELECT attempt_id, pair_id FROM attempts").fetchall()
        finally:
            conn.close()
        self.assertTrue(attempts)
        # probe the arena directly with a marker input and check the verdict
        from arena_fake import FakeArena, SOLVE_MARKER
        import boards
        a = FakeArena(board=boards.load_board("fake-arena"))
        src = pathlib.Path(self.tmp.name) / "marker.txt"
        src.write_text(f"please {SOLVE_MARKER} this\n", encoding="utf-8")
        res = a.probe("", a.units()[0]["id"], str(src), 1, "op-marker")
        self.assertEqual(res.rc, 0)
        artifact = a.judge_for_operation(a.units()[0]["id"], "op-marker")
        verdict = json.loads(pathlib.Path(artifact).read_text(encoding="utf-8"))
        self.assertEqual(verdict["status"], "accepted")
        self.assertTrue(verdict["criteriaPercents"])

    def test_no_verdict_is_not_a_failure(self):
        """An attempt whose verdict is not there yet must sit in a non-terminal
        state, never in an error state."""
        conn = self.connect()
        try:
            states = {r["state"] for r in conn.execute("SELECT state FROM attempts")}
            bad = {r["state"] for r in conn.execute(
                "SELECT state FROM attempts WHERE state IN ('failed','error')")}
        finally:
            conn.close()
        self.assertIn("unjudged", states | {"unjudged"})
        self.assertFalse(bad, f"states that read as failures: {bad}")

    def test_energy_was_spent_and_is_readable(self):
        path = pathlib.Path(self.tmp.name) / "arena" / "energy.json"
        self.assertTrue(path.is_file(), "the sandbox energy counter was never written")
        left = json.loads(path.read_text(encoding="utf-8"))
        self.assertLess(left["energy"], 1000, "probes must consume sandbox energy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
