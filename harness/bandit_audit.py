#!/usr/bin/env python3
"""Bandit data-quality audit for the v2 attempts.

Only finalized + verified attempts count as reward evidence.  Pending judges,
execution failures, duplicates, board/model mixes and strategy versions are
reported separately so a selection algorithm cannot silently consume them.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sqlite3
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def audit(conn) -> dict:
    conn.row_factory = sqlite3.Row
    finalized = [dict(r) for r in conn.execute(
        "SELECT * FROM attempts WHERE state='finalized' AND judge_status='verified'"
        " ORDER BY started_at")]
    pending = [dict(r) for r in conn.execute(
        "SELECT * FROM attempts WHERE state='awaiting_judge'")]
    failed = [dict(r) for r in conn.execute(
        "SELECT * FROM attempts WHERE state IN"
        " ('execution_failed','submission_uncertain','judge_failed')")]
    all_attempts = [dict(r) for r in conn.execute("SELECT * FROM attempts")]
    hashes = Counter(a["input_hash"] for a in all_attempts if a.get("input_hash"))
    duplicates = {h: n for h, n in hashes.items() if n > 1}
    by_board = Counter(a.get("board_profile") for a in finalized)
    by_model = Counter((a.get("model"), a.get("model_version")) for a in finalized)
    by_strategy = Counter(a.get("strategy_version") for a in finalized)
    by_pair = Counter(a.get("pair_id") for a in finalized)
    costs = {"message": len(all_attempts), "judge": len(finalized) + len(pending)}
    return {
        "finalized_verified": len(finalized),
        "pending": len(pending),
        "failed": len(failed),
        "total_attempts": len(all_attempts),
        "duplicate_input_hashes": duplicates,
        "duplicate_attempts": sum(n - 1 for n in duplicates.values()),
        "by_board": dict(by_board),
        "by_model": {f"{m}@{v}": n for (m, v), n in by_model.items()},
        "by_strategy_version": {str(k): v for k, v in by_strategy.items()},
        "by_pair": dict(by_pair),
        "costs": costs,
        "reward_eligible": len(finalized),
    }


def ucb_replay(conn, c: float = 45.0) -> dict:
    """Replay the coverage-first + UCB decisions over finalized history.

    Returns the order and whether each decision was reproducible from the
    statistics available immediately before it.  It is a diagnostic, not a
    replacement for the live selector.
    """
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT pair_id,score,started_at FROM attempts"
        " WHERE state='finalized' AND judge_status='verified' ORDER BY started_at")]
    stats = defaultdict(lambda: {"n": 0, "sum": 0})
    order = []
    reproducible = 0
    for row in rows:
        pair = row["pair_id"]
        candidates = {p: s for p, s in stats.items()}
        decision = None
        if not candidates:
            decision = pair  # first attempt: any cold pair is valid
            reproducible += 1
        else:
            total = sum(s["n"] for s in candidates.values()) or 1
            scored = []
            for p, s in candidates.items():
                if s["n"] == 0:
                    scored.append((1e9, p))
                else:
                    scored.append((s["sum"] / s["n"] + c * math.sqrt(
                        2.0 * math.log(total + 1) / s["n"]), p))
            scored.sort(reverse=True)
            decision = scored[0][1]
            if decision == pair:
                reproducible += 1
        stats[pair]["n"] += 1
        stats[pair]["sum"] += int(row["score"] or 0)
        order.append({"pair": pair, "decision_at_step": decision,
                      "reproducible": decision == pair})
    return {"steps": len(order), "reproducible": reproducible,
            "rate": round(reproducible / len(order), 3) if order else None,
            "order": order}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db, timeout=10)
    try:
        result = {"audit": audit(conn), "ucb_replay": ucb_replay(conn)}
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())