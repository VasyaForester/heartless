#!/usr/bin/env python3
"""Audit the reward channel: is the selector learning from real probes?

Two questions, in this order (a selector tuned on a corrupt channel is noise):

1. HOW MANY PROBES WERE OUR OWN FAULT?  A probe the harness failed to land
   (`probe_ok=False`, a tool call lost in the fill step, a lost send, a mock
   mismatch) says nothing about the arm.  It must be excluded from the
   statistics and counted as a harness defect we can fix.  Measured
   2026-11-13: 120 of the last 400 probes were dropped by our own plumbing
   while still being graded as evidence.

2. IS THE LOCAL PROXY ORDERED LIKE THE JUDGE?  The proxy is what the selector
   learns from on the ~99% of probes that never reach a verdict, so its ORDER
   must agree with judge scores where both exist.  `--calibrate` prints the mean
   judge score per proxy level; if the order disagrees, fix the mapping instead
   of trusting the policy comparison.

Usage:
    python3 harness/reward_audit.py                    # channel health
    python3 harness/reward_audit.py --calibrate        # proxy vs judge
    python3 harness/reward_audit.py --json
"""

import argparse
import collections
import json
import math
import pathlib
import sqlite3
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import strategy  # noqa: E402

WORK = HERE.parent
REPEATS = WORK / "datasets" / "lbp" / "repeats.jsonl"
DB = WORK / "artifacts" / "harness.db"
# The composite reward was 0.7*judge + 0.3*local until this moment; historical
# rows can be inverted exactly.  Rows after it must be read from the raw
# observation log (strategy-memory disagreements), never inverted.
BLEND_073_CUTOFF = 1794635948


def _spearman(xs: list, ys: list) -> float | None:
    """Rank correlation over the raw pairs, ties get average ranks.

    Descriptive only — it does NOT decide anything by itself: a saturated proxy
    range can still correlate with the judge while being useless for ranking
    (that is what the verdict block measures instead).
    """
    n = len(xs)
    if n < 3:
        return None

    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def ledger_rows(path=REPEATS, tail: int = 0) -> list[dict]:
    """One dict per probe; malformed lines are skipped, not fatal."""
    p = pathlib.Path(path)
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-tail:] if tail else rows


def audit(rows: list[dict]) -> dict:
    faults = collections.Counter()
    rewards = collections.Counter()
    sources = collections.Counter()
    for row in rows:
        fault = strategy.harness_fault(row)
        if fault:
            faults[fault] += 1
        reward, _ = strategy.local_reward(row)
        if reward is None:
            rewards["none"] += 1
        else:
            rewards[str(reward)] += 1
        sources[str(row.get("failure_class"))] += 1
    valid = sum(v for k, v in rewards.items() if k != "none")
    n = len(rows)
    return {
        "probes": n,
        "faults": dict(faults.most_common()),
        "fault_rate": round(sum(faults.values()) / n, 4) if n else None,
        "reward_levels": dict(rewards.most_common(14)),
        "valid_rewards": valid,
        "valid_rate": round(valid / n, 4) if n else None,
        "worst_offenders": dict(sources.most_common(6)),
    }


def calibrate(rows: list[dict], db_path=DB) -> dict:
    """Mean judge score per proxy level — the monotonicity check.

    Two sources of pairs: (a) ledger rows that carry judge fields, (b) attempts
    in the live DB whose reward came from the composite evaluator (they hold a
    verified judge score AND a local proxy value).
    """
    buckets: dict[str, list[float]] = collections.defaultdict(list)
    paired = 0
    for row in rows:
        pcts = row.get("pcts")
        if not pcts or not isinstance(pcts, list):
            continue
        reward, _ = strategy.local_reward(row)
        if reward is None:
            continue
        try:
            score = sum(float(x) for x in pcts) / len(pcts) / 100.0
        except (TypeError, ZeroDivisionError):
            continue
        buckets[f"{reward:.2f}"].append(score)
        paired += 1
    db_pairs = 0
    dis_pairs = 0
    path = pathlib.Path(db_path)
    if path.is_file():
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cols = {r[1] for r in conn.execute("pragma table_info(attempts)")}
        if {"reward", "score", "judge_status"} <= cols:
            for r in conn.execute("SELECT reward, score FROM attempts"
                                  " WHERE reward IS NOT NULL AND score IS NOT NULL"
                                  " AND reward_source='composite'"):
                # labelled apart on purpose: the DB stores the COMPOSITE reward
                # (judge + proxy blend), a different scale from the raw proxy
                # levels of the ledger — mixing them in one column would be a
                # fake monotonicity claim.
                buckets[f"composite:{float(r['reward']):.2f}"].append(
                    float(r["score"]) / 100.0)
                db_pairs += 1
    # RAW pairs (judge vs proxy, no blend) from the arm-level disagreement log —
    # this is the column the monotonicity verdict is allowed to use, because both
    # numbers are independent measurements of the same probe.
    raw_pairs: list = []
    mem = pathlib.Path("artifacts/strategy-memory.db")
    if mem.is_file():
        conn = sqlite3.connect(f"file:{mem}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            for r in conn.execute("SELECT judge_reward, local_reward FROM disagreements"
                                  " WHERE judge_reward IS NOT NULL"
                                  " AND local_reward IS NOT NULL"):
                raw_pairs.append((float(r["local_reward"]), float(r["judge_reward"])))
                dis_pairs += 1
        except sqlite3.OperationalError:
            pass
    # plus every ledger probe that carries both a proxy level and judge pcts
    for row in rows:
        pcts = row.get("pcts")
        if not pcts or not isinstance(pcts, list):
            continue
        reward, _ = strategy.local_reward(row)
        if reward is None:
            continue
        try:
            raw_pairs.append((reward, sum(float(x) for x in pcts) / len(pcts) / 100.0))
        except (TypeError, ZeroDivisionError):
            continue
    # historical arm-level pairs recovered from the composite rows written under
    # the OLD 0.7/0.3 blend: local = (reward - 0.7*judge) / 0.3 is an EXACT
    # inversion, not an estimate.  Guarded by a cutoff so it can never be applied
    # to rows written under the 0.9/0.1 blend introduced 2026-11-14; from then on
    # the live path records raw pairs itself.  Sources may overlap (a row can be
    # both inverted and logged as a disagreement) — that is stated, not silently
    # deduped, because the finding below (how many engaged probes EVER scored) does
    # not depend on the exact count.
    inv_pairs = 0
    if path.is_file():
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            for r in conn.execute(
                    "SELECT reward, pcts FROM attempts WHERE reward_source='composite'"
                    " AND pcts IS NOT NULL AND started_at < ?", (BLEND_073_CUTOFF,)):
                try:
                    pcts = json.loads(r["pcts"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if not pcts:
                    continue
                judge = sum(float(x) for x in pcts) / len(pcts) / 100.0
                local = (float(r["reward"]) - 0.7 * judge) / 0.3
                if -0.05 <= local <= 1.5:
                    raw_pairs.append((round(local, 4), round(judge, 4)))
                    inv_pairs += 1
        except sqlite3.OperationalError:
            pass
    out = {}
    for level, scores in sorted(buckets.items(),
                                key=lambda kv: (kv[0].startswith("composite"),
                                                float(kv[0].split(":")[-1]))):
        out[level] = {"n": len(scores),
                      "mean_judge": round(statistics.fmean(scores), 4)}
    means = [out[k]["mean_judge"] for k in out if not k.startswith("composite")]
    order_ok = all(b >= a for a, b in zip(means, means[1:])) if len(means) > 1 else None
    # verdict on the raw pairs: the question that matters is whether a HIGH proxy
    # ever comes with a non-trivial judge score (discriminating power), not
    # whether the two columns correlate on a saturated range.
    engaged = [(p, j) for p, j in raw_pairs if p >= 0.5]
    judged_high = [(p, j) for p, j in raw_pairs if j > 0.05]
    verdict = None
    if len(raw_pairs) >= 30:
        rho = _spearman([p for p, _ in raw_pairs], [j for _, j in raw_pairs])
        saturated = (len(engaged) >= 5 and
                     statistics.fmean([j for _, j in engaged]) <= 0.05)
        verdict = {
            "pairs": len(raw_pairs),
            "spearman": None if rho is None else round(rho, 3),
            "proxy_engaged_n": len(engaged),
            "proxy_engaged_mean_judge": (round(statistics.fmean([j for _, j in engaged]), 4)
                                         if engaged else None),
            "judge_positive_n": len(judged_high),
            "call": ("saturated: the proxy says engaged while the judge stays at zero"
                     if saturated else "pending: no saturation pattern detected"),
        }
    return {
        "pairs": paired + db_pairs,
        "from_ledger": paired,
        "from_db": db_pairs,
        "from_disagreements": dis_pairs,
        "from_db_inverted": inv_pairs,
        "raw_pairs": len(raw_pairs),
        "by_level": out,
        "monotone": order_ok,
        "verdict": verdict,
        "enough_evidence": raw_pairs and len(raw_pairs) >= 30,
        "note": ("the verdict column uses RAW (proxy, judge) pairs only — composite "
                 "rows keep the judge inside the predictor and are shown for context; "
                 "a monotone column means the proxy ranks what the judge scores"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "").strip().split("\n")[0] or "reward audit")
    ap.add_argument("--path", default=str(REPEATS))
    ap.add_argument("--tail", type=int, default=400,
                    help="audit only the newest N probes (0 = all; default 400, the "
                         "channel degrades as the arena changes)")
    ap.add_argument("--calibrate", action="store_true",
                    help="compare proxy levels against judge scores where both exist")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = ledger_rows(a.path, a.tail)
    report = {"audit": audit(rows)}
    if a.calibrate:
        report["calibration"] = calibrate(rows)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    au = report["audit"]
    print(f"probes: {au['probes']}  |  valid rewards: {au['valid_rewards']} "
          f"({au['valid_rate']})  |  harness faults: {sum(au['faults'].values())} "
          f"({au['fault_rate']})")
    if au["faults"]:
        print("harness faults (excluded from the statistics; OUR defects):")
        for kind, n in au["faults"].items():
            print(f"  {kind:<22} {n:>5}")
    print("reward levels:")
    for level, n in au["reward_levels"].items():
        print(f"  {level:<8} {n:>5}")
    if a.calibrate:
        cal = report["calibration"]
        print(f"\nproxy vs judge (paired probes: {cal['pairs']} — ledger "
              f"{cal['from_ledger']}, db {cal['from_db']}, "
              f"raw pairs {cal['raw_pairs']}: {cal['from_disagreements']} logged "
              f"+ {cal['from_db_inverted']} inverted, sources may overlap):")
        for level, v in cal["by_level"].items():
            print(f"  proxy {level:<6} n={v['n']:<4} mean judge {v['mean_judge']:.3f}")
        v = cal.get("verdict")
        if v:
            print(f"  RAW-PAIR VERDICT ({v['pairs']} pairs): {v['call']}")
            print(f"    spearman={v['spearman']} | proxy>=0.5: n={v['proxy_engaged_n']} "
                  f"mean judge {v['proxy_engaged_mean_judge']} | "
                  f"judge>0.05: n={v['judge_positive_n']}")
        elif cal["enough_evidence"] is not True:
            print(f"  verdict needs >=30 raw pairs (have {cal['raw_pairs']}) — "
                  f"the table above is a description, not a verdict")
        print(f"  {cal['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
