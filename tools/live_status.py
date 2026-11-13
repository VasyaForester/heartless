#!/usr/bin/env python3
"""Live lane status: recent attempts/judges/submissions + energy, read-only."""
import pathlib
import sqlite3
import time

W = pathlib.Path(__file__).resolve().parent.parent
conn = sqlite3.connect(f"file:{W / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row


def fmt(ts):
    return time.strftime("%H:%M", time.localtime(ts)) if isinstance(ts, (int, float)) and ts > 1e9 else ts


print("== last 12 attempts ==")
for r in conn.execute("SELECT pair_id,state,verdict,score,reward,started_at,submitted_at,"
                      "finished_at,delta FROM attempts ORDER BY started_at DESC LIMIT 12"):
    d = dict(r)
    print(f"  {fmt(d['started_at'])} {str(d['pair_id'])[:46]:46s} st={str(d['state'])[:16]:16s} "
          f"v={str(d['verdict'])[:10]:10s} sc={d['score']} rw={d['reward']} d={str(d['delta'])[:22]}")

print("\n== attempts last 2h by pair ==")
cut = time.time() - 7200
for r in conn.execute("SELECT pair_id, COUNT(*) n, SUM(CASE WHEN submitted_at IS NOT NULL THEN 1 ELSE 0 END) sub,"
                      " AVG(reward) arw FROM attempts WHERE started_at > ? GROUP BY pair_id ORDER BY n DESC",
                      (cut,)):
    d = dict(r)
    print(f"  n={d['n']:>3} sub={d['sub']:>3} avg_rw={round(d['arw'] or 0, 2)}  {d['pair_id']}")

print("\n== judges table (schema + last 8) ==")
cols = [r[1] for r in conn.execute("PRAGMA table_info(judges)")]
print("  cols:", cols)
try:
    for r in conn.execute("SELECT * FROM judges ORDER BY rowid DESC LIMIT 8"):
        d = dict(r)
        print("  ", {k: d[k] for k in list(d)[:7]})
except Exception as exc:  # noqa: BLE001
    print("  err:", exc)

print("\n== verdicts by status (all time) ==")
for r in conn.execute("SELECT judge_status, COUNT(*) FROM attempts GROUP BY judge_status"):
    print("  ", dict(r))