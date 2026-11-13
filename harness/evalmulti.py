#!/usr/bin/env python3
"""Multi-criterion evaluation v3 (Phase 6, offline).

The judge returns independent criterion percentages. A single mean hides the
fact that one mandatory criterion can be fully failed while others pass.
This module keeps the vector, flags mandatory-failure blockers, and prints a
Pareto summary per pair.

Usage: python3 harness/evalmulti.py [--db artifacts/harness.db]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def load(db: pathlib.Path):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    pairs = {}
    for r in conn.execute("SELECT attempt_id, scenario, model, delta, pcts, score, verdict,"
                          " judge_status, state FROM attempts ORDER BY rowid"):
        try:
            pcts = json.loads(r["pcts"]) if r["pcts"] else None
        except Exception:
            pcts = None
        if not pcts:
            continue
        key = f"{r['scenario']}|{r['model']}"
        pairs.setdefault(key, []).append({**dict(r), "pcts": pcts})
    return pairs


def dominated(a, b) -> bool:
    """a dominated by b (b at least as good on all criteria, better on one)."""
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def analyse(pairs):
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pairs": {}}
    for key, rows in pairs.items():
        dim = max(len(r["pcts"]) for r in rows)
        crit_max = [max((r["pcts"][i] if i < len(r["pcts"]) else 0) for r in rows) for i in range(dim)]
        crit_mean = [round(sum((r["pcts"][i] if i < len(r["pcts"]) else 0) for r in rows) / len(rows), 1)
                     for i in range(dim)]
        # mandatory-failure blockers: attempts where one criterion is a hard zero
        # while overall score is otherwise non-trivial
        blockers = [r for r in rows if 0 in (r["pcts"] or [])]
        # Pareto frontier over the distinct pct vectors
        vecs = sorted({tuple(r["pcts"]) for r in rows}, key=lambda t: (-sum(t), t))
        frontier = [v for v in vecs if not any(dominated(v, w) for w in vecs if w != v)]
        worst = min(range(dim), key=lambda i: crit_mean[i]) if dim else None
        out["pairs"][key] = {
            "n": len(rows),
            "criteria": dim,
            "max_per_criterion": crit_max,
            "mean_per_criterion": crit_mean,
            "blocking_criterion": worst,
            "blocking_mean": crit_mean[worst] if worst is not None else None,
            "mandatory_fail_attempts": len(blockers),
            "pareto_frontier": [list(v) for v in frontier[:5]],
            "accepted": any((r["verdict"] or "").lower() == "accepted" for r in rows),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--out", default=str(WORK / "artifacts" / "eval-multi-objective.json"))
    a = ap.parse_args()
    pairs = load(pathlib.Path(a.db))
    res = analyse(pairs)
    pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pairs={len(res['pairs'])} -> {a.out}")
    for key, s in sorted(res["pairs"].items()):
        print(f"  {key:58s} n={s['n']:3d} max={s['max_per_criterion']}"
              f" blocker=#{s['blocking_criterion']}({s['blocking_mean']}%)"
              f" fails={s['mandatory_fail_attempts']} accepted={s['accepted']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())