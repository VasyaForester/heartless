"""Online candidate learning: watermark semantics (2026-11-15)."""
import pathlib
import sqlite3
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import online_learning  # noqa: E402


class LiveObservationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.conn = sqlite3.connect(self.tmp / "t.db")
        self.conn.execute("CREATE TABLE attempts (pair_id TEXT, delta TEXT, reward REAL)")
        self.conn.execute("INSERT INTO attempts VALUES ('negq|SA', 'append_policy', 0.2)")
        self.conn.commit()
        self.rows = []

    def tearDown(self):
        self.conn.close()

    def test_watermark_skips_history_and_appends_new(self):
        live = online_learning.LiveObservations(
            self.conn, self.rows, state_path=self.tmp / "state.json", board="lbp")
        self.assertEqual(live.pull(), 0)  # стартовый watermark
        self.conn.execute(
            "INSERT INTO attempts VALUES ('negq|SA', 'gen.audit.prose_pre.keep_verbatim', 0.6)")
        self.conn.commit()
        self.assertEqual(live.pull(), 1)
        self.assertEqual(self.rows[0]["spec"], ("audit", "prose_pre", "keep_verbatim"))
        self.assertEqual(live.pull(), 0)  # без дублей

    def test_state_survives_restart(self):
        live = online_learning.LiveObservations(
            self.conn, self.rows, state_path=self.tmp / "state.json", board="lbp")
        self.conn.execute(
            "INSERT INTO attempts VALUES ('negq|SA', 'gen.quote.prose_post.fill_row', 0.4)")
        self.conn.commit()
        self.assertEqual(live.pull(), 1)
        again = online_learning.LiveObservations(
            self.conn, [], state_path=self.tmp / "state.json", board="lbp")
        self.assertEqual(again.pull(), 0)


if __name__ == "__main__":
    unittest.main()