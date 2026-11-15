"""One reward function, one board: the bench grades by the number the driver uses.

Grok's review (2026-11-15, axis "measurability": 8/10) put the requirement plainly: the
number the bench prints has to be the number the driver optimises.  The driver selects
on `attempts.reward` (written by apply_verdict), while the bench used to grade every
probe with its own local map over the probe ledger.

`--reward-map db` closes that gap for the probes the journal knows: the reward comes
from `attempts.reward`, joined by the input file name, and the fallback for the rest is
explicit (each row carries `channel`, and the coverage share is printed).  These tests
pin the join, the fallback, the board pinning and the coverage arithmetic.

What they CANNOT do is pretend the two channels are identical for every probe — 74% of
ledger rows have no journal reward at all, so the honest statement is "the driver's own
number where it exists, a documented map elsewhere", which is exactly what the report
prints.
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

import store  # noqa: E402
import strategy_bench as bench  # noqa: E402

BOARD = "lucky-break-payday"
SCEN = "scam-retail"
MODEL = "Diamond Whale Bold"
ARM = "append_nonce"


def name_for(tag: str, delta=ARM, scenario=SCEN) -> str:
    """A probe file name the ledger's own parser accepts (see strategy_bench._DELTA_RE)."""
    return f"lbp-{scenario}-loop2-{delta}-1794747456-{tag}.txt"


def ledger_row(input_name: str, scenario=SCEN, model=MODEL, **extra) -> dict:
    row = {"ts": "2026-11-15T12:00:00", "scenario": scenario, "model": model,
           "input": f"inputs\\{input_name}", "probe_ok": True, "reply_tail": "sure, ok"}
    row.update(extra)
    return row


class RewardChannelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)
        self.db = self.dir / "harness.db"
        self.ledger = self.dir / "repeats.jsonl"
        conn = store.connect(self.db)
        conn.execute("INSERT INTO pairs(id,board_profile,scenario,model)"
                     " VALUES(?,?,?,?)", (f"{SCEN}|{MODEL}", BOARD, SCEN, MODEL))
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def add_attempt(self, input_name: str, reward: float, delta=ARM,
                    pair=None, with_reward=True):
        """One attempt row for this board's pair.

        `with_reward=False` writes a row the journal has no reward for (the selector
        will not see it, and neither may the bench).  The connection is always closed:
        a leaked handle on Windows makes the NEXT test's temp-dir cleanup fail, which
        is how one bad test used to cascade into four.
        """
        key = pair or f"{SCEN}|{MODEL}"
        conn = store.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
                "started_at,input_path,delta,reward,reward_source,state)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"att-{input_name}", key, BOARD, SCEN, MODEL, "lane", time.time(),
                 f"inputs\\{input_name}", delta, reward if with_reward else None,
                 "judge" if with_reward else None, "finalized"))
        finally:
            conn.close()

    def write_ledger(self, rows):
        self.ledger.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                               encoding="utf-8")

    def test_the_journal_reward_is_the_one_used_when_the_input_matches(self):
        name = name_for("1")
        self.add_attempt(name, 0.42)
        self.write_ledger([ledger_row(name)])
        rows = bench.load_history(self.ledger, board=BOARD, reward_source="db",
                                 db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "db")
        self.assertEqual(rows[0]["reward"], 0.42, "must be attempts.reward, not the map")
        self.assertEqual(rows[0]["confidence"], 1.0)

    def test_a_probe_the_journal_does_not_know_falls_back_and_says_so(self):
        self.add_attempt(name_for("1"), 0.42)
        self.write_ledger([ledger_row(name_for("1")), ledger_row(name_for("2"))])
        rows = bench.load_history(self.ledger, board=BOARD, reward_source="db",
                                  db_path=self.db)
        by_channel = {r["channel"] for r in rows}
        self.assertEqual(by_channel, {"db", "local"})
        local = next(r for r in rows if r["channel"] == "local")
        self.assertIsNotNone(local["reward"], "the fallback map still grades the probe")

    def test_without_the_db_channel_every_row_is_local(self):
        self.add_attempt(name_for("1"), 0.42)
        self.write_ledger([ledger_row(name_for("1"))])
        rows = bench.load_history(self.ledger, board=BOARD)
        self.assertEqual([r["channel"] for r in rows], ["local"])

    def test_the_board_is_pinned_by_the_profile_registry(self):
        """The ledger is shared by every board; a scenario of another board must be
        excluded, and the only way to know which board a scenario belongs to is the
        profile registry (boards/*.json) — one board per analysis."""
        foreign = next((s for s, b in bench.boards_by_scenario().items()
                        if b != BOARD), None)
        if not foreign:
            self.skipTest("no second board registered")
        self.add_attempt(name_for("1"), 0.1)
        self.write_ledger([ledger_row(name_for("1")),
                           ledger_row(name_for("2"), scenario=foreign, model="M")])
        rows = bench.load_history(self.ledger, board=BOARD)
        self.assertEqual(len(rows), 1, "the bench must analyse one board, not a mixture")

    def test_an_explicit_board_field_beats_the_scenario_guess(self):
        self.add_attempt(name_for("1"), 0.1)
        self.write_ledger([ledger_row(name_for("1"), board="some-other-board")])
        rows = bench.load_history(self.ledger, board=BOARD)
        self.assertEqual(rows, [])

    def test_db_rewards_reads_the_journal_and_ignores_unrewarded_rows(self):
        self.add_attempt(name_for("7"), 0.5)
        self.add_attempt(name_for("8"), 0.0, with_reward=False)
        got = bench.db_rewards(self.db)
        self.assertIn(name_for("7"), got)
        self.assertNotIn(name_for("8"), got,
                         "a row without a reward is not a measurement")

    def test_a_missing_journal_falls_back_instead_of_crashing(self):
        self.write_ledger([ledger_row(name_for("9"))])
        rows = bench.load_history(self.ledger, board=BOARD, reward_source="db",
                                  db_path=self.dir / "nope.db")
        self.assertEqual([r["channel"] for r in rows], ["local"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
