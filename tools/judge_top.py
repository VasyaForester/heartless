#!/usr/bin/env python3
"""Verified judges with scores (read-only)."""
import json
import pathlib
import sqlite3

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

rows = list(conn.execute("SELECT * FROM judges WHERE status='verified' ORDER BY captured_at DESC"))
print(f"verified judges: {len(rows)}\n")
for r in rows:
    d = dict(r)
    print(f"{d['captured_at']}  score={d.get('score')}  verified={d.get('verified')}")
    print(f"  attempt={d['attempt_id']}")
    p = d.get("raw_path") or d.get("judge_ref")
    print(f"  raw={p}")
    try:
        raw = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        keep = {k: raw.get(k) for k in ("status", "score", "pcts", "verdict", "operationId",
                                        "criteria", "result") if k in raw}
        print("  raw:", json.dumps(keep, ensure_ascii=False)[:600])
    except Exception as exc:  # noqa: BLE001
        print("  raw unreadable:", exc)
    print()

print("== highest scored attempts (any status, score not null) ==")
for r in conn.execute("SELECT pair_id,score,pcts,verdict,judge_status,started_at FROM attempts "
                      "WHERE score IS NOT NULL ORDER BY score DESC LIMIT 8"):
    d = dict(r)
    print(f"  score={d['score']:>3} pcts={d['pcts']} v={d['verdict']} st={d['judge_status']} {d['pair_id']}")