import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import attempts  # noqa: E402
import store  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "h.db"
        self.conn = store.connect(self.db)
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES('s|m','lucky-break-payday','s','m')")
        self.conn.commit()
        self.lease = store.acquire_lease(self.conn, "test", "tab", pid=os.getpid())
        self.assertIsNotNone(self.lease)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def make_attempt(self, aid="a1", state="prepared"):
        store.insert_attempt(self.conn, self.lease, {
            "attempt_id": aid, "pair_id": "s|m", "board_profile": "lucky-break-payday",
            "scenario": "s", "model": "m", "lane": "test", "started_at": time.time(),
        })
        attempts.prepare(self.conn, self.lease, aid, input_text="hello",
                         input_path="inputs/x.txt", delta="append_nonce",
                         delta_version=1, nonce="n1")
        if state in ("submitted", "awaiting"):
            attempts.mark_submitted(self.conn, self.lease, aid, transcript_text="hello")
        if state == "awaiting":
            attempts.mark_awaiting(self.conn, self.lease, aid, judge_ref="j.json")
        return aid

    def test_schema_version(self):
        self.assertEqual(store.schema_version(self.conn), store.SCHEMA_VERSION)
        self.assertTrue(self.conn.execute("PRAGMA foreign_keys").fetchone()[0])

    def test_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,started_at)"
                " VALUES('bad','missing','lucky-break-payday','s','m','test',0)")

    def test_lease_fencing(self):
        lease2 = store.acquire_lease(self.conn, "test", "tab", pid=os.getpid())
        self.assertIsNotNone(lease2)
        with self.assertRaises(store.LeaseLost):
            store.heartbeat(self.conn, self.lease)
        store.heartbeat(self.conn, lease2)

    def test_expired_lease_cannot_write(self):
        aid = self.make_attempt()
        self.conn.execute("UPDATE leases SET heartbeat=0 WHERE lane='test'")
        self.conn.commit()
        with self.assertRaises(store.LeaseLost):
            store.transition(self.conn, self.lease, aid, "prepared",
                             input_text="x")

    def test_invalid_transition(self):
        aid = self.make_attempt()
        with self.assertRaises(store.InvalidTransition):
            store.transition(self.conn, self.lease, aid, "finalized")

    def test_events_append_only(self):
        aid = self.make_attempt(state="awaiting")
        rows = self.conn.execute(
            "SELECT from_state,to_state FROM attempt_events WHERE attempt_id=? ORDER BY seq",
            (aid,)).fetchall()
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [(None, "allocated"), ("allocated", "prepared"),
                          ("prepared", "submitted"), ("submitted", "awaiting_judge")])

    def test_pending_judge_cannot_finalize(self):
        aid = self.make_attempt(state="awaiting")
        store.record_judge(self.conn, self.lease, aid, "j.json",
                           status="pending", score=None, pcts=[], verified=False)
        with self.assertRaises(store.InvalidTransition):
            store.finalize_attempt(self.conn, self.lease, aid, solved=True)

    def test_verified_judge_finalizes(self):
        aid = self.make_attempt(state="awaiting")
        store.record_judge(self.conn, self.lease, aid, "j.json",
                           status="accepted", score=90, pcts=[90], verified=True)
        store.transition(self.conn, self.lease, aid, "judged",
                         judge_status="verified", score=90, pcts="[90]",
                         verdict="accepted")
        store.finalize_attempt(self.conn, self.lease, aid, solved=True)
        row = self.conn.execute("SELECT solved,solved_attempt FROM pairs WHERE id='s|m'").fetchone()
        self.assertEqual(row["solved"], 1)
        self.assertEqual(row["solved_attempt"], aid)

    def test_migration_from_v2(self):
        v2 = Path(self.tmp.name) / "v2.db"
        c = sqlite3.connect(v2)
        c.executescript("""
        CREATE TABLE pairs (id TEXT PRIMARY KEY, scenario TEXT, model TEXT,
          solved INTEGER DEFAULT 0, best_score INTEGER DEFAULT -1, best_input TEXT,
          attempts INTEGER DEFAULT 0, last_verdict TEXT);
        CREATE TABLE deltas (pair_id TEXT, delta TEXT, n INTEGER DEFAULT 0,
          sum_score INTEGER DEFAULT 0, PRIMARY KEY (pair_id, delta));
        CREATE TABLE attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, pair_id TEXT,
          delta TEXT, input TEXT, started REAL, finished REAL, rc INTEGER,
          verdict TEXT, score INTEGER, pcts TEXT, energy INTEGER);
        CREATE TABLE leases (lane TEXT PRIMARY KEY, pid INTEGER, target TEXT, heartbeat REAL);
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, payload TEXT);
        """)
        c.execute("INSERT INTO pairs VALUES('s|m','s','m',0,-1,NULL,0,NULL)")
        c.execute("INSERT INTO attempts(pair_id,delta,input,started,finished,rc,verdict,score,pcts,energy)"
                  " VALUES('s|m','append_nonce','inputs/x.txt',1,2,0,'accepted',90,'[90]',10)")
        c.commit()
        c.close()
        conn = store.connect(v2)
        self.assertEqual(store.schema_version(conn), store.SCHEMA_VERSION)
        row = conn.execute("SELECT * FROM attempts WHERE attempt_id='legacy-1'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["judge_status"], "unverified")
        # v4 additive columns exist after migrating an older database
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(pairs)")}
        self.assertTrue({"latest_input", "latest_attempt", "best_attempt"} <= cols)
        acols = {r["name"] for r in conn.execute("PRAGMA table_info(attempts)")}
        self.assertTrue({"reward", "reward_source"} <= acols)
        self.assertTrue(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='attempts_v2'").fetchone())
        conn.close()


if __name__ == "__main__":
    unittest.main()