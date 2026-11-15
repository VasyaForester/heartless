"""One reward function, one board — across the bench, the nightly report and the choice.

Grok's review (2026-11-15, axis "measurability": 8/10) ended with: "ночной отчёт и выбор
попытки ссылаются на одну функцию награды и на одну доску".  This file pins that state of
affairs so a later edit cannot quietly fork it:

  * the driver SELECTS on `attempts.reward` (delta_stats reads that column);
  * the nightly report COUNTS wins with the same column (`reward >= 0.5` on attempts);
  * the bench now GRADES with that channel BY DEFAULT (DEFAULT_REWARD_MAP = 'db'), with the
    local map only as a documented fallback for probes the journal never rewarded;
  * every one of them analyses ONE board (the profile registry decides which).

The functional half (that the db channel really reads attempts.reward) lives in
test_reward_channel.py; here are the wiring guards plus the pure channel mapping, because
the failure mode is a future edit choosing a different source, not today's behaviour.
"""

import os
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import strategy_bench as bench  # noqa: E402


def code_lines(name: str) -> str:
    path = HARNESS / name
    return "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines()
                     if not ln.strip().startswith("#"))


class RewardChannelMappingTest(unittest.TestCase):
    def test_the_default_is_the_drivers_channel(self):
        self.assertEqual(bench.DEFAULT_REWARD_MAP, "db")
        source, flags = bench.reward_channel(bench.DEFAULT_REWARD_MAP)
        self.assertEqual(source, "db", "the bench must grade by attempts.reward by default")
        self.assertEqual(flags, (True, True), "and keep both local-map fixes as the fallback")

    def test_the_older_maps_are_still_askable(self):
        self.assertEqual(bench.reward_channel("v2"), ("local", (True, True)))
        self.assertEqual(bench.reward_channel("faults"), ("local", (True, False)))
        self.assertEqual(bench.reward_channel("v1"), ("local", (False, False)))

    def test_an_unknown_choice_is_refused(self):
        with self.assertRaises(ValueError):
            bench.reward_channel("whatever")

    def test_the_cli_takes_its_default_from_the_constant(self):
        self.assertIn("default=DEFAULT_REWARD_MAP", code_lines("strategy_bench.py"),
                      "the argparse default must come from the one constant")


class OneRewardFunctionTest(unittest.TestCase):
    """Source guards: every consumer of the reward reads the SAME column."""

    def test_the_driver_selects_on_attempts_reward(self):
        src = code_lines("driver.py")
        self.assertIn("reward", src)
        # the selector's statistics come from the reward column, not from a local guess
        idx = src.find("def delta_stats(")
        self.assertGreater(idx, 0)
        window = src[idx:idx + 2500]
        self.assertIn("reward", window, "delta_stats must read the reward column")

    def test_the_nightly_report_counts_wins_with_the_same_column(self):
        src = code_lines("nightly.py")
        self.assertIn("reward>=0.5", src.replace(" ", ""),
                      "the nightly win count must read attempts.reward")

    def test_the_bench_grades_by_the_driver_channel_by_default(self):
        src = code_lines("strategy_bench.py")
        self.assertIn("DEFAULT_REWARD_MAP = \"db\"", src)

    def test_everything_pins_one_board(self):
        """The ledger is shared by all boards; each consumer must analyse one."""
        bench_src = code_lines("strategy_bench.py")
        self.assertIn("board_of", bench_src, "the bench resolves the board, never mixes them")
        nightly = code_lines("nightly.py")
        self.assertIn("board", nightly, "the nightly report is per-board")


if __name__ == "__main__":
    unittest.main(verbosity=2)
