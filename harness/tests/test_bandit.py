import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import attempts  # noqa: E402
import bandit_audit  # noqa: E402
import store  # noqa: E402


class BanditTest(unittest.TestCase):
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

    def alloc(self, aid, input_text="hello"):
        store.insert_attempt(self.conn, self.lease, {
            "attempt_id": aid, "pair_id": "s|m", "board_profile": "lucky-break-payday",
            "scenario": "s", "model": "m", "lane": "test", "started_at": time.time(),
        })
        attempts.prepare(self.conn, self.lease, aid, input_text=input_text,
                         input_path=f"inputs/{aid}.txt", delta="append_nonce",
                         delta_version=1, nonce="n1", strategy_version=2)
        return aid

    def final(self, aid, score=90, input_text="hello"):
        self.alloc(aid, input_text)
        attempts.mark_submitted(self.conn, self.lease, aid, transcript_text=input_text)
        attempts.mark_awaiting(self.conn, self.lease, aid, judge_ref=f"{aid}.json")
        store.record_judge(self.conn, self.lease, aid, f"{aid}.json",
                           status="accepted", score=score, pcts=[score], verified=True)
        store.transition(self.conn, self.lease, aid, "judged",
                         judge_status="verified", score=score, pcts=f"[{score}]",
                         verdict="accepted")
        store.finalize_attempt(self.conn, self.lease, aid, solved=False)

    def test_only_finalized_verified_count(self):
        self.final("a1")
        self.final("a2")
        p = self.alloc("p1")
        attempts.mark_submitted(self.conn, self.lease, p, transcript_text="pending")
        attempts.mark_awaiting(self.conn, self.lease, p, judge_ref="p1.json")
        f = self.alloc("f1")
        attempts.mark_failed(self.conn, self.lease, f, "rc=1")
        result = bandit_audit.audit(self.conn)
        self.assertEqual(result["finalized_verified"], 2)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["total_attempts"], 4)

    def test_duplicates_reported(self):
        self.final("a1")
        self.final("a2")
        result = bandit_audit.audit(self.conn)
        self.assertEqual(result["duplicate_attempts"], 1)

    def test_ucb_replay_is_diagnostic(self):
        self.final("a1")
        self.final("a2")
        result = bandit_audit.ucb_replay(self.conn)
        self.assertEqual(result["steps"], 2)
        self.assertIsNotNone(result["rate"])


if __name__ == "__main__":
    unittest.main()