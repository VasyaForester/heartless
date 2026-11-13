#!/usr/bin/env python3
"""Do our attempts really submit? (2026-11-13)."""
import json
import pathlib
import sqlite3
import time

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

print("== execution_status (last 2h) ==")
cut = time.time() - 7200
for r in conn.execute("SELECT execution_status, judge_status, COUNT(*) n FROM attempts "
                      "WHERE started_at > ? GROUP BY execution_status, judge_status ORDER BY n DESC",
                      (cut,)):
    print("  ", dict(r))

print("\n== last 3 attempts ==")
rows = list(conn.execute("SELECT * FROM attempts ORDER BY started_at DESC LIMIT 3"))
for d in rows:
    print(f"  {d['attempt_id']}")
    print(f"    exec={d['execution_status']} judge={d['judge_status']} state={d['state']} "
          f"submitted_at={d['submitted_at']} input={d['input_path']}")

print("\n== repeats.jsonl rows for these ==")
rp = W / "datasets" / "lbp" / "repeats.jsonl"
ids = {d["attempt_id"] for d in rows}
found = 0
if rp.is_file():
    for line in reversed(rp.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("opid") in ids:
            found += 1
            keep = {k: row.get(k) for k in ("opid", "scenario", "model", "submitted", "verdict",
                                            "status", "score", "energy", "tool_called", "sent_ok",
                                            "input") if k in row}
            print("  ", json.dumps(keep, ensure_ascii=False)[:500])
print(f"  found={found}")

print("\n== latest attempt transcript (assistant) ==")
d0 = max((W / "artifacts" / "attempts").glob("lucky-break-payday_negative*"),
         key=lambda p: p.stat().st_mtime, default=None)
if d0:
    print("  dir:", d0.name)
    tp = d0 / "transcript.json"
    if tp.is_file():
        try:
            tr = json.loads(tp.read_text(encoding="utf-8", errors="replace"))
            for m in tr.get("messages", []):
                if m.get("role") == "assistant":
                    print("  A:", (m.get("text") or "")[:400].replace("\n", " | "))
        except Exception as exc:  # noqa: BLE001
            print("  err:", exc)