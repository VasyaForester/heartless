"""The recovery table and the one-writer rule, proven instead of asserted.

Grok's review (2026-11-15) asked for exactly this: kill the driver in `prepared`,
`submitted` and `awaiting_judge` and see `execution_failed`, `submission_uncertain`
and a PRESERVED judge wait — plus the guarantee that re-running a lane cannot send a
second attempt over a live arena (the lease).

Why it matters: these three states are the only window in which a crash can leave the
arena and the journal disagreeing.  A silent reset would destroy a submission that may
already have reached the judge; a missing reset would freeze the lane.
"""

import os
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import attempts as attempts_mod  # noqa: E402
import store  # noqa: E402

LANE = "test-lane"


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name) / "t.db"
        self.conn = store.connect(self.db)
        self.lease = store.acquire_lease(self.conn, LANE, "target-1")
        self.assertTrue(self.lease, "the test needs the lane lease")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES('s|m','board','s','m')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _attempt(self, aid: str, state: str):
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,state) VALUES(?,?,?,?,?,?,?,?)",
            (aid, "s|m", "board", "s", "m", LANE, 0.0, state))
        self.conn.commit()

    def _state(self, aid: str) -> str:
        return self.conn.execute("SELECT state FROM attempts WHERE attempt_id=?",
                                 (aid,)).fetchone()["state"]

    def test_the_three_open_states_recover_exactly_as_documented(self):
        self._attempt("a-prepared", "prepared")
        self._attempt("a-submitted", "submitted")
        self._attempt("a-awaiting", "awaiting_judge")
        out = attempts_mod.recover(self.conn, self.lease)
        got = {r["attempt_id"]: r["to"] for r in out}
        self.assertEqual(got["a-prepared"], "execution_failed")
        self.assertEqual(got["a-submitted"], "submission_uncertain")
        self.assertTrue(got["a-awaiting"].startswith("awaiting_judge"),
                        "the judge wait must be PRESERVED, not reset")
        self.assertEqual(self._state("a-prepared"), "execution_failed")
        self.assertEqual(self._state("a-submitted"), "submission_uncertain")
        self.assertEqual(self._state("a-awaiting"), "awaiting_judge")

    def test_the_execution_status_says_what_happened(self):
        self._attempt("a-prepared", "prepared")
        self._attempt("a-submitted", "submitted")
        attempts_mod.recover(self.conn, self.lease)
        rows = {r["attempt_id"]: r["execution_status"] for r in self.conn.execute(
            "SELECT attempt_id, execution_status FROM attempts")}
        self.assertEqual(rows["a-prepared"], "failed")
        self.assertEqual(rows["a-submitted"], "uncertain")

    def test_recovery_is_visible_in_the_attempt_history(self):
        self._attempt("a-submitted", "submitted")
        attempts_mod.recover(self.conn, self.lease)
        kinds = [r["kind"] for r in self.conn.execute(
            "SELECT kind FROM attempt_events WHERE attempt_id='a-submitted'")]
        self.assertIn("transition", kinds)
        payloads = [r["payload"] for r in self.conn.execute(
            "SELECT payload FROM attempt_events WHERE attempt_id='a-submitted'")]
        self.assertTrue(any("do not resubmit" in (p or "") for p in payloads),
                        "the reason must be in the record, not only in a log")

    def test_a_finished_attempt_is_untouched(self):
        self._attempt("a-done", "finalized")
        attempts_mod.recover(self.conn, self.lease)
        self.assertEqual(self._state("a-done"), "finalized")

    def test_a_second_lane_run_cannot_own_the_same_lane(self):
        """Axis-10: re-running the same lane must not send a second attempt over a
        live arena.  The lease is what stops it, and the lease is atomic."""
        other = store.acquire_lease(self.conn, LANE, "target-1", pid=os.getpid() + 1)
        self.assertIsNone(other, "a live lease must not be handed to a second worker")
        # ... and the same process renewing its own lease is fine
        renewed = store.acquire_lease(self.conn, LANE, "target-1")
        self.assertIsNotNone(renewed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
