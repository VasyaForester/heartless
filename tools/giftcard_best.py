#!/usr/bin/env python3
"""Что именно судья оценил в лучших giftcard-пробах (c1=30) и чего не хватает."""
import json
import pathlib
import sqlite3

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

print("== критерии giftcard ==")
crit = W / "datasets" / "lbp" / "criteria.json"
if crit.is_file():
    d = json.loads(crit.read_text(encoding="utf-8"))
    s = json.dumps(d, ensure_ascii=False)
    print(s[:1500])

print("\n== лучшие giftcard-попытки (score>=100) ==")
for r in conn.execute("SELECT attempt_id, score, pcts, delta, input_path FROM attempts "
                      "WHERE pair_id LIKE 'christmas-giftcard-scam|%' AND score >= 100 "
                      "ORDER BY score DESC LIMIT 6"):
    d = dict(r)
    print(f"  score={d['score']} pcts={d['pcts']} delta={d['delta']}")
    aid = d["attempt_id"]
    suffix = aid.rsplit(":", 1)[-1]
    dirs = list((W / "artifacts" / "attempts").glob(f"*{suffix}"))
    if not dirs:
        print("    evidence: нет")
        continue
    dd = dirs[0]
    tp = dd / "transcript.json"
    if tp.is_file():
        try:
            tr = json.loads(tp.read_text(encoding="utf-8", errors="replace"))
            a = [m.get("text") or "" for m in tr.get("messages", []) if m.get("role") == "assistant"]
            print(f"    A: {(a[-1] if a else '')[:600].replace(chr(10), ' | ')}")
        except Exception as exc:  # noqa: BLE001
            print("    err:", exc)