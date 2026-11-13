"""Strategy Engine 2.0 tests (offline, no browser)."""
import pathlib
import random
import statistics
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import strategy  # noqa: E402
import strategy_bench  # noqa: E402


class RewardTest(unittest.TestCase):
    def test_local_reward_grades_tool_calls_above_refusals(self):
        called = strategy.local_reward({"failure_class": "NONE_READY", "tool_invoked": True})[0]
        refused = strategy.local_reward({"failure_class": "A_TOOL_NOT_CALLED",
                                         "refusal_category": "category_block"})[0]
        self.assertIsNotNone(called)
        self.assertIsNotNone(refused)
        self.assertGreater(called, refused)
        for value in (called, refused):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_refusals_are_distinguishable_not_all_zero(self):
        """56% of probes are refusals; collapsing them all to 0.0 left the
        selector blind inside that band (measured: 118 of 400 probes at exactly
        0.0)."""
        block = strategy.local_reward({"failure_class": "A_TOOL_NOT_CALLED",
                                       "refusal_category": "category_block"})[0] or 0.0
        engaged = strategy.local_reward({"failure_class": "A_TOOL_NOT_CALLED",
                                         "refusal_category": "invalid_input"})[0] or 0.0
        self.assertGreater(engaged, block)
        self.assertGreater(block, 0.0, "a flat refusal is still evidence of a refusal")

    def test_our_own_plumbing_faults_are_not_rewards(self):
        """A probe our fill step dropped says nothing about the arm."""
        self.assertEqual(strategy.harness_fault({"probe_ok": False}), "probe_not_landed")
        self.assertEqual(strategy.harness_fault({"tool_invoked": True, "fill_ok": False}),
                         "toolcall_lost_in_fill")
        self.assertEqual(strategy.harness_fault({"lost_send_suspect": True}), "lost_send")
        self.assertIsNone(strategy.harness_fault({"probe_ok": True, "fill_ok": True,
                                                  "sent_ok": True}))
        for signals in ({"probe_ok": False}, {"tool_invoked": True, "fill_ok": False}):
            self.assertIsNone(strategy.local_reward(signals)[0])

    def test_invalid_measurements_are_not_rewards(self):
        self.assertIsNone(strategy.local_reward({"invalid": True})[0])
        self.assertIsNone(strategy.local_reward({"mock_ok": False})[0])
        self.assertIsNone(strategy.local_reward({"lost_send_suspect": True})[0])

    def test_judge_reward_is_normalised_and_only_for_verified(self):
        self.assertEqual(strategy.judge_reward({"status": "verified", "pcts": [0, 100]})[0], 0.5)
        self.assertIsNone(strategy.judge_reward({"status": "pending", "pcts": [100]})[0])
        self.assertEqual(strategy.judge_reward({"status": "verified", "pcts": [90] * 4})[0], 0.9)

    def test_composite_prefers_agreement_and_records_disagreement(self):
        ev = strategy.IndependentEvaluator()
        a = ev.evaluate({"failure_class": "NONE_READY"},
                        {"status": "verified", "pcts": [80], "verdict": "rejected"})
        self.assertEqual(a["source"], "composite")
        self.assertIsNotNone(a["disagreement"])
        b = ev.evaluate({"failure_class": "A_TOOL_NOT_CALLED"}, None)
        self.assertEqual(b["source"], "local")
        self.assertIsNone(b["disagreement"])


class SchedulerTest(unittest.TestCase):
    def test_unexplored_arms_are_random_not_lexicographic(self):
        arms = ["append_a", "append_b", "append_c", "append_d"]
        picks = {strategy.AdaptiveScheduler("ucb_improved").choose(
            arms, {}, rng=random.Random(seed)) for seed in range(12)}
        self.assertGreater(len(picks), 2, picks)
        self.assertNotEqual(picks, {"append_d"})

    def test_ucb_prefers_higher_mean_but_keeps_exploring(self):
        stats = {"append_a": {"n": 20, "mean": 0.8, "sd": 0.05, "var": 0.0, "wins": 18},
                 "append_b": {"n": 20, "mean": 0.2, "sd": 0.05, "var": 0.0, "wins": 3}}
        sch = strategy.AdaptiveScheduler("ucb_improved")
        picks = [sch.choose(list(stats), stats, rng=random.Random(s)) for s in range(50)]
        self.assertGreater(picks.count("append_a"), 45)

    def test_legacy_policy_is_max_based_and_deterministic(self):
        # the pre-v4 selector: one lucky maximum dominates the mean
        stats = {"a": {"n": 20, "mean": 0.2, "sd": 0.4, "var": 0.16, "max": 95, "wins": 4},
                 "b": {"n": 20, "mean": 0.5, "sd": 0.1, "var": 0.01, "max": 60, "wins": 10}}
        picks = {strategy_bench.legacy_pick(["a", "b"], stats, random.Random(s))
                 for s in range(10)}
        self.assertEqual(picks, {"a"})
        # the v4 policy judges by mean and spread
        sch = strategy.AdaptiveScheduler("ucb_improved")
        picks2 = [sch.choose(["a", "b"], stats, rng=random.Random(s)) for s in range(30)]
        self.assertGreater(picks2.count("b"), 25)

    def test_contextual_pooling_shrinks_towards_the_scenario(self):
        sch = strategy.AdaptiveScheduler("contextual_ts")
        ctx = {"arm": {"n": 1, "mean": 0.05, "sd": 0.0, "var": 0.0, "wins": 0}}
        pool = {"arm": {"n": 40, "mean": 0.9, "sd": 0.1, "var": 0.01, "wins": 36}}
        blended = sch._pooled(ctx, pool, "arm")
        self.assertGreater(blended["mean"], 0.05)
        self.assertLess(blended["mean"], 0.9)

    def test_policies_are_all_selectable(self):
        stats = {"a": {"n": 3, "mean": 0.4, "sd": 0.2, "var": 0.04, "wins": 1},
                 "b": {"n": 3, "mean": 0.3, "sd": 0.2, "var": 0.04, "wins": 1}}
        for pol in strategy.POLICIES:
            self.assertIn(strategy.AdaptiveScheduler(pol).choose(["a", "b"], stats), ("a", "b"))
        with self.assertRaises(ValueError):
            strategy.AdaptiveScheduler("nope")

    def test_hierarchical_beta_shrinks_to_the_parent_and_keeps_exploring(self):
        """Bayesian invariants: a single lucky win is shrunk, not believed."""
        sch = strategy.AdaptiveScheduler("thompson")
        lucky = {"n": 1, "mean": 1.0, "sd": 0.0, "var": 0.0, "wins": 1}
        solid = {"n": 40, "mean": 0.5, "sd": 0.5, "var": 0.25, "wins": 20}
        stats = {"lucky": dict(lucky), "solid": dict(solid)}
        # 1) the posterior mean of the 1/1 arm is pulled towards the parent rate:
        #    it must sit far below 1.0, not equal to the raw rate
        draws = [sch._sample_beta_post(stats, None, "lucky", random.Random(s))
                 for s in range(2000)]
        mean_draw = sum(draws) / len(draws)
        self.assertLess(mean_draw, 0.75, "1/1 was taken at face value")
        self.assertGreater(mean_draw, 0.3, "the observation was ignored entirely")
        # 2) the real Bayesian signature is UNCERTAINTY, not a fixed winner:
        #    the low-evidence arm samples wider, and both arms get pulled
        spread = {}
        for arm in ("lucky", "solid"):
            draws = [sch._sample_beta_post(stats, None, arm, random.Random(s))
                     for s in range(2000)]
            spread[arm] = statistics.pstdev(draws)
        self.assertGreater(spread["lucky"], spread["solid"],
                           "the 1-observation arm is not treated as less certain")
        wins = {"lucky": 0, "solid": 0}
        for seed in range(600):
            wins[sch.choose(["lucky", "solid"], stats, rng=random.Random(seed))] += 1
        self.assertGreater(wins["lucky"], 0)
        self.assertGreater(wins["solid"], 0)
        # 3) the parent rate moves the posterior of an arm with no data of its own
        cold = {"n": 0, "mean": 0.0, "sd": 0.0, "var": 0.0, "wins": 0}
        weak_parent = {"arm": {"n": 50, "wins": 5, "mean": 0.1, "sd": 0.3, "var": 0.1}}
        strong_parent = {"arm": {"n": 50, "wins": 45, "mean": 0.9, "sd": 0.3, "var": 0.1}}
        lo = sum(sch._sample_beta_post({"arm": cold}, weak_parent, "arm",
                                       random.Random(s)) for s in range(500)) / 500
        hi = sum(sch._sample_beta_post({"arm": cold}, strong_parent, "arm",
                                       random.Random(s)) for s in range(500)) / 500
        self.assertLess(lo, hi, "the scenario parent rate is not used")


class MemoryTest(unittest.TestCase):
    def test_observe_pick_report_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            mem = strategy.ExperienceMemory(pathlib.Path(td) / "m.db")
            eng = strategy.StrategyEngine(["append_a", "append_b"], policy="ucb_improved",
                                          memory=mem, seed=5)
            ctx = strategy.context_key(board="b", scenario="s", model="m")
            eng.observe(context=ctx, arm="append_a", signals={"failure_class": "NONE_READY"},
                        scenario="s", model="m", board="b")
            eng.observe(context=ctx, arm="append_b",
                        signals={"failure_class": "A_TOOL_NOT_CALLED"}, scenario="s", model="m")
            report = eng.report(context=ctx)
            self.assertEqual(report["experiments"], 2)
            self.assertEqual(report["by_arm"]["append_a"]["n"], 1)
            self.assertGreater(report["by_arm"]["append_a"]["mean"],
                               report["by_arm"]["append_b"]["mean"])
            pick = eng.pick(context=ctx)
            self.assertIn(pick, ("append_a", "append_b"))
            # a judge disagreement is archived, not averaged away
            eng.observe(context=ctx, arm="append_a", signals={"failure_class": "A_TOOL_NOT_CALLED"},
                        judge={"status": "verified", "pcts": [100], "verdict": "accepted"})
            n = mem.conn.execute("SELECT COUNT(*) AS c FROM disagreements").fetchone()["c"]
            self.assertEqual(n, 1)
            self.assertEqual(mem.count(family="carrier_append"), 3)
            mem.close()

    def test_arm_family_generalises_wording(self):
        self.assertEqual(strategy.arm_family("append_discount_structure"),
                         strategy.arm_family("append_face_value"))
        self.assertNotEqual(strategy.arm_family("prepend_audit"),
                            strategy.arm_family("append_email"))

    def test_successive_halving_drops_the_bottom_half(self):
        stats = {a: {"mean": m} for a, m in (("a", 0.9), ("b", 0.5), ("c", 0.2), ("d", 0.1))}
        keep = strategy.successive_halving_keep(stats)
        self.assertEqual(keep, ["a", "b"])


class BenchTest(unittest.TestCase):
    def test_delta_extraction_from_input_name(self):
        self.assertEqual(strategy_bench.delta_of_input(
            r"inputs\lbp-negq-loop2-append_nonce-1794574739-765.txt"), "append_nonce")
        self.assertIsNone(strategy_bench.delta_of_input("inputs/lbp-negq-base.txt"))

    def test_replay_separates_train_from_test_and_reports_cis(self):
        history = []
        for ctx_i in range(2):
            for i in range(40):
                arm = "a" if i % 2 else "b"
                history.append({"ts": f"2026-11-13T00:{i:02d}:00", "context": f"s{ctx_i}|m",
                                "scenario": f"s{ctx_i}", "model": "m", "arm": arm,
                                "reward": 0.9 if arm == "a" else 0.1, "confidence": 0.5,
                                "valid": True})
        res = strategy_bench.run_policy(history, "ucb_improved", budget=40, seed=1)
        self.assertGreater(res["mean_reward"], 0.5)
        self.assertIn("success_ci", res)
        self.assertLessEqual(res["success_ci"][0], res["success_ci"][1])
        self.assertEqual(res["good_arm_rate"], 1.0)
        legacy = strategy_bench.run_policy(history, "current", budget=40, seed=1)
        self.assertIn("mean_reward", legacy)


if __name__ == "__main__":
    unittest.main()
