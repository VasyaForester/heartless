#!/usr/bin/env python3
"""Per-pair accounting snapshot from harness.db (read-only). 2026-11-13."""
import pathlib
import sqlite3
import sys
import time

WORK = pathlib.Path(__file__).resolve().parent.parent
db = WORK / "artifacts" / "harness.db"
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)

pcols = [r[1] for r in conn.execute("PRAGMA table_info(pairs)")]
print("pairs cols:", pcols)

print("\n== pairs ==")
for r in conn.execute("SELECT * FROM pairs ORDER BY solved, id"):
    d = dict(r)
    print(f"  solved={d.get('solved')} attempts={d.get('attempts'):>4} best={d.get('best_score')} "
          f"{d.get('id')}")

acols = [r[1] for r in conn.execute("PRAGMA table_info(attempts)")]
print("\nattempts cols:", acols)
idc = "pair_id" if "pair_id" in acols else ("pair" if "pair" in acols else None)
stc = "status" if "status" in acols else None
tsc = next((c for c in ("updated_at", "created_at", "started_at", "ts") if c in acols), None)
scc = "score" if "score" in acols else None
if idc:
    q = f"SELECT {idc} AS pid, COUNT(*) n"
    if stc:
        q += f", SUM(CASE WHEN {stc}='judged' THEN 1 ELSE 0 END) judged"
    if scc:
        q += f", MAX({scc}) smax"
    if tsc:
        q += f", MAX({tsc}) last"
    q += f" FROM attempts GROUP BY {idc}"
    print("\n== attempts per pair ==")
    for r in conn.execute(q):
        d = dict(r)
        last = d.get("last")
        if isinstance(last, (int, float)) and last > 1e9:
            last = time.strftime("%H:%M", time.localtime(last))
        print(f"  n={d['n']:>4} judged={d.get('judged')} smax={d.get('smax')} last={last}  {d['pid']}")

# last hour cadence
if tsc and idc:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM attempts WHERE {tsc} > ?",
                           (time.time() - 3600,)).fetchone()
        print(f"\nattempts last 60 min: {row[0]}")
    except Exception as exc:
        print("cadence err:", exc)
sys.exit(0)