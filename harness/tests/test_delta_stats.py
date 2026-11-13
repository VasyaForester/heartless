"""Arm statistics must come from the authoritative reward channel.

The live selector read the legacy `deltas` aggregate, where two scales had been
mixed (judge score sums 0..300 written before v4 and normalised rewards 0..100
after): 62 rows read as means up to 1.93, so the selector ranked arms across
incompatible units.
"""

import os
import pathlib
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import driver  # noqa: E402
import store  # noqa: E402

PAIR = "scenario|model"


class DeltaStatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(pathlib.Path(self.tmp.name) / "t.db")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES(?,?,?,?)",
            (PAIR, driver.BOARD_NAME, "scenario", "model"))
        self.conn.commit()

    def tearDown(self):
        # Windows keeps the file locked until the connection is closed, and the
        # temp-dir cleanup then fails AFTER the assertions already passed.
        self.conn.close()
        self.tmp.cleanup()

    def add_attempt(self, aid, delta, reward, source="local"):
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,delta,reward,reward_source,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (aid, PAIR, driver.BOARD_NAME, "scenario", "model", "test", time.time(),
             delta, reward, source, "finalized"))
        self.conn.commit()

    def test_stats_come_from_attempt_rewards(self):
        self.add_attempt("a1", "arm_a", 0.2)
        self.add_attempt("a2", "arm_a", 0.8)
        self.add_attempt("b1", "arm_b", 0.1)
        stats = driver.delta_stats(self.conn, PAIR)
        self.assertEqual(stats["arm_a"]["n"], 2)
        self.assertAlmostEqual(stats["arm_a"]["mean"], 0.5, places=4)
        self.assertEqual(stats["arm_a"]["wins"], 1)
        self.assertGreater(stats["arm_a"]["sd"], 0.0, "spread must be real, not 0")
        self.assertEqual(stats["arm_b"]["n"], 1)

    def test_unrewarded_attempts_are_not_counted(self):
        self.add_attempt("a1", "arm_a", 0.4)
        self.conn.execute("INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,"
                          "model,lane,started_at,delta,state) VALUES('a2',?,?,?,?,?,?,?,?)",
                          (PAIR, driver.BOARD_NAME, "scenario", "model", "test",
                           time.time(), "arm_a", "unjudged"))
        self.conn.commit()
        stats = driver.delta_stats(self.conn, PAIR)
        self.assertEqual(stats["arm_a"]["n"], 1)

    def test_a_mixed_scale_legacy_row_cannot_leak_in(self):
        """The pre-v4 aggregate says this arm averages 1.93; with rewarded
        attempts present it must be ignored entirely."""
        self.conn.execute(
            "INSERT INTO deltas(pair_id,delta,n,sum_score) VALUES(?,?,?,?)",
            (PAIR, "arm_a", 12, 2310))
        self.add_attempt("a1", "arm_a", 0.2)
        stats = driver.delta_stats(self.conn, PAIR)
        self.assertAlmostEqual(stats["arm_a"]["mean"], 0.2, places=4)
        self.assertEqual(stats["arm_a"]["n"], 1)

    def test_legacy_fallback_only_when_there_is_nothing_better(self):
        self.conn.execute(
            "INSERT INTO deltas(pair_id,delta,n,sum_score) VALUES(?,?,?,?)",
            (PAIR, "arm_a", 2, 100))
        self.conn.commit()
        stats = driver.delta_stats(self.conn, PAIR)
        self.assertEqual(stats["arm_a"]["n"], 2)

    def test_empty_pair_returns_nothing(self):
        self.assertEqual(driver.delta_stats(self.conn, PAIR), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
