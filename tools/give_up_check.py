"""What would the give-up rule park right now?  (read-only, changes nothing)

The rule (advice #6, RULES 92) parks a pair for a few hours when it has stopped
moving: at least `min_probes` probes inside the last `window_hours` with no reward
at or above `max_reward`.  It is decided from data, so it is worth being able to
LOOK at the decision before trusting it — this is that view.

    python3 tools/give_up_check.py [--db artifacts/harness.db] [--json]

Exit code is 0 whatever it finds: this is an operator's window, not a gate.
"""

import argparse
import json
import pathlib
import sqlite3
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(WORK / "harness"))

import driver  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--board", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    board = a.board or driver.BOARD_NAME
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    now = time.time()
    since = now - driver.GIVE_UP["window_hours"] * 3600.0
    rows = []
    for r in conn.execute(
            "SELECT id FROM pairs WHERE solved=0 AND best_input IS NOT NULL"
            " AND board_profile=? ORDER BY id", (board,)):
        key = r["id"]
        w = conn.execute(
            "SELECT COUNT(*) AS n,"
            " SUM(CASE WHEN judge_status='verified' AND COALESCE(score,0) > 0"
            "          THEN 1 ELSE 0 END) AS paid"
            " FROM attempts WHERE pair_id=? AND COALESCE(started_at,0) >= ?",
            (key, since)).fetchone()
        n, paid = int(w["n"] or 0), int(w["paid"] or 0)
        rows.append({"pair": key, "probes_in_window": n, "verified_paid_in_window": paid,
                     "would_park": (n >= driver.GIVE_UP["min_probes"] and paid == 0)})
    conn.close()

    if a.json:
        print(json.dumps({"board": board, "rule": driver.GIVE_UP, "pairs": rows},
                         ensure_ascii=False, indent=1))
        return 0
    print(f"board {board}; правило: >= {driver.GIVE_UP['min_probes']} проб за "
          f"{driver.GIVE_UP['window_hours']:g}ч и НИ ОДНОЙ проверенной судьи со счётом выше "
          f"нуля → парковка на {driver.GIVE_UP['park_hours']:g}ч "
          f"(колонка reward в решении не читается)\n")
    print(f"{'пара':<50}{'проб':>6}{'судья>0':>9}  решение")
    for r in rows:
        verdict = "ПАРКОВКА" if r["would_park"] else ""
        print(f"  {r['pair']:<48}{r['probes_in_window']:>6}"
              f"{r['verified_paid_in_window']:>9}  {verdict}")
    print(f"\nзапарковалось бы: {sum(1 for r in rows if r['would_park'])} из {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
