#!/usr/bin/env python3
"""Export the v2 SQLite pair state to a JSONL journal.

The SQLite DB (`artifacts/harness.db`) is the live truth.  This export is a
derived, human-readable snapshot for review/archival; it never writes back.
The legacy `datasets/lbp/pairs.jsonl` is left untouched (it carries notes that
predate the v2 schema).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--out", default=str(WORK / "datasets" / "lbp" / "pairs-v2.jsonl"))
    a = ap.parse_args()

    db = pathlib.Path(a.db)
    if not db.is_file():
        print(f"db not found: {db}")
        return 1
    conn = sqlite3.connect(str(db), timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id,scenario,model,solved,best_score,best_input,attempts,last_verdict "
        "FROM pairs ORDER BY scenario, model"
    ).fetchall()
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            last = conn.execute(
                "SELECT id,started,finished,rc,verdict,score,pcts,energy,delta,input "
                "FROM attempts WHERE pair_id=? ORDER BY id DESC LIMIT 1", (r["id"],)
            ).fetchone()
            rec = {
                "schema": "lbp-pairs-v2",
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "pair_id": r["id"],
                "scenario": r["scenario"],
                "model": r["model"],
                "solved": bool(r["solved"]),
                "best_score": r["best_score"],
                "best_input": r["best_input"],
                "attempts": r["attempts"],
                "last_verdict": r["last_verdict"],
                "last_attempt": dict(last) if last else None,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    conn.close()
    print(f"exported {n} pairs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())