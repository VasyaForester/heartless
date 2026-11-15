#!/usr/bin/env python3
"""Базовые входы пар + победный CT-транскрипт."""
import json
import pathlib
import sqlite3

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
print("== best_input по незакрытым парам ==")
for r in conn.execute("SELECT id,best_input,attempts FROM pairs WHERE solved=0 ORDER BY id"):
    print(f"  {r['id']:52s} base={r['best_input']}")

p = W / "artifacts" / "lbp-banking-idor-exploit-copper-turtle-brave-submit-transcript.json"
print("\n== победный CT-транскрипт ==", p.is_file())
if p.is_file():
    d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    for m in d.get("messages", []):
        print(f"[{m.get('role')}] {(m.get('text') or '')[:1000]}")
        print("---")

v = W / "inputs" / "lbp-bank-v55-selfcheck-verbatim.txt"
print("\n== v55 (кадр, который есть в inputs) ==", v.is_file())
if v.is_file():
    print(v.read_text(encoding="utf-8", errors="replace")[:900])