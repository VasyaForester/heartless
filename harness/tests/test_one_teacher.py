"""One teacher: the JUDGE.  The local proxy is a diagnostic, never the reward.

Task 2026-11-15 (`reports/agent-task-reward-2026-11-15.md`).  The selector learned from the
tool-call surrogate on 87% of the data: a probe pays 0.70 for calling a tool and `check_ready`
pays 0.80, while the JUDGE pays 0.00-0.04 on the same attempts (22 of 22, measured
2026-11-14).  752 deltas over 2909 attempts and not one `accepted`.

The three properties the task calls "done", plus the gates that keep them from regressing:

  * silence does not move an arm's mean (a missing judge writes NO reward);
  * a surrogate 0.7 with zero verified judges parks the pair, and one verified score above
    zero lifts the park;
  * `accepted` + verified marks the pair solved (and nothing else does).
"""

import json
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
import strategy  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = pathlib.Path(self.tmp.name)
        self._work, driver.WORK = driver.WORK, self.work
        (self.work / "artifacts").mkdir(parents=True, exist_ok=True)
        self.conn = store.connect(self.work / "t.db")
        self.lease = store.acquire_lease(self.conn, "lane-t", "target")
        assert self.lease is not None, "the test lane must own the journal"
        self._seq = 0

    def tearDown(self):
        driver.WORK = self._work
        self.conn.close()
        self.tmp.cleanup()

    def pair(self, key="s|m"):
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model,solved,attempts,best_input)"
            " VALUES(?,?,?,?,0,0,'inputs/x.txt')",
            (key, driver.BOARD_NAME, key.split("|")[0], "model"))
        self.conn.commit()

    def attempt(self, pair="s|m", *, reward=None, source=None, judge_status="unjudged",
                verdict=None, score=None, delta="arm", ts=None):
        # `time.time_ns()` is too coarse on Windows (15.6 ms ticks): a loop of inserts gets
        # one timestamp, so the id carries a counter instead.
        self._seq += 1
        aid = f"{pair}-{self._seq}"
        self.conn.execute(
            "INSERT INTO attempts(attempt_id,pair_id,board_profile,scenario,model,lane,"
            "started_at,delta,reward,reward_source,judge_status,verdict,score,state)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, pair, driver.BOARD_NAME, pair.split("|")[0], "model", "test",
             ts or time.time(), delta, reward, source, judge_status, verdict, score, "unjudged"))
        self.conn.commit()
        return aid


class SilenceTeachesNothingTest(Base):
    """A judge that did not speak must not become a number."""

    def test_no_judge_returns_no_reward(self):
        ev = strategy.IndependentEvaluator()
        got = ev.evaluate({"failure_class": "NONE_READY", "tool_invoked": True}, None)
        self.assertIsNone(got["reward"], "silence is not a reward")
        self.assertEqual(got["source"], "missing")
        self.assertEqual(got["confidence"], 0.0)
        # the local validator is still visible — as a DIAGNOSTIC
        self.assertIsNotNone(got["local_reward"])
        self.assertIsNone(got["judge_reward"])

    def test_silence_does_not_move_the_arms_mean(self):
        self.pair()
        self.attempt(reward=0.4, source="composite", judge_status="verified", verdict="rejected",
                     score=40)
        self.attempt()                                    # judge silent, no reward written
        self.attempt()
        stats = driver.delta_stats(self.conn, "s|m")
        self.assertEqual(stats["arm"]["n"], 1, "unjudged attempts are not observations")
        self.assertAlmostEqual(stats["arm"]["mean"], 0.4, places=6,
                               msg="a silent judge must not drag the mean toward zero")

    def test_a_missing_reward_does_not_enter_the_delta_aggregate(self):
        self.pair()
        store.bump_delta(self.conn, self.lease, "s|m", "arm", 0.6)
        row = self.conn.execute("SELECT n, sum_score FROM deltas WHERE pair_id='s|m'"
                                " AND delta='arm'").fetchone()
        before = (int(row["n"] or 0), int(row["sum_score"] or 0))
        store.bump_delta(self.conn, self.lease, "s|m", "arm", None)
        row = self.conn.execute("SELECT n, sum_score FROM deltas WHERE pair_id='s|m'"
                                " AND delta='arm'").fetchone()
        self.assertEqual((int(row["n"] or 0), int(row["sum_score"] or 0)), before,
                         "a None reward must not be counted as a zero score")


class JudgeIsTheTeacherTest(Base):
    def test_a_verified_zero_pays_through_the_judge_not_the_proxy(self):
        """The acceptance case: verified + score 0 + a loud proxy (0.70)."""
        ev = strategy.IndependentEvaluator()
        got = ev.evaluate({"failure_class": "NONE_READY", "tool_invoked": True},
                          {"status": "verified", "score": 0, "pcts": [], "verdict": "rejected"})
        self.assertIsNotNone(got["reward"], "a verified judge always produces a reward")
        self.assertIn(got["source"], ("composite", "judge"))
        self.assertLess(got["reward"], 0.1,
                        "the judge's 0.0 must dominate the proxy's 0.7 (composite = 0.1*proxy)")
        self.assertAlmostEqual(got["judge_reward"], 0.0, places=6)


class GiveUpReadsTheJudgeTest(Base):
    """Item 2: the park decision reads the verified judge, never the `reward` column."""

    def test_a_surrogate_07_never_saves_a_pair(self):
        self.pair("dead|model")
        now = time.time()
        for i in range(driver.GIVE_UP["min_probes"] + 2):
            self.attempt("dead|model", reward=0.7, source="local", judge_status="unjudged",
                         ts=now - 3600 + i)
        parked = driver._give_up_pairs(self.conn, ["dead|model"], now)
        self.assertEqual(parked, {"dead|model"},
                         "20 probes with a 0.7 surrogate and no judge must park the pair")

    def test_one_verified_score_above_zero_lifts_the_park(self):
        self.pair("alive|model")
        now = time.time()
        for i in range(driver.GIVE_UP["min_probes"] + 2):
            self.attempt("alive|model", reward=0.7, source="local", judge_status="unjudged",
                         ts=now - 3600 + i)
        self.attempt("alive|model", judge_status="verified", verdict="rejected", score=10,
                     ts=now - 60)
        parked = driver._give_up_pairs(self.conn, ["alive|model"], now)
        self.assertEqual(parked, set(), "one paid judge score lifts the park")

    def test_a_verified_zero_is_not_movement(self):
        self.pair("zero|model")
        now = time.time()
        for i in range(driver.GIVE_UP["min_probes"] + 2):
            self.attempt("zero|model", judge_status="verified", verdict="rejected", score=0,
                         ts=now - 3600 + i)
        parked = driver._give_up_pairs(self.conn, ["zero|model"], now)
        self.assertEqual(parked, {"zero|model"},
                         "hundreds of judge ZEROS are still no movement")

    def test_old_probes_outside_the_window_still_do_not_count(self):
        self.pair("dead|model")
        now = time.time()
        for i in range(driver.GIVE_UP["min_probes"] * 3):
            self.attempt("dead|model", judge_status="verified", score=0, ts=now - 5 * 86400 + i)
        self.assertEqual(driver._give_up_pairs(self.conn, ["dead|model"], now), set())


class SolvedFollowsAttemptsTest(Base):
    """Item 4: a flag without an accepted+verified attempt is not a solve."""

    def test_accepted_marks_the_pair_solved(self):
        self.pair("win|model")
        self.attempt("win|model", judge_status="verified", verdict="accepted", score=100,
                     reward=0.9, source="composite")
        out = driver.recompute_solved(self.conn)
        flag = self.conn.execute("SELECT solved FROM pairs WHERE id='win|model'").fetchone()[0]
        self.assertEqual(int(flag), 1)
        self.assertEqual(out["solved"], 1)

    def test_a_flag_without_such_an_attempt_is_cleared_with_a_reason(self):
        self.pair("fake|model")
        self.conn.execute("UPDATE pairs SET solved=1 WHERE id='fake|model'")
        self.attempt("fake|model", judge_status="verified", verdict="rejected", score=90,
                     reward=0.9, source="composite")
        out = driver.recompute_solved(self.conn)
        flag = self.conn.execute("SELECT solved FROM pairs WHERE id='fake|model'").fetchone()[0]
        self.assertEqual(int(flag), 0, "a rejected judge verdict is not a solve")
        self.assertEqual(out["changed"][0]["pair"], "fake|model")
        ev = self.conn.execute("SELECT payload FROM events WHERE kind='solved_recomputed'"
                               " ORDER BY rowid DESC LIMIT 1").fetchone()
        self.assertIsNotNone(ev, "the reason for clearing a flag must be recorded")
        self.assertIn("verified_accepted", ev["payload"])

    def test_seeding_never_invents_a_solve(self):
        """`seed` must not carry `solved` over from the bookkeeping file."""
        src = (HERE.parent / "driver.py").read_text(encoding="utf-8")
        self.assertIn("solved = 0", src,
                      "the seed must write 0 and let recompute_solved decide")


class DeltaGateTest(Base):
    """Item 3: no new delta until the pair has two verified judges."""

    def test_a_fresh_pair_still_gets_its_first_probe(self):
        self.pair("fresh|model")
        arms, source = driver.choosable_arms(self.conn, "fresh|model", ["a", "b", "c"])
        self.assertEqual(arms, ["a", "b", "c"])
        self.assertIn("fresh pair", source)

    def test_without_two_verified_judges_only_probed_deltas_compete(self):
        self.pair("gated|model")
        self.attempt("gated|model", delta="a", reward=0.7, source="local",
                     judge_status="unjudged")
        arms, source = driver.choosable_arms(self.conn, "gated|model", ["a", "b", "c"])
        self.assertEqual(arms, ["a"], "a new delta is not proposed under a silent judge")
        self.assertIn("gate", source)

    def test_two_verified_judges_reopen_the_catalog(self):
        self.pair("open|model")
        self.attempt("open|model", delta="a", judge_status="verified", verdict="rejected",
                     score=0, reward=0.3, source="composite")
        self.attempt("open|model", delta="a", judge_status="verified", verdict="rejected",
                     score=20, reward=0.4, source="composite")
        arms, source = driver.choosable_arms(self.conn, "open|model", ["a", "b", "c"])
        self.assertEqual(sorted(arms), ["a", "b", "c"])
        self.assertEqual(source, "verified means")

    def test_the_verified_ranking_ignores_the_surrogate(self):
        self.pair("rank|model")
        self.attempt("rank|model", delta="a", reward=0.9, source="local",
                     judge_status="unjudged")            # a loud surrogate, no judge
        self.attempt("rank|model", delta="b", judge_status="verified", verdict="rejected",
                     score=10, reward=0.2, source="composite")
        stats = driver.verified_delta_stats(self.conn, "rank|model")
        self.assertEqual(list(stats), ["b"], "only a verified delta has a verified mean")
        self.assertAlmostEqual(stats["b"]["mean"], 0.1, places=4)

    def test_generated_frames_wait_for_the_same_gate(self):
        self.pair("gen|model")
        self.assertIsNone(driver.make_generated_variant(self.conn, self.lease, "gen|model",
                                                        __import__("random").Random(1), []),
                          "a composed frame is a new delta and waits for two judges")


if __name__ == "__main__":
    unittest.main(verbosity=2)
