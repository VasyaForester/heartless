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


def load(db_path=DB) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("pragma table_info(attempts)")}
    # the tag column arrives with the schema migration; a ledger that never ran
    # the new driver yet is still readable (rows then classify by delta prefix)
    has_tag = "arm_source" in cols
    sel = "pair_id, delta, reward, reward_source, state, started_at"
    rows = conn.execute(
        f"SELECT {sel}{', arm_source' if has_tag else ', NULL AS arm_source'}"
        " FROM attempts WHERE reward IS NOT NULL").fetchall()
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


def verdict(gen: dict, ctl: dict, min_n: int) -> dict:
    """Undecided unless there is enough evidence AND the intervals separate."""
    if gen["n"] < min_n or ctl["n"] < min_n:
        need = {"generated": max(0, min_n - gen["n"]), "control_repeat": max(0, min_n - ctl["n"])}
        return {"call": "undecided", "reason": "not enough samples yet", "still_needed": need}
    d_mean = (gen["mean_reward"] or 0.0) - (ctl["mean_reward"] or 0.0)
    g_lo, g_hi = gen["success_ci95"] or (0, 0)
    c_lo, c_hi = ctl["success_ci95"] or (0, 0)
    separated = g_lo > c_hi or c_lo > g_hi
    if not separated:
        return {"call": "undecided", "reason": "success intervals overlap",
                "delta_mean_reward": round(d_mean, 4)}
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
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = load(a.db)
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
    pairs = [(k, v["generated"]["n"], v["control_repeat"]["n"]) for k, v in report["per_pair"].items()]
    if pairs:
        print("\nper pair (generated / control probes):")
        for pair, g, c in sorted(pairs, key=lambda x: -(x[1] + x[2])):
            print(f"  {pair:<52} {g:>3} / {c:>3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
