"""Generator A/B: the tagging that makes the experiment measurable, and the
verdict rule that keeps 'undecided' on the table."""

import os
import pathlib
import random
import sqlite3
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import ab_report  # noqa: E402
import store  # noqa: E402


class ClassifyTest(unittest.TestCase):
    def test_explicit_tag_wins(self):
        self.assertEqual(ab_report.classify("gen.contract.aria.x", "control_repeat"),
                         "control_repeat")
        self.assertEqual(ab_report.classify("append_schema", "generated"), "generated")

    def test_historical_rows_fall_back_to_the_prefix(self):
        # pre-experiment rows have no tag: a 'gen.*' delta can only be generated
        self.assertEqual(ab_report.classify("gen.authority.aria.keep", None), "generated")
        self.assertEqual(ab_report.classify("append_schema", None), "catalog")
        self.assertEqual(ab_report.classify(None, None), "catalog")


class VerdictTest(unittest.TestCase):
    @staticmethod
    def rows(source, rewards):
        return [{"pair_id": "s|m", "delta": "d", "arm_source": source, "reward": r,
                 "reward_source": "local", "state": "finalized", "started_at": 0.0}
                for r in rewards]

    def test_no_verdict_before_the_sample_guard(self):
        gen = ab_report.summarise(self.rows("generated", [1.0] * 5))
        ctl = ab_report.summarise(self.rows("control_repeat", [0.0] * 5))
        v = ab_report.verdict(gen, ctl, min_n=20)
        self.assertEqual(v["call"], "undecided")
        self.assertEqual(v["still_needed"], {"generated": 15, "control_repeat": 15})

    def test_overlapping_intervals_stay_undecided(self):
        gen = ab_report.summarise(self.rows("generated", [1.0] * 12 + [0.0] * 8))
        ctl = ab_report.summarise(self.rows("control_repeat", [1.0] * 11 + [0.0] * 9))
        v = ab_report.verdict(gen, ctl, min_n=20)
        self.assertEqual(v["call"], "undecided")
        self.assertEqual(v["reason"], "success intervals overlap")

    def test_a_real_gap_is_called(self):
        gen = ab_report.summarise(self.rows("generated", [1.0] * 18 + [0.0] * 2))
        ctl = ab_report.summarise(self.rows("control_repeat", [1.0] * 2 + [0.0] * 18))
        v = ab_report.verdict(gen, ctl, min_n=20)
        self.assertEqual(v["call"], "generated")
        self.assertGreater(v["delta_mean_reward"], 0)

    def test_control_can_win_too(self):
        gen = ab_report.summarise(self.rows("generated", [0.0] * 20))
        ctl = ab_report.summarise(self.rows("control_repeat", [1.0] * 20))
        v = ab_report.verdict(gen, ctl, min_n=20)
        self.assertEqual(v["call"], "control_repeat")

    def test_wilson_interval_brackets_the_rate(self):
        lo, hi = ab_report.wilson(5, 10)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        self.assertAlmostEqual(ab_report.wilson(0, 0)[0], 0.0)


class TaggingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(pathlib.Path(self.tmp.name) / "t.db")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) "
            "VALUES('s|m','lucky-break-payday','s','m')")
        self.conn.commit()
        self.lease = store.acquire_lease(self.conn, "test", "tab", pid=os.getpid())

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_arm_source_survives_a_round_trip(self):
        import attempts as attempts_mod
        aid = attempts_mod.allocate(self.conn, self.lease, pair_id="s|m",
                                    board="lucky-break-payday", scenario="s", model="m",
                                    lane="test")
        store.set_arm_source(self.conn, self.lease, aid, "control_repeat")
        row = store.get_attempt(self.conn, aid)
        self.assertEqual(row["arm_source"], "control_repeat")
        # and the crash-safe path: an unknown id is a no-op, not an exception
        store.set_arm_source(self.conn, self.lease, "nope", "generated")
        self.assertEqual(store.get_attempt(self.conn, aid)["arm_source"], "control_repeat")

    def test_the_experiment_flag_parses_and_defaults_to_off(self):
        """--ab-generate must default to 1.0 (always generate): the flag changes
        live behaviour only when someone asks for it."""
        src = (HERE.parent / "driver.py").read_text(encoding="utf-8")
        self.assertIn('flag_default("ab_generate", "HERMES_AB_GENERATE", "1.0"', src)
        # the coin only decides inside the generation branch
        self.assertIn("a.ab_generate >= 1.0 or rng.random() < a.ab_generate", src)


class LaneFlagsTest(unittest.TestCase):
    """A live experiment must survive an auto-restart: an env var exported once
    is forgotten by the next supervisor/watchdog start, so the flag lives in a
    file, with CLI > env > file > default precedence."""

    def setUp(self):
        import driver as driver_mod
        self.driver = driver_mod
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.artifacts = pathlib.Path(self.tmp.name) / "artifacts"
        self.artifacts.mkdir(parents=True)
        self._work = driver_mod.WORK
        driver_mod.WORK = pathlib.Path(self.tmp.name)
        self.addCleanup(lambda: setattr(driver_mod, "WORK", self._work))

    def write_flags(self, text):
        (self.artifacts / "lane-flags.json").write_text(text, encoding="utf-8")

    def test_missing_file_is_empty(self):
        self.assertEqual(self.driver.lane_flags(), {})

    def test_broken_file_is_ignored_not_fatal(self):
        self.write_flags("{not json")
        self.assertEqual(self.driver.lane_flags(), {})

    def test_file_supplies_the_default_and_env_wins(self):
        self.write_flags('{"ab_generate": 0.5}')
        flags = self.driver.lane_flags()
        self.assertEqual(flags["ab_generate"], 0.5)
        self.assertEqual(self.driver.flag_default("ab_generate", "NOPE_ENV", 1.0, flags), 0.5)
        os.environ["HERMES_TEST_AB"] = "0.25"
        try:
            self.assertEqual(self.driver.flag_default("ab_generate", "HERMES_TEST_AB", 1.0, flags), "0.25")
        finally:
            os.environ.pop("HERMES_TEST_AB", None)
        self.assertEqual(self.driver.flag_default("unknown_flag", "NOPE_ENV", 1.0, flags), 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
