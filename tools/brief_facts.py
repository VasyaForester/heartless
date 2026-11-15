#!/usr/bin/env python3
"""Сбор фактов для брифа: решённые клетки, критерии остальных сценариев, победный refund-кадр."""
import json
import pathlib
import sqlite3

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

print("== solved-клетки ==")
for r in conn.execute("SELECT id FROM pairs WHERE solved=1 ORDER BY id"):
    print("  ", r["id"])

print("\n== критерии: double-refund / scam-retail ==")
d = json.loads((W / "datasets" / "lbp" / "criteria.json").read_text(encoding="utf-8"))
for sid in ("double-refund", "scam-retail"):
    g = d["scenarios"].get(sid) or {}
    print(f"\n-- {sid} --")
    print(json.dumps({k: g.get(k) for k in ("class", "target_tool", "assertions", "judge_criteria")},
                     ensure_ascii=False, indent=1)[:900])

print("\n== победный refund-транскрипт (user+assistant) ==")
for p in (W / "artifacts").glob("lbp-double-refund-*-submit-transcript.json"):
    try:
        tr = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        continue
    print(f"\n-- {p.name}")
    for m in tr.get("messages", [])[:2]:
        print(f"[{m.get('role')}] {(m.get('text') or '')[:700]}")
        print("  ---")