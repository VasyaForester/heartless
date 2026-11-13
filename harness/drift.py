#!/usr/bin/env python3
"""Environment drift monitor v3 (Phase 5, offline).

Reads harness.db attempts and builds a per-(model, scenario) behaviour timeline:
tool-called rate, refusal-like rate, mean score, EWMA and CUSUM on tool-called.
Detects change points WITHOUT attributing them to a specific cause.

Usage: python3 harness/drift.py [--db artifacts/harness.db] [--out artifacts/env-timeline.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def load_rows(db: pathlib.Path):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = []
    for r in conn.execute(
            "SELECT attempt_id, scenario, model, delta, state, pcts, score, verdict,"
            " started_at, finished_at FROM attempts ORDER BY rowid"):
        pcts = None
        try:
            pcts = json.loads(r["pcts"]) if r["pcts"] else None
        except Exception:
            pcts = None
        rows.append({"id": r["attempt_id"], "scenario": r["scenario"], "model": r["model"],
                     "delta": r["delta"], "state": r["state"], "pcts": pcts,
                     "score": r["score"], "verdict": r["verdict"],
                     "ts": r["finished_at"] or r["started_at"]})
    return rows


def tool_called(row) -> int | None:
    if not row["pcts"] or len(row["pcts"]) < 2:
        return None
    v = row["pcts"][1]
    return 1 if v == 100 else 0


def analyse(rows, alpha: float = 0.2, k: float = 0.5, h: float = 4.0):
    per = {}
    for r in rows:
        key = f"{r['scenario']}|{r['model']}"
        per.setdefault(key, []).append(r)
    out = {"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
           "alpha": alpha, "cusum_k": k, "cusum_h": h, "series": {}}
    for key, rs in per.items():
        tc = [(i, tool_called(r), r) for i, r in enumerate(rs)]
        tc = [(i, v, r) for i, v, r in tc if v is not None]
        if not tc:
            continue
        ewma = None
        csum_pos = csum_neg = 0.0
        drift_flags = []
        for i, v, r in tc:
            ewma = v if ewma is None else alpha * v + (1 - alpha) * ewma
            mu = 0.5  # baseline reference: 1.0 in hot windows, 0.0 in walls
            csum_pos = max(0.0, csum_pos + (v - mu) - k * 0.1)
            csum_neg = max(0.0, csum_neg + (mu - v) - k * 0.1)
            if csum_pos > h or csum_neg > h:
                drift_flags.append({"at": i, "ts": r["ts"], "state": r["state"],
                                    "tool_called": v, "cusum": round(csum_pos - csum_neg, 2)})
                csum_pos = csum_neg = 0.0
        scores = [r["score"] for _, _, r in tc if isinstance(r["score"], (int, float))]
        out["series"][key] = {
            "n": len(tc),
            "tool_rate": round(sum(v for _, v, _ in tc) / len(tc), 3),
            "ewma_tool": round(ewma or 0, 3),
            "mean_score": round(sum(scores) / len(scores), 1) if scores else None,
            "last_ts": tc[-1][2]["ts"],
            "drift_flags": drift_flags[-5:],
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--out", default=str(WORK / "artifacts" / "env-timeline.json"))
    a = ap.parse_args()
    rows = load_rows(pathlib.Path(a.db))
    res = analyse(rows)
    pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"attempts={len(rows)} series={len(res['series'])} -> {a.out}")
    for key, s in sorted(res["series"].items()):
        flag = f"  ⚠ drift×{len(s['drift_flags'])}" if s["drift_flags"] else ""
        print(f"  {key:58s} n={s['n']:4d} tool={s['tool_rate']:.2f} ewma={s['ewma_tool']:.2f}"
              f" score={s['mean_score']}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())