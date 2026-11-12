import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import attempts  # noqa: E402
import store  # noqa: E402


class AttemptsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(Path(self.tmp.name) / "h.db")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES('s|m','lucky-break-payday','s','m')")
        self.conn.commit()
        self.lease = store.acquire_lease(self.conn, "test", "tab", pid=os.getpid())

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def alloc(self, aid):
        store.insert_attempt(self.conn, self.lease, {
            "attempt_id": aid, "pair_id": "s|m", "board_profile": "lucky-break-payday",
            "scenario": "s", "model": "m", "lane": "test", "started_at": time.time(),
        })
        attempts.prepare(self.conn, self.lease, aid, input_text="hello",
                         input_path="inputs/x.txt", delta="append_nonce",
                         delta_version=1, nonce="n1")
        return aid

    def test_recover_prepared(self):
        aid = self.alloc("a-prepared")
        out = attempts.recover(self.conn, self.lease)
        self.assertEqual(out[0]["to"], "execution_failed")
        row = store.get_attempt(self.conn, aid)
        self.assertEqual(row["state"], "execution_failed")

    def test_recover_submitted_is_uncertain(self):
        aid = self.alloc("a-submitted")
        attempts.mark_submitted(self.conn, self.lease, aid, transcript_text="hello")
        out = attempts.recover(self.conn, self.lease)
        self.assertEqual(out[0]["to"], "submission_uncertain")
        row = store.get_attempt(self.conn, aid)
        self.assertEqual(row["state"], "submission_uncertain")

    def test_recover_awaiting_is_kept(self):
        aid = self.alloc("a-awaiting")
        attempts.mark_submitted(self.conn, self.lease, aid, transcript_text="hello")
        attempts.mark_awaiting(self.conn, self.lease, aid, judge_ref="j.json")
        out = attempts.recover(self.conn, self.lease)
        self.assertEqual(out[0]["to"], "awaiting_judge (kept)")
        row = store.get_attempt(self.conn, aid)
        self.assertEqual(row["state"], "awaiting_judge")

    def test_uncertain_does_not_duplicate(self):
        aid = self.alloc("a-uncertain")
        attempts.mark_submitted(self.conn, self.lease, aid, transcript_text="hello")
        attempts.mark_uncertain(self.conn, self.lease, aid, "timeout")
        row = store.get_attempt(self.conn, aid)
        self.assertEqual(row["state"], "submission_uncertain")
        with self.assertRaises(store.InvalidTransition):
            attempts.mark_submitted(self.conn, self.lease, aid, transcript_text="hello")


if __name__ == "__main__":
    unittest.main()