"""Judge ledger tests: an attempt must never inherit another attempt's verdict."""
import json
import pathlib
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import judge_ledger  # noqa: E402


def _judge_file(path, opid, status="rejected", pcts=("0%",), minutes_ago=0):
    from datetime import datetime, timedelta, timezone
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago))
    path.write_text(json.dumps({
        "clicked": True, "kind": "judge", "status": status,
        "submittedAt": stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "operationId": opid,
        "url": "https://app.grayswan.ai/arena/challenge/lucky-break-payday?chatId=abc123",
        "criteriaPercents": [{"selector": "#bits-c1", "text": f"tool … {p}"} for p in pcts],
    }), encoding="utf-8")
    return path


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self._old_dir, self._old_index = judge_ledger.LEDGER_DIR, judge_ledger.INDEX_PATH
        judge_ledger.LEDGER_DIR = self.dir / "judges"
        judge_ledger.INDEX_PATH = judge_ledger.LEDGER_DIR / "index.jsonl"

    def tearDown(self):
        judge_ledger.LEDGER_DIR, judge_ledger.INDEX_PATH = self._old_dir, self._old_index
        self.tmp.cleanup()

    def test_foreign_artifact_is_never_bound(self):
        p = _judge_file(self.dir / "pair-judge.json", "op-prev")
        res = judge_ledger.bind(p, "op-now")
        self.assertFalse(res["bound"])
        self.assertEqual(res["reason"], "judge belongs to another operation")
        self.assertIsNone(judge_ledger.path_for("op-now"))
        self.assertTrue(judge_ledger.is_foreign(p, "op-now"))
        self.assertFalse(judge_ledger.is_foreign(p, "op-prev"))

    def test_matching_artifact_binds_and_is_indexed(self):
        p = _judge_file(self.dir / "pair-judge.json", "op-now")
        res = judge_ledger.bind(p, "op-now", pair_key="s|m")
        self.assertTrue(res["bound"])
        self.assertIsNotNone(judge_ledger.path_for("op-now"))
        entry = judge_ledger.load("op-now")
        self.assertEqual(entry["operationId"], "op-now")
        self.assertEqual(judge_ledger.status_of(judge_ledger.path_for("op-now")), "rejected")
        rows = judge_ledger.index()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pair"], "s|m")
        self.assertEqual(rows[0]["chat_id"], "abc123")

    def test_rebind_does_not_overwrite_the_first_artifact(self):
        p = _judge_file(self.dir / "pair-judge.json", "op-now", pcts=("10%",))
        first = judge_ledger.bind(p, "op-now")
        _judge_file(p, "op-now", pcts=("90%",))
        second = judge_ledger.bind(p, "op-now")
        self.assertEqual(first["sha256"], second["sha256"], "ledger copy was overwritten")
        self.assertEqual(judge_ledger.load("op-now")["criteriaPercents"][0]["text"], "tool … 10%")

    def test_observation_envelope_is_unwrapped(self):
        p = self.dir / "chatops.json"
        inner = {"status": "accepted", "operationId": "op-x",
                 "url": "https://x?chatId=deadbeef"}
        p.write_text(json.dumps({"clicked": True, "kind": "judge",
                                 "observation": json.dumps(inner)}), encoding="utf-8")
        self.assertEqual(judge_ledger.operation_id_of(p), "op-x")
        self.assertTrue(judge_ledger.bind(p, "op-x")["bound"])

    def test_missing_file_is_reported_not_invented(self):
        res = judge_ledger.bind(self.dir / "nope.json", "op-1")
        self.assertFalse(res["bound"])
        self.assertEqual(res["reason"], "no judge artifact")
        self.assertIsNone(judge_ledger.operation_id_of(None))
        self.assertIsNone(judge_ledger.path_for(""))


class LateVerdictTest(unittest.TestCase):
    """An `unjudged` attempt must accept a late verdict — and never be reused."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        import attempts
        import store
        self.attempts, self.store = attempts, store
        self.conn = store.connect(self.dir / "h.db")
        self.lease = store.acquire_lease(self.conn, "test", "tab")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model,best_input)"
            " VALUES('s|m','lucky-break-payday','s','m','inputs/x.txt')")
        self.conn.commit()
        self._old = (judge_ledger.LEDGER_DIR, judge_ledger.INDEX_PATH)
        judge_ledger.LEDGER_DIR = self.dir / "judges"
        judge_ledger.INDEX_PATH = judge_ledger.LEDGER_DIR / "index.jsonl"

    def tearDown(self):
        judge_ledger.LEDGER_DIR, judge_ledger.INDEX_PATH = self._old
        self.conn.close()
        self.tmp.cleanup()

    def _attempt(self, aid):
        self.store.insert_attempt(self.conn, self.lease, {
            "attempt_id": aid, "pair_id": "s|m", "board_profile": "lucky-break-payday",
            "scenario": "s", "model": "m", "lane": "test", "started_at": time.time(),
        })
        self.attempts.prepare(self.conn, self.lease, aid, input_text="hello",
                              input_path="inputs/x.txt", delta="append_nonce",
                              delta_version=1, nonce="n1", strategy_version=3)
        self.attempts.mark_submitted(self.conn, self.lease, aid, transcript_text="reply")
        return aid

    def test_unjudged_is_not_terminal_and_a_late_verdict_finalizes(self):
        aid = "board:s:m:test:aaaaaaaaaaaa"
        self._attempt(aid)
        self.attempts.mark_unjudged(self.conn, self.lease, aid, reason="not submitted")
        row = self.store.get_attempt(self.conn, aid)
        self.assertEqual(row["state"], "unjudged")
        self.assertNotIn("unjudged", self.store.TERMINAL)
        # the ledger copy arrives later, exactly as the platform would deliver it
        _judge_file(self.dir / "later.json", aid, status="accepted", pcts=("100%", "100%"))
        judge_ledger.bind(self.dir / "later.json", aid)
        done = judge_ledger.reconcile_unjudged(self.conn, self.lease)
        self.assertEqual(done[0]["status"], "verified")
        self.assertTrue(done[0]["solved"])
        row = self.store.get_attempt(self.conn, aid)
        self.assertEqual(row["state"], "finalized")
        self.assertEqual(row["reward"], 1.0)
        self.assertEqual(row["reward_source"], "judge")
        self.assertEqual(self.conn.execute("SELECT solved FROM pairs WHERE id='s|m'")
                         .fetchone()["solved"], 1)

    def test_missing_ledger_entry_leaves_the_attempt_open(self):
        aid = "board:s:m:test:bbbbbbbbbbbb"
        self._attempt(aid)
        self.attempts.mark_unjudged(self.conn, self.lease, aid)
        self.assertEqual(judge_ledger.reconcile_unjudged(self.conn, self.lease), [])
        self.assertEqual(self.store.get_attempt(self.conn, aid)["state"], "unjudged")


if __name__ == "__main__":
    unittest.main()
