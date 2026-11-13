#!/usr/bin/env python3
"""Offline benchmark: does the new selector actually beat the old one?

Advice 2026-11-13 (#6 and #8): a new search algorithm is only an improvement if
it is measured against the old one on the same data, with the same budget, with
several seeds, on a held-out split, with confidence intervals.

What is compared (the five implementations the advice asks for):

  A  current        — the pre-v4 selector: max-based UCB, c=45 on raw percents,
                      unexplored arms resolved by descending sort (so the
                      alphabetically last delta goes first, for every pair)
  B  random         — uniform random arm
  C  ucb_improved   — mean + spread UCB on the NORMALISED reward
  D  thompson       — Beta-Bernoulli Thompson sampling on binarised success
  E  contextual_ts  — Thompson sampling with pooling across the models of a
                      scenario + a novelty bonus (Diversity Archive)

Data source: the real run ledger `datasets/lbp/repeats.jsonl` (1839 probes,
~11 days of work).  The arm of a probe is the delta in its input filename; the
reward comes from the INDEPENDENT local validator (`strategy.local_reward`),
because on this arena almost no probe ever reaches a judge verdict.

Offline evaluation is a *logged* bandit replay: the reward of a chosen arm is
what the log recorded for that (context, arm) pair.  Pulls with no logged
sample are counted as unobserved (zero reward, flagged), and the report also
prints the "hit rate" so the reader can see how much of the score is anchored
in real evidence.  An oracle over the same arm space is printed for scale.

Usage:
  python3 harness/strategy_bench.py                 # full comparison, 5 seeds
  python3 harness/strategy_bench.py --budget 200 --seeds 9 --json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import re
import statistics
import sys
import time
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import strategy  # noqa: E402
from strategy import (AdaptiveScheduler, SUCCESS_THRESHOLD, _wilson, arm_family,  # noqa: E402
                      local_reward)

REPEATS = WORK / "datasets" / "lbp" / "repeats.jsonl"
OUT_JSON = WORK / "artifacts" / "strategy-bench.json"

_DELTA_RE = re.compile(r"loop\d*-([A-Za-z0-9_.]+?)-\d{6,}-\d+\.txt$")


def delta_of_input(path: str) -> str | None:
    m = _DELTA_RE.search(str(path or "").replace("\\", "/"))
    return m.group(1) if m else None


def load_history(path=REPEATS, *, arms: str = "catalog",
                 min_probes_per_context: int = 0) -> list[dict]:
    """Real probes with an arm and an independently validated reward.

    `arms="catalog"` (default) restricts the arm space to the fixed delta
    catalog, so the comparison stays a comparison of POLICIES over a stable
    space.  Leaving it at "all" folds in the generated frames, which are
    one-shot by construction: a frame tried once has no payoff in the held-out
    half, so the metric collapses (measured 2026-11-13: 132 arms, every policy
    at ~0.006).  The generated arms are a different question — whether
    generation pays off — and are measured by generator_bench.py / live rewards.
    """
    import generation
    out = []
    excluded = 0
    p = pathlib.Path(path)
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        arm = delta_of_input(row.get("input"))
        if not arm:
            continue
        if arms == "catalog" and arm not in generation.DELTAS:
            excluded += 1
            continue
        reward, conf = local_reward(row)
        out.append({
            "ts": row.get("ts"), "context": f"{row.get('scenario')}|{row.get('model')}",
            "scenario": row.get("scenario"), "model": row.get("model"),
            "arm": arm, "reward": reward, "confidence": conf,
            "valid": reward is not None,
        })
    if excluded:
        print(f"[bench] arm space = catalog; {excluded} probes on generated/unknown "
              f"arms excluded (use --arms all to include them)")
    if min_probes_per_context:
        by_ctx = defaultdict(list)
        for row in out:
            by_ctx[row["context"]].append(row)
        keep = {c for c, rows in by_ctx.items() if len(rows) >= min_probes_per_context}
        dropped = len(by_ctx) - len(keep)
        out = [row for row in out if row["context"] in keep]
        if dropped:
            print(f"[bench] context filter: {dropped} contexts with <"
                  f"{min_probes_per_context} catalog probes dropped (too little history "
                  f"to learn from; the comparison would be noise)")
    return out


# --------------------------------------------------------------------------
# baselines
# --------------------------------------------------------------------------
def legacy_pick(arms, stats, rng: random.Random, *, c: float = 45.0) -> str:
    """The PRE-v4 selector, reproduced faithfully for comparison (A).

    max-based UCB on the raw percent sum, `1e9` for unexplored arms and a
    descending sort — which resolves ties alphabetically, last first.
    """
    total = sum(int(s["n"]) for s in stats.values()) + 1
    scored = []
    for a in arms:
        s = stats.get(a)
        if not s or s["n"] == 0:
            scored.append((1e9, a))
        else:
            scored.append((s["max"] + c * math.sqrt(2.0 * math.log(total) / s["n"]), a))
    scored.sort(reverse=True)
    return scored[0][1]


def policy_pick(policy: str, arms, stats, rng: random.Random,
                pooled: dict | None = None, prior_k: float | None = None) -> str:
    if policy == "current":
        return legacy_pick(arms, stats, rng)
    kw: dict[str, float | int] = {"seed": rng.randint(0, 10**6)}
    if prior_k is not None:
        kw["prior_k"] = float(prior_k)
    sch = AdaptiveScheduler(policy, **kw)
    return sch.choose(arms, _norm_stats(stats), rng=rng,
                      pooled_stats=_norm_stats(pooled) if pooled else None)


def _norm_stats(stats: dict) -> dict:
    """Accept both the bench's raw dicts and scheduler stats dicts."""
    out = {}
    for a, s in stats.items():
        n = int(s.get("n", 0))
        mean = float(s.get("mean", 0.0))
        out[a] = {"n": n, "mean": mean, "sd": float(s.get("sd", 0.0)),
                  "var": float(s.get("var", 0.0)),
                  "wins": int(s.get("wins", 0))}
    return out


def update(stats: dict, arm: str, reward: float | None, raw_percent: float = 0.0) -> None:
    s = stats.setdefault(arm, {"n": 0, "sum": 0.0, "sumsq": 0.0, "max": -1.0,
                               "wins": 0, "reward": None})
    s["n"] += 1
    r = 0.0 if reward is None else float(reward)
    s["sum"] += r
    s["sumsq"] += r * r
    s["max"] = max(s["max"], raw_percent)
    if reward is not None and reward >= SUCCESS_THRESHOLD:
        s["wins"] += 1
    mean = s["sum"] / s["n"]
    var = max(0.0, s["sumsq"] / s["n"] - mean * mean)
    s["mean"], s["sd"], s["var"] = mean, math.sqrt(var), var
    s["reward"] = mean


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------
def run_policy(history: list[dict], policy: str, *, budget: int, seed: int,
               split: float = 0.7, arms: list[str] | None = None,
               prior_k: float | None = None) -> dict:
    """Train on the first `split` of the log, then replay decisions on the rest.

    Payoffs are estimated per (context, arm) from the logged rewards: the train
    half builds the statistics the policy starts from, the test half supplies
    the payoff of every pull.  This is a stationary-bandit reading of a logged
    bandit — the same assumption UCB/Thompson themselves make — and it is the
    only reading that can compare arms the old selector never tried.
    """
    arms = arms or sorted({h["arm"] for h in history})
    by_ctx: dict[str, list[dict]] = defaultdict(list)
    for h in history:
        by_ctx[h["context"]].append(h)

    train: dict[str, list[dict]] = {}
    test: dict[str, list[dict]] = {}
    for ctx, rows in by_ctx.items():
        rows = sorted(rows, key=lambda r: str(r.get("ts") or ""))
        cut = max(1, int(len(rows) * split))
        train[ctx], test[ctx] = rows[:cut], rows[cut:] or rows[-1:]

    def payoff(rows) -> dict[tuple[str, str], tuple[float, int]]:
        acc: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in rows:
            if r["reward"] is not None:
                acc[(r["context"], r["arm"])].append(float(r["reward"]))
        return {k: (statistics.fmean(v), len(v)) for k, v in acc.items()}

    train_pay = payoff([r for rows in train.values() for r in rows])
    test_pay = payoff([r for rows in test.values() for r in rows])

    # the statistics the policy starts from (train half only)
    stats: dict[str, dict] = {}
    for ctx, rows in train.items():
        st: dict = {}
        for r in rows:
            update(st, r["arm"], r["reward"])
        stats[ctx] = st
    # scenario-level pool: what the OTHER models of this scenario already showed
    scen_stats: dict[str, dict] = {}
    for ctx, st in stats.items():
        scene = ctx.split("|")[0]
        pool = scen_stats.setdefault(scene, {})
        for arm, s in st.items():
            tgt = pool.setdefault(arm, {"n": 0, "sum": 0.0, "sumsq": 0.0, "max": -1.0,
                                        "wins": 0, "reward": None})
            tgt["n"] += s["n"]
            tgt["sum"] += s["sum"]
            tgt["sumsq"] += s["sumsq"]
            tgt["wins"] += s["wins"]
            tgt["max"] = max(tgt["max"], s["max"])
            mean = tgt["sum"] / tgt["n"] if tgt["n"] else 0.0
            tgt["mean"] = mean
            tgt["var"] = max(0.0, tgt["sumsq"] / tgt["n"] - mean * mean) if tgt["n"] else 0.0
            tgt["sd"] = math.sqrt(tgt["var"])

    rng = random.Random(seed)
    contexts = sorted(test)
    if not contexts:
        return {"policy": policy, "error": "no evaluation window"}
    best_by_ctx = {}
    for ctx in contexts:
        cand = [(v[0], a) for (c, a), v in test_pay.items() if c == ctx]
        best_by_ctx[ctx] = max(cand)[0] if cand else 0.0

    picks, hits, rewards, arms_used, fams_used = [], 0, [], set(), set()
    # ranking of arms per context by their test-half payoff (the target the
    # policy is trying to find; used for the "did it find a good arm" metrics)
    ranked_by_ctx = {ctx: [a for _, a in sorted(
        ((v[0], a) for (c, a), v in test_pay.items() if c == ctx), reverse=True)]
        for ctx in contexts}
    good_hits = top3_hits = 0
    for i in range(int(budget)):
        ctx = contexts[i % len(contexts)]
        st = stats.setdefault(ctx, {})
        scene = ctx.split("|")[0]
        pool = scen_stats.setdefault(scene, {})
        arm = policy_pick(policy, arms, st, rng, pooled=pool, prior_k=prior_k)
        picks.append(arm)
        arms_used.add(arm)
        fams_used.add(arm_family(arm))
        known = test_pay.get((ctx, arm))
        if known is None:
            reward = 0.0
        else:
            reward = known[0]
            hits += 1
        ranked = ranked_by_ctx.get(ctx) or []
        if ranked and reward >= 0.8 * test_pay.get((ctx, ranked[0]), (0.0, 0))[0]:
            good_hits += 1
        if arm in ranked[:3]:
            top3_hits += 1
        rewards.append(reward)
        # the policy learns from the TRAIN payoff of that pair (no peeking at test)
        train_reward = (train_pay.get((ctx, arm)) or (None, 0))[0]
        update(st, arm, train_reward)
        update(pool, arm, train_reward)   # keep the scenario pool in step
    n = len(rewards)
    total = sum(rewards)
    wins = sum(1 for r in rewards if r >= SUCCESS_THRESHOLD)
    lo, hi = _wilson(wins, n)
    oracle = sum(best_by_ctx[c] for c in contexts) / len(contexts)
    return {
        "policy": policy, "budget": n, "seed": seed,
        "total_reward": round(total, 4),
        "mean_reward": round(total / n, 4) if n else None,
        "sample_efficiency": round(total / n, 4) if n else None,
        "hit_rate": round(hits / n, 4) if n else None,
        "good_arm_rate": round(good_hits / n, 4) if n else None,
        "top3_rate": round(top3_hits / n, 4) if n else None,
        "coverage_arms": len(arms_used), "coverage_families": len(fams_used),
        "success_rate": round(wins / n, 4) if n else None,
        "success_ci": [round(lo, 4), round(hi, 4)],
        "ci_width": round(hi - lo, 4),
        "oracle_reward": round(oracle, 4),
        "regret": round(oracle - (total / n if n else 0.0), 4),
        "picks": picks,
    }


def aggregate(runs: list[dict]) -> dict:
    ok = [r for r in runs if "mean_reward" in r]
    if not ok:
        return {}
    def stat(key):
        vals = [r[key] for r in ok if r.get(key) is not None]
        if not vals:
            return None
        mean = statistics.fmean(vals)
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        half = 1.96 * sd / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
        return {"mean": round(mean, 4), "sd": round(sd, 4),
                "ci95": [round(mean - half, 4), round(mean + half, 4)]}
    return {
        "policy": ok[0]["policy"], "seeds": len(ok),
        "mean_reward": stat("mean_reward"),
        "hit_rate": stat("hit_rate"),
        "success_rate": stat("success_rate"),
        "good_arm_rate": stat("good_arm_rate"),
        "top3_rate": stat("top3_rate"),
        "coverage_arms": stat("coverage_arms"),
        "coverage_families": stat("coverage_families"),
        "ci_width": stat("ci_width"),
        "regret": stat("regret"),
        "oracle_reward": round(statistics.fmean([r["oracle_reward"] for r in ok]), 4),
    }


def compare(history: list[dict], *, budget: int = 200, seeds: int = 5,
            split: float = 0.7, budget_sweep: tuple = ()) -> dict:
    policies = ["current", "random", "ucb_improved", "thompson", "contextual_ts"]
    arms = sorted({h["arm"] for h in history})
    per_policy = {}
    for pol in policies:
        runs = [run_policy(history, pol, budget=budget, seed=1000 + s, split=split, arms=arms)
                for s in range(seeds)]
        per_policy[pol] = {"runs": runs, "aggregate": aggregate(runs)}
    ranked = sorted(
        ({"policy": p, **v["aggregate"]} for p, v in per_policy.items() if v["aggregate"]),
        key=lambda d: -(d.get("mean_reward") or {}).get("mean", 0.0))
    best = ranked[0]["policy"] if ranked else None
    cur = per_policy["current"]["aggregate"].get("mean_reward", {}).get("mean") if ranked else None
    win = per_policy[best]["aggregate"].get("mean_reward", {}).get("mean") if best else None
    sweep = {}
    for b in (budget_sweep or ()):
        row = {}
        for pol in policies:
            runs = [run_policy(history, pol, budget=int(b), seed=2000 + s, split=split, arms=arms)
                    for s in range(max(3, seeds // 2))]
            row[pol] = (aggregate(runs).get("mean_reward") or {}).get("mean")
        sweep[str(b)] = row
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": {"probes": len(history),
                 "contexts": len({h["context"] for h in history}),
                 "arms": len(arms),
                 "valid_rewards": sum(1 for h in history if h["valid"]),
                 "source": str(REPEATS.relative_to(WORK))},
        "protocol": {"budget": budget, "seeds": seeds, "train_split": split,
                     "reward": "independent local validator (strategy.local_reward)",
                     "arms": arms, "budget_sweep": list(budget_sweep or ())},
        "policies": {p: v["aggregate"] for p, v in per_policy.items()},
        "ranking": ranked,
        "budget_sweep": sweep,
        "winner": best,
        "improvement_vs_current": (None if (cur is None or win is None)
                                   else round((win - cur) / cur, 4) if cur else None),
        "raw": {p: v["runs"] for p, v in per_policy.items()},
    }


def tune_prior(history: list[dict], *, policy: str = "contextual_ts", betas=(1.0, 2.0, 6.0, 12.0, 25.0),
               budget: int = 300, seeds: int = 5, split: float = 0.7) -> dict:
    """Is the Bayesian policy losing because the PRIOR is mis-tuned?

    The hierarchical Beta has one free knob (prior_k: how many pseudo-observations
    the scenario parent contributes).  Sweeping it turns "TS does not win" from an
    opinion into a measured statement about the algorithm and its prior.
    """
    import strategy as strategy_mod  # noqa: F401  (policies come from the live module)
    arms = sorted({h["arm"] for h in history})
    out = {}
    for beta in betas:
        rewards, successes, good = [], [], []
        for s in range(seeds):
            run = run_policy(history, policy, budget=budget, seed=3000 + s,
                             split=split, arms=arms, prior_k=beta)
            if run.get("mean_reward") is not None:
                rewards.append(run["mean_reward"])
                successes.append(run["success_rate"])
                good.append(run["good_arm_rate"])
        if rewards:
            out[str(beta)] = {
                "mean_reward": round(statistics.fmean(rewards), 4),
                "success_rate": round(statistics.fmean(successes), 4),
                "good_arm_rate": round(statistics.fmean(good), 4),
                "seeds": len(rewards),
            }
    best = max(out, key=lambda k: out[k]["mean_reward"]) if out else None
    return {"policy": policy, "budget": budget, "seeds": seeds, "by_prior_k": out, "best": best}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--split", type=float, default=0.7)
    ap.add_argument("--history", default=str(REPEATS))
    ap.add_argument("--arms", default="catalog", choices=("catalog", "all"),
                    help="catalog = the fixed delta space (stable policy comparison); "
                         "all = include generated frames (one-shot, unmeasurable offline)")
    ap.add_argument("--min-probes-per-context", type=int, default=20,
                    help="keep only contexts with at least this many catalog probes "
                         "(default 20; the workspace now has 52 contexts and most are "
                         "too young to compare policies on)")
    ap.add_argument("--out", default=str(OUT_JSON))
    ap.add_argument("--json", action="store_true", help="print the whole report")
    ap.add_argument("--sweep", default="", help="comma-separated budgets for the sweep, e.g. 100,300,1000")
    ap.add_argument("--tune", default="", help="comma-separated prior_k values to sweep for the "
                                               "Bayesian policies, e.g. 1,2,6,12,25")
    ap.add_argument("--tune-seeds", type=int, default=0,
                    help="seeds for the prior sweep (default: half of --seeds)")
    a = ap.parse_args()
    history = load_history(a.history, arms=a.arms,
                           min_probes_per_context=a.min_probes_per_context)
    if not history:
        print(json.dumps({"error": "no history", "path": a.history}))
        return 1
    sweep = tuple(int(x) for x in a.sweep.split(",") if x.strip())
    report = compare(history, budget=a.budget, seeds=a.seeds, split=a.split,
                     budget_sweep=sweep)
    if a.tune:
        betas = tuple(float(x) for x in a.tune.split(",") if x.strip())
        tune_seeds = a.tune_seeds or max(3, a.seeds // 2)
        report["tuning"] = {
            "contextual_ts": tune_prior(history, policy="contextual_ts", betas=betas,
                                        budget=a.budget, seeds=tune_seeds),
            "thompson": tune_prior(history, policy="thompson", betas=betas,
                                   budget=a.budget, seeds=tune_seeds),
        }
    pathlib.Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    d = report["data"]
    print(f"history: {d['probes']} probes / {d['contexts']} contexts / {d['arms']} arms "
          f"/ {d['valid_rewards']} valid rewards")
    print(f"protocol: budget={report['protocol']['budget']} seeds={report['protocol']['seeds']} "
          f"train_split={report['protocol']['train_split']}")
    print(f"{'policy':<15}{'mean_reward':>13}{'ci95':>22}{'success':>9}"
          f"{'good_arm':>10}{'top3':>7}{'hit':>7}{'arms':>6}{'regret':>9}")
    for row in report["ranking"]:
        mr = row.get("mean_reward") or {}
        hr = row.get("hit_rate") or {}
        sr = row.get("success_rate") or {}
        ga = row.get("good_arm_rate") or {}
        t3 = row.get("top3_rate") or {}
        print(f"{row['policy']:<15}{mr.get('mean', 0):>13.4f}"
              f"{str(mr.get('ci95')):>22}{sr.get('mean', 0):>9.3f}"
              f"{ga.get('mean', 0):>10.3f}{t3.get('mean', 0):>7.3f}"
              f"{hr.get('mean', 0):>7.3f}"
              f"{(row.get('coverage_arms') or {}).get('mean', 0):>6.1f}"
              f"{(row.get('regret') or {}).get('mean', 0):>9.4f}")
    print(f"oracle (best arm per context, test half): "
          f"{report['ranking'][0].get('oracle_reward')}")
    if report.get("budget_sweep"):
        print("\nbudget sweep (mean reward):")
        pols = ["current", "random", "ucb_improved", "thompson", "contextual_ts"]
        print(f"{'budget':>8}" + "".join(f"{p:>15}" for p in pols))
        for b, row in report["budget_sweep"].items():
            print(f"{b:>8}" + "".join(f"{(row.get(p) or 0):>15.4f}" for p in pols))
    print(f"winner: {report['winner']}  improvement_vs_current: "
          f"{report['improvement_vs_current']}")
    print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
