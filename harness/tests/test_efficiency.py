"""The mission metric must be computable offline, per board, and refuse noise.

Advice taken (2026-11-14): make "confirmed decisions per unit of energy" the
headline and split it into factors.  These tests pin the properties that keep it
honest: boards are never pooled, our own dropped probes are excluded from the
denominator of throughput, and a loss alarm cannot fire on an empty window (it
did: 1.00 over two probes after a machine sleep).
"""

import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import efficiency  # noqa: E402


def make_ledger(path: pathlib.Path, rows: list) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def make_db(path: pathlib.Path, attempts: list) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE attempts (attempt_id TEXT, pair_id TEXT,"
                 " board_profile TEXT, started_at REAL, submitted_at REAL,"
                 " execution_status TEXT, judge_status TEXT, score REAL,"
                 " reward REAL, reward_source TEXT, delta TEXT, arm_source TEXT,"
                 " lane TEXT)")
    for i, a in enumerate(attempts):
        conn.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (f"att{i}", a.get("pair", "s|m"), a["board"], a.get("ts", 0),
                      a.get("ts", 0) + 1, "ok", a.get("judge", "unjudged"),
                      a.get("score"), a.get("score") and 0.05,
                      a.get("score") and "judge", "d", "catalog", "main"))
    conn.commit()
    conn.close()


class EfficiencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.ledger = self.root / "repeats.jsonl"
        self.db = self.root / "harness.db"

    def test_boards_are_reported_separately_and_never_pooled(self):
        now = __import__("time").time()
        make_ledger(self.ledger, [
            {"ts": "2026-11-15T10:00:00", "scenario": "scam-retail", "probe_ok": True},
            {"ts": "2026-11-15T10:01:00", "scenario": "scam-retail", "probe_ok": False},
        ])
        make_db(self.db, [{"board": "lucky-break-payday", "ts": now, "judge": "verified", "score": 30},
                          {"board": "proving-ground", "ts": now}])
        rep = efficiency.report(24.0, db=self.db, repeats=self.ledger)
        self.assertIn("lucky-break-payday", rep["boards"])
        self.assertIn("proving-ground", rep["boards"])
        lbp = rep["boards"]["lucky-break-payday"]
        pg = rep["boards"]["proving-ground"]
        self.assertEqual(lbp["probes"], 1)
        self.assertEqual(lbp["judged"], 1)
        self.assertEqual(lbp["judge_positive"], 1)
        self.assertEqual(pg["probes"], 1)
        self.assertEqual(pg["judged"], 0)
        # energy comes from the board's own cost model, and it is reported per board
        self.assertIsNotNone(lbp["energy"])

    def test_our_own_faults_are_counted_outside_the_probe_count(self):
        make_ledger(self.ledger, [
            {"ts": "2026-11-15T10:00:00", "scenario": "scam-retail", "probe_ok": True},
            {"ts": "2026-11-15T10:00:30", "scenario": "scam-retail", "probe_ok": False},
            {"ts": "2026-11-15T10:00:45", "scenario": "scam-retail",
             "probe_ok": True, "invalid": True},
        ])
        rep = efficiency.report(24.0, db=self.db, repeats=self.ledger)
        total = rep["total"]
        self.assertEqual(total["faults"], 2)
        self.assertEqual(total["ledger_probes"], 3)
        self.assertAlmostEqual(total["fault_share_of_ledger"], round(2 / 3, 4))

    def test_the_loss_gate_needs_a_minimum_sample(self):
        """Measured defect: after a machine sleep the window held two probes, both
        faults, and the alarm fired with 1.00 — noise dressed as a signal."""
        make_ledger(self.ledger, [
            {"ts": "2026-11-15T10:00:00", "scenario": "scam-retail", "probe_ok": False},
            {"ts": "2026-11-15T10:00:30", "scenario": "scam-retail", "probe_ok": False},
        ])
        rep = efficiency.report(24.0, db=self.db, repeats=self.ledger, fail_over=0.45)
        gate = rep["total"]["loss_gate"]
        self.assertEqual(gate["fault_share"], 1.0)
        self.assertFalse(gate["tripped"], "a two-probe window must not trip the alarm")
        self.assertIn("asleep", gate.get("note", ""))

    def test_the_loss_gate_trips_on_a_real_loss_share(self):
        rows = [{"ts": f"2026-11-15T10:{i:02d}:00", "scenario": "scam-retail",
                 "probe_ok": False} for i in range(60)]
        make_ledger(self.ledger, rows)
        rep = efficiency.report(24.0, db=self.db, repeats=self.ledger, fail_over=0.45)
        gate = rep["total"]["loss_gate"]
        self.assertTrue(gate["tripped"])
        self.assertEqual(gate["sample"], 60)

    def test_missing_sources_do_not_explode(self):
        rep = efficiency.report(6.0, db=self.root / "nope.db",
                                repeats=self.root / "nope.jsonl")
        self.assertEqual(rep["total"]["probes"], 0)
        self.assertIsNone(rep["total"]["fault_share_of_ledger"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
