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


print("\n== last 12 attempts ==")
for r in conn.execute("SELECT pair_id,state,verdict,score,reward,reward_source,started_at,submitted_at,"
                      "finished_at,delta FROM attempts ORDER BY started_at DESC LIMIT 12"):
    d = dict(r)
    print(f"  {fmt(d['started_at'])} {str(d['pair_id'])[:46]:46s} st={str(d['state'])[:16]:16s} "
          f"v={str(d['verdict'])[:10]:10s} sc={d['score']} rw={d['reward']} "
          f"src={d['reward_source']} d={str(d['delta'])[:22]}")

# Task 2026-11-15, item 5: the live view counts the JUDGE, not the surrogate.  The mean
# local reward is gone on purpose: it was the number the operator was reading while the
# selector learned from it (0.32 mean against the judge's 0.08), and it is a diagnostic now.
print("\n== last 6h by pair: attempts / verified / accepted / mean verified score ==")
cut = time.time() - 6 * 3600
tot = {"n": 0, "ver": 0, "acc": 0}
rows6 = list(conn.execute(
    "SELECT pair_id, COUNT(*) n,"
    " SUM(CASE WHEN judge_status='verified' THEN 1 ELSE 0 END) ver,"
    " SUM(CASE WHEN judge_status='verified' AND verdict IN ('accepted','solved')"
    "          THEN 1 ELSE 0 END) acc,"
    " AVG(CASE WHEN judge_status='verified' AND score IS NOT NULL THEN score END) msc"
    " FROM attempts WHERE COALESCE(started_at,0) > ? GROUP BY pair_id ORDER BY n DESC",
    (cut,)))
for r in rows6:
    d = dict(r)
    n = int(d["n"] or 0)
    ver = int(d["ver"] or 0)
    acc = int(d["acc"] or 0)
    tot["n"] += n
    tot["ver"] += ver
    tot["acc"] += acc
    share = (ver / n) if n else 0.0
    msc = "-" if d["msc"] is None else round(float(d["msc"]), 1)
    print(f"  n={n:>3} verified={ver:>3} ({share:5.1%}) accepted={acc} "
          f"mean_verified_score={msc}  {d['pair_id']}")
if tot["n"]:
    print(f"  TOTAL n={tot['n']} verified={tot['ver']} "
          f"({tot['ver'] / tot['n']:.1%}) accepted={tot['acc']}")

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