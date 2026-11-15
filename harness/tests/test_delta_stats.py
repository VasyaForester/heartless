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
import strategy  # noqa: E402
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

    def add_attempt(self, aid, delta, reward, source="local", started_at=None):
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,delta,reward,reward_source,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (aid, PAIR, driver.BOARD_NAME, "scenario", "model", "test",
             started_at if started_at is not None else time.time(),
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

class DecayTest(unittest.TestCase):
    """Advice #7: old observations weigh less — measured, not assumed.

    The synthetic bench (harness/bench_synth.py, 8 seeds) showed the UCB family
    gaining in every world with a probe-count half-life, while the Beta family loses
    (its prior already shrinks counts), so decay is a per-policy switch.  These tests
    pin the mechanics: the unit is PROBES (an idle night must not erase knowledge),
    whole numbers stay whole, and a half-life of None keeps today's behaviour.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(pathlib.Path(self.tmp.name) / "t.db")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES(?,?,?,?)",
            (PAIR, driver.BOARD_NAME, "scenario", "model"))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def add(self, aid, delta, reward, ts):
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,delta,reward,reward_source,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (aid, PAIR, driver.BOARD_NAME, "scenario", "model", "test", ts,
             delta, reward, "local", "finalized"))
        self.conn.commit()

    def _pair_with_history(self, old_delta, new_delta, n_old=5, n_new=1):
        """old_delta paid early, new_delta pays late; every probe is one step."""
        base = time.time() - 10000
        for i in range(n_old):
            self.add(f"old{i}", old_delta, 1.0, base + i)
        for i in range(n_new):
            self.add(f"new{i}", new_delta, 1.0, base + 100 + i)

    def test_a_short_half_life_shrinks_stale_evidence_not_counts(self):
        self._pair_with_history("arm_old", "arm_new", n_old=5, n_new=1)
        raw = driver.delta_stats(self.conn, PAIR)
        decayed = driver.delta_stats(self.conn, PAIR, half_life_probes=2.0)
        self.assertEqual(raw["arm_old"]["n"], 5)
        self.assertGreater(decayed["arm_old"]["n"], 0)
        self.assertLess(decayed["arm_old"]["n"], raw["arm_old"]["n"],
                        "stale evidence must weigh less than five full observations")

    def test_no_half_life_keeps_the_previous_behaviour(self):
        self._pair_with_history("arm_old", "arm_new")
        raw = driver.delta_stats(self.conn, PAIR)
        explicit = driver.delta_stats(self.conn, PAIR, half_life_probes=None)
        self.assertEqual(raw, explicit)

    def test_whole_numbers_stay_whole_and_fractions_do_not(self):
        now = time.time()
        for i in range(3):
            self.add(f"a{i}", "arm_a", 0.4, now + i)
        stats = driver.delta_stats(self.conn, PAIR, half_life_probes=1e6)
        self.assertIsInstance(stats["arm_a"]["n"], int)
        stats_small = driver.delta_stats(self.conn, PAIR, half_life_probes=1.5)
        self.assertIsInstance(stats_small["arm_a"]["n"], float)

    def test_decay_is_per_policy_by_default(self):
        self.assertEqual(strategy.half_life_probes("ucb_improved"), 150.0)
        self.assertEqual(strategy.half_life_probes("legacy"), 150.0)
        self.assertIsNone(strategy.half_life_probes("thompson"))
        self.assertIsNone(strategy.half_life_probes("contextual_ts"))
