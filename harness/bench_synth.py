"""Synthetic non-stationarity bench: is decaying old observations worth it?

The advice (2026-11-13 #7) said: the world changes, so old observations should
weigh less — but a decay constant is a hyper-parameter, and the only honest way to
justify one is to show (a) it helps when the world drifts and (b) it does NOT hurt
when the world is stationary.  The logged-replay bench cannot answer either: our
own log is a single stretch of history, and "what if the payoffs had changed" is not
in it.

So this module simulates the environments instead.  Three worlds, deliberately
small and readable:

  stationary — every arm keeps its own success probability forever.
  rotate     — every `period` pulls the payoffs rotate by one arm: the arm that was
               best becomes second-best, and a fresh arm becomes best.  Nothing is
               learnable except "the ranking moved", which is exactly the point.
  window     — one arm is good for a while, then its window closes and another
               opens (the "the platform patched that mock" case).

What is measured:
  payoff      — successes / pulls (did we pick paying arms?)
  best_share  — fraction of pulls on the arm that was ACTUALLY best at that step
                (did we notice the world moved?)
  regret      — mean shortfall against the per-step best arm

Usage: python3 harness/bench_synth.py [--budget 2000] [--seeds 6] [--json]
"""

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from strategy import SUCCESS_THRESHOLD, AdaptiveScheduler, ArmAcc  # noqa: E402

ARMS = [f"arm{i:02d}" for i in range(12)]


# --------------------------------------------------------------------------
# worlds
# --------------------------------------------------------------------------
def p_stationary(arm_i: int, step: int) -> float:
    # a spread of mostly-poor arms with three usable ones: the regime our board is in
    table = [0.30, 0.24, 0.18, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02, 0.02, 0.01]
    return table[arm_i]


def p_rotate(arm_i: int, step: int, period: int = 150) -> float:
    table = [0.30, 0.24, 0.18, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02, 0.02, 0.01]
    shift = (step // period) % len(table)
    return table[(arm_i - shift) % len(table)]


def p_window(arm_i: int, step: int, period: int = 700) -> float:
    """Arm 0 is the winner, then the window moves to arm 3, then to arm 7."""
    windows = [(0, 0.30), (3, 0.26), (7, 0.22)]
    phase = (step // period) % len(windows)
    active, active_p = windows[phase]
    if arm_i == active:
        return active_p
    base = [0.0, 0.10, 0.08, 0.0, 0.06, 0.05, 0.04, 0.0, 0.03, 0.02, 0.02, 0.01]
    if phase > 0 and arm_i == windows[phase - 1][0]:
        return 0.08  # the old window is not dead, just no longer the best
    return base[arm_i]


WORLDS = {
    "stationary": p_stationary,
    "rotate": p_rotate,
    "window": p_window,
}


# --------------------------------------------------------------------------
# statistics with optional exponential decay
# --------------------------------------------------------------------------
def _int_if_whole(x: float):
    return int(x) if float(x).is_integer() else x


def normalise(stats: dict) -> dict:
    """The scheduler wants {n, mean, sd, var, wins}; keep fractional counts as such."""
    out = {}
    for a, s in stats.items():
        out[a] = {"n": _int_if_whole(float(s["n"])), "mean": float(s["mean"]),
                  "sd": float(s["sd"]), "var": float(s["var"]),
                  "wins": _int_if_whole(float(s["wins"]))}
    return out


# --------------------------------------------------------------------------
# one run
# --------------------------------------------------------------------------
def legacy_pick(arms, stats, rng):
    """The pre-v4 selector: max mean, unexplored by sort order."""
    def key(a):
        s = stats.get(a) or {}
        if int(s.get("n") or 0) == 0:
            return (1, a)
        return (0, float(s.get("mean") or 0.0))
    return max(arms, key=key)


def run(world: str, policy: str, *, budget: int, seed: int,
        half_life: float | None, arms: list[str] | None = None) -> dict:
    arms = arms or ARMS
    p = WORLDS[world]
    rng = random.Random(seed)
    sch = None
    if policy != "legacy":
        sch = AdaptiveScheduler(policy, seed=seed)
    acc: dict[str, ArmAcc] = {a: ArmAcc() for a in arms}
    pulls: dict[str, int] = {a: 0 for a in arms}
    successes = 0
    best_share = 0
    regret = 0.0

    for step in range(budget):
        stats = {a: acc[a].stats(step, half_life) for a in arms}
        if policy == "legacy":
            arm = legacy_pick(arms, stats, rng)
        elif policy == "random":
            arm = rng.choice(arms)
        else:
            assert sch is not None
            arm = sch.choose(arms, normalise(stats), rng=rng)
        i = arms.index(arm)
        best_p = max(p(j, step) for j in range(len(arms)))
        won = 1.0 if rng.random() < p(i, step) else 0.0
        acc[arm].add(step, won, half_life)
        pulls[arm] += 1
        successes += int(won)
        regret += best_p - p(i, step)
        if p(i, step) >= best_p - 1e-9:
            best_share += 1
    return {"world": world, "policy": policy, "half_life": half_life, "seed": seed,
            "payoff": successes / budget, "best_share": best_share / budget,
            "regret": regret / budget}


def summarise(runs: list[dict]) -> dict:
    def ci(key):
        vals = [r[key] for r in runs]
        m = statistics.fmean(vals)
        if len(vals) < 2:
            return m, 0.0
        se = statistics.stdev(vals) / math.sqrt(len(vals))
        return m, 1.96 * se
    payoff, payoff_ci = ci("payoff")
    share, share_ci = ci("best_share")
    regret, regret_ci = ci("regret")
    return {"runs": len(runs), "payoff": payoff, "payoff_ci": payoff_ci,
            "best_share": share, "best_share_ci": share_ci,
            "regret": regret, "regret_ci": regret_ci}


def main() -> int:
    ap = argparse.ArgumentParser(description="non-stationarity bench")
    ap.add_argument("--budget", type=int, default=2000)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--policies", default="legacy,random,ucb_improved,thompson,contextual_ts")
    ap.add_argument("--half-lives", default="none,100,300")
    ap.add_argument("--worlds", default="stationary,rotate,window")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="", help="write the table as JSON")
    a = ap.parse_args()

    policies = [p.strip() for p in a.policies.split(",") if p.strip()]
    hls = [None if h.strip() == "none" else float(h.strip())
           for h in a.half_lives.split(",") if h.strip()]
    worlds = [w.strip() for w in a.worlds.split(",") if w.strip()]

    table = []
    for world in worlds:
        for policy in policies:
            for hl in hls:
                runs = [run(world, policy, budget=a.budget, seed=s, half_life=hl)
                        for s in range(a.seeds)]
                agg = summarise(runs)
                agg.update({"world": world, "policy": policy, "half_life": hl})
                table.append(agg)

    payload = {"table": table, "budget": a.budget, "seeds": a.seeds,
               "half_lives": hls, "worlds": worlds, "policies": policies}
    if a.out:
        outp = Path(a.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"written: {outp}")
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0

    print(f"budget={a.budget} per run, seeds={a.seeds} "
          f"(mean ± 95% CI over seeds)\n")
    for world in worlds:
        print(f"== {world} ==")
        print(f"{'policy':<16}{'decay':<8}{'payoff':>16}{'best-arm share':>20}{'regret':>16}")
        for policy in policies:
            for hl in hls:
                row = next(r for r in table
                           if r["world"] == world and r["policy"] == policy
                           and r["half_life"] == hl)
                d = "off" if hl is None else f"{hl:g}"
                print(f"{policy:<16}{d:<8}"
                      f"{row['payoff']:.4f}±{row['payoff_ci']:.4f}".rjust(16) + "  "
                      + f"{row['best_share']:.3f}±{row['best_share_ci']:.3f}".rjust(18) + "  "
                      + f"{row['regret']:.4f}".rjust(14))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
