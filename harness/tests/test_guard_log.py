"""A lifted guard must be written down before it authorises anything.

Grok's review (2026-11-15, axis "refusal honesty": 7/10) found the hole: `--force-submit`
could bypass the refusal guard with nothing in the journal — no who, no why, no which
guard.  The axis-10 requirement is a test in which an UNRECORDED lift does not let the
attempt reach the submit.

The rule is fail-closed: `guard_log.lift()` writes the record (guard, reason, who,
when, attempt/opid) into the live journal's `events` table; when that write fails,
`allows_action()` is False and the caller must skip the action.
"""

import argparse
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import guard_log  # noqa: E402
import lbp  # noqa: E402
import store  # noqa: E402


class GuardLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name) / "t.db"
        store.connect(self.db).close()      # create the schema

    def tearDown(self):
        self.tmp.cleanup()

    def lifts(self):
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            return [dict(zip(("ts", "payload"), r)) for r in conn.execute(
                "SELECT ts, payload FROM events WHERE kind='guard_lifted'")]
        finally:
            conn.close()

    def test_a_lift_is_recorded_with_who_why_and_which_guard(self):
        rec = guard_log.lift("refusal_guard", reason="judge asked for the raw fixture",
                             actor="tester", attempt_id="att-1", opid="op-9", db=self.db)
        self.assertTrue(rec["recorded"])
        self.assertTrue(guard_log.allows_action(rec))
        rows = self.lifts()
        self.assertEqual(len(rows), 1)
        self.assertIn("refusal_guard", rows[0]["payload"])
        self.assertIn("judge asked for the raw fixture", rows[0]["payload"])
        self.assertIn("tester", rows[0]["payload"])
        self.assertIn("att-1", rows[0]["payload"])

    def test_an_unrecordable_lift_does_not_authorise_anything(self):
        rec = guard_log.lift("refusal_guard", reason="x", db=pathlib.Path("C:/nope/nope.db"))
        self.assertFalse(rec["recorded"])
        self.assertIn("detail", rec)
        self.assertFalse(guard_log.allows_action(rec))
        self.assertFalse(guard_log.allows_action(None))
        self.assertFalse(guard_log.allows_action({}))

    def test_the_submit_path_honours_the_record(self):
        """The attempt reaches the submit ONLY when the lift was written down."""
        a = argparse.Namespace(force_reason="reviewed by hand", force_who="tester")
        run = {"attempt_id": "att-2", "opid": "op-2"}
        real = guard_log.DB_DEFAULT
        try:
            guard_log.DB_DEFAULT = self.db
            self.assertTrue(lbp._record_guard_lift(a, run, "comply"))
            self.assertTrue(run["guard_lifted"]["recorded"])
            # and one where the journal cannot be written at all
            guard_log.DB_DEFAULT = pathlib.Path("C:/nope/nope.db")
            run2 = {"attempt_id": "att-3"}
            self.assertFalse(lbp._record_guard_lift(a, run2, "comply"))
            self.assertFalse(run2["guard_lifted"]["recorded"])
        finally:
            guard_log.DB_DEFAULT = real

    def test_the_missing_reason_is_still_recorded_as_unspecified(self):
        rec = guard_log.lift("refusal_guard", reason="", db=self.db)
        self.assertTrue(rec["recorded"])
        self.assertEqual(rec["reason"], "unspecified")

    def test_the_default_who_comes_from_the_environment(self):
        old = os.environ.get("HERMES_FORCE_WHO")
        os.environ["HERMES_FORCE_WHO"] = "op-from-env"
        try:
            self.assertEqual(guard_log.who(), "op-from-env")
        finally:
            if old is None:
                os.environ.pop("HERMES_FORCE_WHO", None)
            else:
                os.environ["HERMES_FORCE_WHO"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
