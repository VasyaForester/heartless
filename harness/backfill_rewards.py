#!/usr/bin/env python3
"""Backfill judge-anchored rewards for attempts that were judged before v4.

Why: the four best probes the workspace has ever produced (score 260/300,
`prepend_controlicd` on christmas-giftcard-scam|Diamond Whale Bold) carry
`reward IS NULL` — they were recorded before the reward column existed (v4).
A selector that cannot see the only confirmed high scores is learning from a
censored history: the best arm looks like an untried arm.

The reward mapping is `strategy.judge_reward` — mean criterion percent in [0, 1]
— so backfilled rows stay on the same scale as live ones.  Rows whose artifact
and pcts are both gone are REPORTED, not guessed: the old per-pair judge file was
overwritten by every submission (the defect the ledger fixed), and inventing a
number there would be fabricating evidence.

Usage:
    python3 harness/backfill_rewards.py --dry-run
    python3 harness/backfill_rewards.py
"""

import argparse
import json
import os
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import store  # noqa: E402
import strategy  # noqa: E402

WORK = HERE.parent
DB = WORK / "artifacts" / "harness.db"
SOURCE = "judge_backfill"


def candidate_rows(conn) -> list:
    return list(conn.execute(
        "SELECT attempt_id, pair_id, delta, score, pcts, judge_ref FROM attempts"
        " WHERE judge_status='verified' AND reward IS NULL ORDER BY started_at"))


def reward_for(row) -> tuple[float | None, str]:
    """(reward, why) from the persisted verdict; pcts is the reliable field."""
    pcts = row["pcts"]
    if pcts:
        try:
            values = [float(x) for x in json.loads(pcts)]
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, "pcts unreadable"
        if values:
            return round(sum(values) / len(values) / 100.0, 4), f"mean of {len(values)} criteria"
    if row["score"] is not None:
        # score is the SUM of criterion percents; without pcts the criterion
        # count is unknown, so the honest move is to leave the row alone.
        return None, f"score={row['score']} but pcts absent (criterion count unknown)"
    return None, "no verdict data"


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lane", default="maint",
                    help="lease lane for the write (the lease proves a live owner; "
                         "the attempt rows themselves are not lease-scoped)")
    a = ap.parse_args()
    conn = store.connect(a.db)
    rows = candidate_rows(conn)
    if not rows:
        print("nothing to backfill: every verified attempt already carries a reward")
        return 0
    planned, skipped = [], []
    for row in rows:
        reward, why = reward_for(row)
        (planned if reward is not None else skipped).append((row, reward, why))
    lease = None
    if not a.dry_run and planned:
        lease = store.acquire_lease(conn, a.lane, "backfill", pid=os.getpid())
    for row, reward, why in planned:
        line = (f"  {row['attempt_id'][-30:]:<32} delta={str(row['delta'])[:22]:<24}"
                f" -> reward={reward} ({why})")
        if a.dry_run or lease is None:
            print("WOULD SET" + line)
        else:
            store.set_reward(conn, lease, row["attempt_id"], reward, SOURCE)
            print("SET       " + line)
    for row, _reward, why in skipped:
        print(f"  SKIP {row['attempt_id'][-30:]:<32} {why}")
    if lease is not None:
        store.release(conn, lease)
    print(f"\nplanned={len(planned)} skipped={len(skipped)}"
          + (" (dry run: nothing written)" if a.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
