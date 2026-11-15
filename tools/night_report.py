#!/usr/bin/env python3
"""Итоги ночи: судьи, рендеры, топ-скоры, попытки по парам (с 00:00)."""
import json
import pathlib
import sqlite3
import time

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cut = time.mktime(time.strptime("2026-11-14 00:00", "%Y-%m-%d %H:%M"))

print("== попытки/рендеры с 00:00 (рендер = есть judge_raw) ==")
stats = {}
for d in (W / "artifacts" / "attempts").iterdir():
    if not d.is_dir():
        continue
    tp = d / "transcript.json"
    if not tp.is_file() or tp.stat().st_mtime < cut:
        continue
    key = d.name.replace("lucky-break-payday_", "").rsplit("_main_", 1)[0]
    s = stats.setdefault(key, {"n": 0, "r": 0})
    s["n"] += 1
    if (d / "judge_raw.json").is_file():
        s["r"] += 1
for k, s in sorted(stats.items()):
    print(f"  {k:50s} probes={s['n']:4d} renders={s['r']:3d}")

print("\n== попытки в БД с 00:00 ==")
for r in conn.execute("SELECT pair_id, COUNT(*) n, AVG(reward) arw FROM attempts "
                      "WHERE started_at > ? GROUP BY pair_id ORDER BY n DESC", (cut,)):
    d = dict(r)
    print(f"  n={d['n']:4d} avg_rw={round(d['arw'] or 0, 3)}  {d['pair_id']}")

print("\n== судьи с 00:00 ==")
for r in conn.execute("SELECT status, COUNT(*) c FROM judges WHERE captured_at > ? GROUP BY status",
                      (time.strftime("%Y-%m-%dT00:00", time.localtime(cut)),)):
    print(" ", dict(r))
for r in conn.execute("SELECT attempt_id, status, score FROM judges WHERE captured_at > ? "
                      "ORDER BY captured_at DESC LIMIT 6",
                      (time.strftime("%Y-%m-%dT00:00", time.localtime(cut)),)):
    d = dict(r)
    print(f"  {d['status']} score={d['score']} {d['attempt_id'][-30:]}")

print("\n== топ-скоры за всё время ==")
for r in conn.execute("SELECT score, pcts, pair_id FROM attempts WHERE score IS NOT NULL "
                      "ORDER BY score DESC LIMIT 5"):
    d = dict(r)
    print(f"  {d['score']:>3} {d['pcts']} {d['pair_id']}")