"""The give-up rule: a pair that never moves yields its slot — softly.

Advice #6 (2026-11-13) said the budget should not keep flowing to pairs that show
no sign of movement.  The risk of doing that badly is obvious: a rule that can
remove the last candidate stops the lane, and the standing rule is that the lane
keeps solving tasks no matter what.  These tests pin the three properties that make
it safe to run unattended:

  * it fires from DATA (probes since the last movement, best reward), not from a
    hand-written list;
  * it never empties the candidate pool — `pick_pair` probes anyway rather than
    stalling;
  * it EXPIRES by itself, so a pair is retested once the world has had time to
    change.
"""

import json
import os
import pathlib
import random
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


class GiveUpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = pathlib.Path(self.tmp.name)
        self._work, driver.WORK = driver.WORK, self.work
        (self.work / "artifacts").mkdir(parents=True, exist_ok=True)
        self.conn = store.connect(self.work / "t.db")
        for key in ("dead|model", "alive|model"):
            self.conn.execute(
                "INSERT INTO pairs(id,board_profile,scenario,model,solved,attempts,best_input)"
                " VALUES(?,?,?,?,0,0,'inputs/x.txt')",
                (key, driver.BOARD_NAME, key.split("|")[0], "model"))
        self.conn.commit()

    def tearDown(self):
        driver.WORK = self._work
        self.conn.close()
        self.tmp.cleanup()

    def add(self, pair, reward, ts):
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,delta,reward,reward_source,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (f"{pair}-{ts}", pair, driver.BOARD_NAME, pair.split("|")[0], "model",
             "test", ts, "arm", reward, "local", "finalized"))
        self.conn.commit()

    def test_a_pair_with_no_movement_is_parked_and_an_alive_one_is_not(self):
        now = time.time()
        want = driver.GIVE_UP["min_probes"]
        for i in range(want + 2):
            self.add("dead|model", 0.0, now - 3600 + i)   # inside the 12h window
        self.add("alive|model", 0.6, now - 100)
        parked = driver._give_up_pairs(self.conn, ["dead|model", "alive|model"], now)
        self.assertEqual(parked, {"dead|model"})
        state = json.loads((self.work / driver.GIVE_UP["state"]).read_text(encoding="utf-8"))
        self.assertIn("dead|model", state)
        self.assertGreater(state["dead|model"]["until"], now)

    def test_a_single_movement_in_the_window_resets_the_clock(self):
        now = time.time()
        want = driver.GIVE_UP["min_probes"]
        for i in range(want + 2):
            self.add("dead|model", 0.0, now - 3600 + i)
        self.add("dead|model", 0.5, now - 60)  # one real sign of life, recently
        parked = driver._give_up_pairs(self.conn, ["dead|model"], now)
        self.assertEqual(parked, set(), "a recent rewarded probe must not be parked")

    def test_old_probes_outside_the_window_do_not_count(self):
        """The first version of this rule looked at the lifetime best reward and
        therefore could never fire (every pair carries 0.35-0.70 from days ago).
        Only the recent window may decide."""
        now = time.time()
        want = driver.GIVE_UP["min_probes"]
        for i in range(want * 3):
            self.add("dead|model", 0.0, now - 5 * 86400 + i)   # ancient, outside
        parked = driver._give_up_pairs(self.conn, ["dead|model"], now)
        self.assertEqual(parked, set())

    def test_the_park_expires_by_itself(self):
        now = time.time()
        want = driver.GIVE_UP["min_probes"]
        for i in range(want + 2):
            self.add("dead|model", 0.0, now - 3600 + i)
        driver._give_up_pairs(self.conn, ["dead|model"], now)
        later = now + driver.GIVE_UP["park_hours"] * 3600.0 + 1
        parked = driver._give_up_pairs(self.conn, ["dead|model"], later)
        # the pair is eligible again: the rule may re-park it, but never as "still
        # parked from before" — the state must be refreshed, not carried over
        state = json.loads((self.work / driver.GIVE_UP["state"]).read_text(encoding="utf-8"))
        self.assertGreater(state["dead|model"]["parked_at"], now - 1)
        self.assertGreater(state["dead|model"]["until"], later)

    def test_pick_pair_never_stalls_even_when_everything_is_parked(self):
        now = time.time()
        want = driver.GIVE_UP["min_probes"]
        for pair in ("dead|model", "alive|model"):
            for i in range(want + 2):
                self.add(pair, 0.0, now - 3600 + i)
        # every candidate qualifies for a park: the lane must still pick one
        key = driver.pick_pair(self.conn, random.Random(1), cooldown_s=0.0, window_s=1e9)
        self.assertIn(key, {"dead|model", "alive|model"})

    def test_an_unknown_pair_is_never_parked(self):
        self.assertEqual(driver._give_up_pairs(self.conn, ["ghost|model"], time.time()),
                         set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
