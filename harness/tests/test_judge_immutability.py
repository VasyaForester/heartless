"""The judge artifact is a CACHE; the attempt's recorded binding is the evidence.

Grok's review (2026-11-15, axis "judge reconciliation": 8/10) put it plainly: the
accepted verdict is the row captured with the attempt, and `lbp-*-judge.json` is a
cache — rewriting that file proves nothing.  The axis-10 requirement is a test that
rejects a verdict whose operation id, chat, time or transcript hash disagree with the
attempt.

The mismatch classes themselves are already pinned in test_judge.py (foreign operation
id, foreign chat, stale verdict, duplicate, mismatched transcript hash, no identity at
all).  What this file adds is the layer above them: `driver.apply_verdict()` — a
finished attempt is IMMUTABLE, so a rewritten (or simply better) judge artifact cannot
change its recorded outcome or feed the bandit a second time.
"""

import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import driver  # noqa: E402
import judge_correlation  # noqa: E402
import store  # noqa: E402

PAIR = "scenario|model"


def judge_json(tmp: pathlib.Path, *, opid="opid-1", chat="deadbeef", pcts=(100, 0),
               status="accepted", ts=None) -> pathlib.Path:
    p = tmp / f"lbp-{opid}-judge.json"
    p.write_text(json.dumps({
        "operationId": opid,
        "status": status,
        "criteriaPercents": [{"text": f"Criterion {i + 1}: {v}%"} for i, v in enumerate(pcts)],
        "evidence": [{"text": "judge output"}],
        "submittedAt": ts or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "url": f"https://app.grayswan.ai/arena/chat?chatId={chat}",
    }), encoding="utf-8")
    return p


class ImmutabilityTest(unittest.TestCase):
    """A rewritten judge file cannot change a finished attempt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.db = self.dir / "t.db"
        self.conn = store.connect(self.db)
        self.lease = store.acquire_lease(self.conn, "lane-x", "target")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES(?,?,?,?)",
            (PAIR, driver.BOARD_NAME, "scenario", "model"))
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,state,delta) VALUES('att-1',?,?,?,?,?,?,?,?)",
            (PAIR, driver.BOARD_NAME, "scenario", "model", "lane-x", 0.0, "unjudged", "arm"))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    class _Engine:
        """Minimal engine stand-in: records what it was told, no strategy maths."""

        def __init__(self):
            self.calls = []

        def observe(self, **kw):
            self.calls.append(kw)
            return {"reward": 0.5 if kw.get("judge") else 0.1,
                    "source": "judge" if kw.get("judge") else "local"}

    def test_the_first_verdict_is_kept_and_a_later_rewrite_is_ignored(self):
        engine = self._Engine()
        first = {"status": "verified", "judge_ref": str(judge_json(self.dir)),
                 "operation_id": "opid-1", "chat_id": "deadbeef",
                 "score": 100, "pcts": [100, 0], "verdict": "accepted",
                 "raw_hash": "h1", "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        out1 = driver.apply_verdict(self.conn, self.lease, "att-1", PAIR, "scenario",
                                    "model", "arm", first, {"probe_ok": True}, engine)
        self.assertEqual(out1["outcome"], "verified")
        row = store.get_attempt(self.conn, "att-1")
        self.assertEqual(row["state"], "finalized")
        reward_before, score_before = row["reward"], row["score"]

        # the file gets "improved" afterwards — a rewrite is not evidence
        better = dict(first)
        better.update(judge_ref=str(judge_json(self.dir, pcts=(100, 100), status="solved")),
                      score=200, verdict="solved", raw_hash="h2")
        out2 = driver.apply_verdict(self.conn, self.lease, "att-1", PAIR, "scenario",
                                    "model", "arm", better, {"probe_ok": True}, engine)
        self.assertEqual(out2["outcome"], "immutable")
        self.assertEqual(out2["reward"], reward_before)
        row2 = store.get_attempt(self.conn, "att-1")
        self.assertEqual(row2["reward"], reward_before)
        self.assertEqual(row2["score"], score_before)
        self.assertEqual(row2["state"], "finalized")

    def test_the_engine_is_not_told_about_the_rewrite(self):
        engine = self._Engine()
        first = {"status": "verified", "judge_ref": str(judge_json(self.dir)),
                 "operation_id": "opid-1", "chat_id": "deadbeef", "score": 100,
                 "pcts": [100, 0], "verdict": "accepted", "raw_hash": "h1"}
        driver.apply_verdict(self.conn, self.lease, "att-1", PAIR, "scenario", "model",
                             "arm", first, {"probe_ok": True}, engine)
        calls_after_first = len(engine.calls)
        driver.apply_verdict(self.conn, self.lease, "att-1", PAIR, "scenario", "model",
                             "arm", dict(first, score=999, verdict="solved"),
                             {"probe_ok": True}, engine)
        self.assertEqual(len(engine.calls), calls_after_first,
                         "a cached-file rewrite must not become new evidence for the bandit")


if __name__ == "__main__":
    unittest.main(verbosity=2)

class PendingOutcomeTest(unittest.TestCase):
    """`pending` stays an UNKNOWN outcome (Grok review 2026-11-15, axis "refusal honesty").

    A verdict the judge has not returned yet must not become a reward, must not finalize
    the attempt, and must not feed the bandit — otherwise a "we do not know" is silently
    counted as a failure, which is exactly the accounting lie the axis is about.  A later
    verdict for the same attempt is still allowed to land (nothing is frozen by pending).
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.conn = store.connect(self.dir / "t.db")
        self.lease = store.acquire_lease(self.conn, "lane-p", "target")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES(?,?,?,?)",
            (PAIR, driver.BOARD_NAME, "scenario", "model"))
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,state,delta) VALUES('att-p',?,?,?,?,?,?,?,?)",
            (PAIR, driver.BOARD_NAME, "scenario", "model", "lane-p", 0.0, "submitted", "arm"))
        self.conn.commit()
        self.engine = ImmutabilityTest._Engine()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _apply(self, status: str, **extra):
        res = {"status": status, "judge_ref": "", "operation_id": "opid-p",
               "chat_id": "deadbeef", "score": None, "pcts": [], "verdict": status,
               "raw_hash": "h", "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        res.update(extra)
        return driver.apply_verdict(self.conn, self.lease, "att-p", PAIR, "scenario",
                                    "model", "arm", res, {"probe_ok": True}, self.engine)

    def test_pending_records_no_reward_and_does_not_finalize(self):
        out = self._apply("pending")
        self.assertEqual(out["outcome"], "pending")
        row = store.get_attempt(self.conn, "att-p")
        self.assertIsNone(row["reward"], "an unknown outcome must not become a number")
        self.assertNotEqual(row["state"], "finalized")
        self.assertEqual(row["judge_status"], "pending")

    def test_pending_does_not_feed_the_bandit(self):
        self._apply("pending")
        self.assertEqual(self.engine.calls, [],
                         "the engine must not be told about a verdict that has not landed")

    def test_a_later_real_verdict_is_still_accepted(self):
        self._apply("pending")
        out = self._apply("verified", score=100, verdict="accepted", pcts=[100, 0])
        self.assertEqual(out["outcome"], "verified")
        row = store.get_attempt(self.conn, "att-p")
        self.assertIsNotNone(row["reward"])
        self.assertEqual(row["state"], "finalized")
        self.assertEqual(len(self.engine.calls), 1, "exactly one real observation")
