#!/usr/bin/env python3
"""Reward-channel audit (skill rule #1: verify the channel before tuning any policy).

Checks, for the last N live attempts:
  * how many carry a reward, split by reward_source;
  * whether each judged attempt's judge artifact is bound to THAT attempt id;
  * mean reward + success rate (reward >= 0.5) per source — the two metrics;
  * unit coverage (which pairs got probed) vs the unsolved set;
  * arm concentration (top deltas) — the "starvation" symptom.
Read-only. Usage: python3 tools/reward_audit.py [--n 100]
"""
import argparse
import collections
import json
import pathlib
import sqlite3
import time

W = pathlib.Path(__file__).resolve().parent.parent
DB = W / "artifacts" / "harness.db"

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=100)
a = ap.parse_args()

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

rows = list(conn.execute("SELECT * FROM attempts ORDER BY started_at DESC LIMIT ?", (a.n,)))
print(f"window: last {len(rows)} attempts\n")

c = collections.Counter()
src = collections.Counter()
by_src = collections.defaultdict(list)
units = collections.Counter()
arms = collections.Counter()
for r in rows:
    c[r["execution_status"]] += 1
    units[r["pair_id"]] += 1
    arms[str(r["delta"])[:28]] += 1
    if r["reward"] is not None:
        s = r["reward_source"] or "null-source"
        src[s] += 1
        by_src[s].append(float(r["reward"]))

print("execution_status:", dict(c))
print("units probed:", len(units), "| top:", units.most_common(4))
print("arm concentration: top3 share =",
      round(sum(n for _, n in arms.most_common(3)) / max(len(rows), 1), 2))
print("rewards present:", sum(src.values()), "/", len(rows))
for s, vals in by_src.items():
    mean = sum(vals) / len(vals)
    succ = sum(1 for v in vals if v >= 0.5) / len(vals)
    print(f"  source={s:22s} n={len(vals):3d} mean={mean:.3f} success(>=.5)={succ:.3f}")

# judge binding: every verified judge must point at its own attempt
ver = list(conn.execute("SELECT attempt_id, operation_id, status FROM judges WHERE status='verified'"))
bad = [v for v in ver if v["operation_id"] != v["attempt_id"]]
print(f"\nverified judges: {len(ver)} (mis-bound: {len(bad)})")
for v in ver[-4:]:
    print("  ", v["status"], v["operation_id"][:80])

# judged attempts in the window and their scores
judged = [r for r in rows if r["judge_status"] == "verified"]
print(f"verified judges inside window: {len(judged)}")
for r in judged[:5]:
    print(f"  score={r['score']} pcts={r['pcts']} {r['pair_id']}")

# how many attempts could ever be judged (executed a tool call)? — proxy:
# a judge artifact exists for this attempt id
try:
    have = {r[0] for r in conn.execute("SELECT attempt_id FROM judges")}
    cov = sum(1 for r in rows if r["attempt_id"] in have)
    print(f"attempts with a judge artifact: {cov}/{len(rows)}")
except Exception as exc:  # noqa: BLE001
    print("judge coverage err:", exc)