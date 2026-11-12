import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import reconcile  # noqa: E402
import store  # noqa: E402


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "h.db"
        conn = store.connect(self.db)
        conn.execute("INSERT INTO pairs(id,board_profile,scenario,model,solved,attempts)"
                     " VALUES('s|m','lucky-break-payday','s','m',0,0)")
        conn.commit()
        conn.close()
        self.pairs = self.dir / "pairs.jsonl"
        self.pairs.write_text(json.dumps({
            "scenario_id": "s", "model_id": "m", "outcome": "SUCCESS", "attempts": 5,
        }) + "\n", encoding="utf-8")
        self.v2 = self.dir / "pairs-v2.jsonl"
        self.v2.write_text(json.dumps({"pair_id": "s|m", "solved": False}) + "\n",
                           encoding="utf-8")
        self.board = self.dir / "board.json"
        self.board.write_text(json.dumps({"pairs": {"s|m": {"solved": False}}}),
                              encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_conflict(self):
        report = reconcile.reconcile(self.db, self.pairs, self.v2, self.board)
        self.assertTrue(any(c["pair"] == "s|m" for c in report["status_conflicts"]))

    def test_attempts_absent(self):
        report = reconcile.reconcile(self.db, self.pairs, self.v2, self.board)
        self.assertTrue(any(a["pair"] == "s|m" for a in report["attempts_absent"]))

    def test_missing_in_db(self):
        self.pairs.write_text(json.dumps({
            "scenario_id": "x", "model_id": "y", "outcome": "SUCCESS", "attempts": 1,
        }) + "\n", encoding="utf-8")
        report = reconcile.reconcile(self.db, self.pairs, self.v2, self.board)
        self.assertIn("x|y", report["missing_in_db"])

    def test_missing_in_export(self):
        self.v2.write_text("", encoding="utf-8")
        report = reconcile.reconcile(self.db, self.pairs, self.v2, self.board)
        self.assertIn("s|m", report["missing_in_export"])

    def test_read_only(self):
        before = self.db.stat().st_mtime
        reconcile.reconcile(self.db, self.pairs, self.v2, self.board)
        self.assertEqual(self.db.stat().st_mtime, before)


if __name__ == "__main__":
    unittest.main()