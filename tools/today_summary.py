#!/usr/bin/env python3
"""Сводка за сегодня: попытки, рендеры, вердикты, энергии."""
import json
import pathlib
import sqlite3
import time

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cut = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 00:00", "%Y-%m-%d %H:%M"))

print("== попытки сегодня по парам ==")
for r in conn.execute("SELECT pair_id, COUNT(*) n, AVG(reward) arw FROM attempts "
                      "WHERE started_at > ? GROUP BY pair_id ORDER BY n DESC", (cut,)):
    d = dict(r)
    print(f"  n={d['n']:4d} avg_rw={round(d['arw'] or 0, 3)}  {d['pair_id']}")

print("\n== судейские статусы сегодня ==")
for r in conn.execute("SELECT judge_status, COUNT(*) c FROM attempts WHERE started_at > ? "
                      "GROUP BY judge_status", (cut,)):
    print(" ", dict(r))

print("\n== вердикты с оценкой сегодня ==")
rows = list(conn.execute("SELECT score,pcts,pair_id,attempt_id FROM attempts "
                         "WHERE started_at > ? AND score IS NOT NULL ORDER BY score DESC LIMIT 6",
                         (cut,)))
for d in rows:
    print(f"  score={d['score']:>3} pcts={d['pcts']} {d['pair_id']} {d['attempt_id'][-12:]}")
if not rows:
    print("  нет")

print("\n== энергия (последние строки лога) ==")
try:
    import re
    txt = (W / "artifacts" / "driver.log").read_text(errors="replace").splitlines()[-400:]
    vals = [m.group(1) for l in txt for m in [re.search(r"energy=(-?\d+)", l)] if m]
    print("  ", vals[-3:])
except Exception as exc:  # noqa: BLE001
    print("  err:", exc)