#!/usr/bin/env python3
"""Does composing NEW frames pay off? — the live randomized answer.

Why this tool exists
--------------------
`generator_bench.py` could only say that component effects do NOT visibly
transfer to unseen combinations; it cannot say whether GENERATION as a policy is
worth the probe, because a brand-new frame has no reward by construction until
it is actually tried.  That question is only answerable online, from a
randomized experiment (driver `--ab-generate P`):

    treatment = compose a new frame            (arm_source='generated')
    control   = re-probe the best catalog delta (arm_source='control_repeat')

Both cost exactly one probe on the same pair, so the difference in reward is the
value of generating.  This tool reads the ledger and reports the difference with
a Wilson interval and an explicit sample-size guard, so "undecided" stays a
possible answer.

Usage:
    python3 harness/ab_report.py                # whole ledger
    python3 harness/ab_report.py --json         # machine-readable
    python3 harness/ab_report.py --min-n 15     # more evidence before a verdict
"""

import argparse
import json
import math
import os
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DB = HERE.parent / "artifacts" / "harness.db"
SUCCESS_THRESHOLD = 0.5
MIN_N = 20


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = wins / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def classify(delta: str | None, arm_source: str | None) -> str:
    """Explicit tag first, then the historical prefix (pre-experiment rows)."""
    if arm_source in ("generated", "control_repeat", "catalog"):
        return arm_source
    if delta and str(delta).startswith("gen."):
        return "generated"
    return "catalog"


def load(db_path=DB, *, board: str | None = None) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("pragma table_info(attempts)")}
    # the tag column arrives with the schema migration; a ledger that never ran
    # the new driver yet is still readable (rows then classify by delta prefix)
    has_tag = "arm_source" in cols
    sel = "pair_id, delta, reward, reward_source, state, started_at"
    where, params = "WHERE reward IS NOT NULL", []
    if board:
        # attempts carry board_profile; without the filter two lanes' boards
        # would be pooled into one A/B comparison
        where += " AND board_profile=?"
        params.append(board)
    rows = conn.execute(
        f"SELECT {sel}{', arm_source' if has_tag else ', NULL AS arm_source'}"
        f" FROM attempts {where}", params).fetchall()
    out = []
    for r in rows:
        out.append({
            "pair_id": r["pair_id"], "delta": r["delta"],
            "arm_source": classify(r["delta"], r["arm_source"]),
            "reward": float(r["reward"]), "reward_source": r["reward_source"],
            "state": r["state"], "started_at": r["started_at"],
        })
    return out


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "mean_reward": None, "success_rate": None, "success_ci95": None,
                "successes": 0}
    rewards = [r["reward"] for r in rows]
    wins = sum(1 for r in rows if r["reward"] >= SUCCESS_THRESHOLD)
    lo, hi = wilson(wins, n)
    return {"n": n, "mean_reward": round(sum(rewards) / n, 4), "successes": wins,
            "success_rate": round(wins / n, 4), "success_ci95": [round(lo, 4), round(hi, 4)]}


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's approximation) — enough for power."""
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p <= 0:
        return float("-inf")
    if p >= 1:
        return float("inf")
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def probes_needed(gen: dict, ctl: dict, power: float = 0.8, alpha: float = 0.05) -> dict:
    """How many probes per arm to separate the two success rates.

    "Undecided" without a plan is a permanent state; this turns it into a number.
    Two-proportion test: n = (z_{1-a/2} + z_power)^2 (p1(1-p1) + p2(1-p2)) / (p1-p2)^2.
    """
    p1, p2 = gen.get("success_rate"), ctl.get("success_rate")
    if p1 is None or p2 is None:
        return {"needed_per_arm": None, "reason": "no success data yet"}
    gap = abs(p1 - p2)
    if gap < 1e-9:
        return {"needed_per_arm": None, "reason": "observed gap is zero: no finite n separates them"}
    z_a = _norm_ppf(1 - alpha / 2)
    z_b = _norm_ppf(power)
    n = ((z_a + z_b) ** 2) * (p1 * (1 - p1) + p2 * (1 - p2)) / (gap ** 2)
    n = int(math.ceil(n))
    return {"needed_per_arm": n, "observed_gap": round(gap, 4),
            "have": {"generated": gen["n"], "control_repeat": ctl["n"]},
            "still_needed": max(0, n - gen["n"]) + max(0, n - ctl["n"]),
            "note": f"80% power at alpha={alpha}, two-proportion test on the observed rates"}


def verdict(gen: dict, ctl: dict, min_n: int) -> dict:
    """Undecided unless there is enough evidence AND the intervals separate."""
    if gen["n"] < min_n or ctl["n"] < min_n:
        need = {"generated": max(0, min_n - gen["n"]), "control_repeat": max(0, min_n - ctl["n"])}
        out = {"call": "undecided", "reason": "not enough samples yet", "still_needed": need}
        out["power"] = probes_needed(gen, ctl)
        return out
    d_mean = (gen["mean_reward"] or 0.0) - (ctl["mean_reward"] or 0.0)
    g_lo, g_hi = gen["success_ci95"] or (0, 0)
    c_lo, c_hi = ctl["success_ci95"] or (0, 0)
    separated = g_lo > c_hi or c_lo > g_hi
    if not separated:
        return {"call": "undecided", "reason": "success intervals overlap",
                "delta_mean_reward": round(d_mean, 4),
                "power": probes_needed(gen, ctl)}
    better = "generated" if d_mean > 0 else "control_repeat"
    return {"call": better, "reason": "success intervals separated",
            "delta_mean_reward": round(d_mean, 4),
            "ci95": {"generated": gen["success_ci95"], "control_repeat": ctl["success_ci95"]}}


def by_pair(rows: list[dict]) -> dict:
    out = {}
    for row in rows:
        if row["arm_source"] not in ("generated", "control_repeat"):
            continue
        out.setdefault(row["pair_id"], {"generated": [], "control_repeat": []})
        out[row["pair_id"]][row["arm_source"]].append(row)
    return {k: {"generated": summarise(v["generated"]),
                "control_repeat": summarise(v["control_repeat"])} for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").strip().split("\n")[0] or "generator A/B report")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--min-n", type=int, default=MIN_N,
                    help=f"probes per arm before a verdict is allowed (default {MIN_N})")
    ap.add_argument("--board", default=os.environ.get("HERMES_BOARD", "lucky-break-payday"),
                    help="board to compare (attempts of the other lane's board would "
                         "otherwise be pooled into the same arms)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = load(a.db, board=a.board)
    gen = summarise([r for r in rows if r["arm_source"] == "generated"])
    ctl = summarise([r for r in rows if r["arm_source"] == "control_repeat"])
    cat = summarise([r for r in rows if r["arm_source"] == "catalog"])
    report = {
        "generated": gen, "control_repeat": ctl, "catalog_all": cat,
        "verdict": verdict(gen, ctl, a.min_n),
        "per_pair": by_pair(rows),
        "note": ("treatment = new frame, control = re-probe of the best catalog delta; "
                 "both cost one probe.  'catalog_all' includes pre-experiment probes on "
                 "untried deltas, so it is NOT a control — it is context only."),
    }
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"{'arm':<18}{'n':>5}{'mean_reward':>13}{'success':>9}{'ci95 (success)':>22}")
    for name, s in (("generated", gen), ("control_repeat", ctl), ("catalog (context)", cat)):
        if s["n"]:
            print(f"{name:<18}{s['n']:>5}{s['mean_reward']:>13.4f}{s['success_rate']:>9.3f}"
                  f"{str(s['success_ci95']):>22}")
        else:
            print(f"{name:<18}{0:>5}{'-':>13}{'-':>9}{'-':>22}")
    v = report["verdict"]
    print(f"\nverdict: {v['call']} ({v['reason']})")
    if v.get("still_needed"):
        print(f"  still needed: " + ", ".join(f"{k} +{n}" for k, n in v["still_needed"].items()))
    if v.get("delta_mean_reward") is not None:
        print(f"  mean-reward difference (generated - control): {v['delta_mean_reward']:+.4f}")
    power = v.get("power") or {}
    if power.get("needed_per_arm"):
        print(f"  decision needs ~{power['needed_per_arm']} probes PER ARM "
              f"(gap {power['observed_gap']}): have generated {power['have']['generated']}, "
              f"control {power['have']['control_repeat']} -> {power['still_needed']} more probes")
    elif power.get("reason"):
        print(f"  decision plan: {power['reason']}")
    pairs = [(k, v["generated"]["n"], v["control_repeat"]["n"]) for k, v in report["per_pair"].items()]
    if pairs:
        print("\nper pair (generated / control probes):")
        for pair, g, c in sorted(pairs, key=lambda x: -(x[1] + x[2])):
            print(f"  {pair:<52} {g:>3} / {c:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
