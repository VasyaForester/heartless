#!/usr/bin/env python3
"""Check the acceptance of `reports/agent-task-reward-2026-11-15.md` on live data.

The task's "done when" is partly a LIVE claim ("the next 50 live attempts have zero
`reward_source='local'`", "no new deltas while a pair has fewer than two verified
judges").  This is the repeatable read-only view of exactly those numbers, so the claim
can be checked by running one command instead of trusting a sentence:

    python3 tools/teacher_check.py [--n 50] [--board lucky-break-payday] [--json]

Exit code 0 when the acceptance holds, 1 when it does not, 2 when the window is not yet
full (the criterion is about a number of attempts that has to accumulate).  It never
writes anything: `mode=ro`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

W = pathlib.Path(__file__).resolve().parent.parent
A = W / "artifacts"


def window_start(conn, explicit: str | None):
    """When the judge became the only teacher: the boundary this check counts from.

    Default comes from the JOURNAL, not from a guess: `target_binding` is written once per
    driver run (`driver._bind_target`), so the newest one IS the start of the run whose
    attempts we are grading.  `--since` overrides it (epoch seconds or a `...T..:..:..`
    stamp).  Why it matters: "the last 50 attempts" reaches back into the previous run and
    grades the old teacher's rows — the criterion is about the attempts AFTER the change.
    """
    if explicit:
        text = str(explicit).strip()
        if text.replace(".", "", 1).isdigit():
            return float(text)
        import time as _t
        return _t.mktime(_t.strptime(text, "%Y-%m-%dT%H:%M:%S"))
    row = conn.execute("SELECT payload FROM events WHERE kind='target_binding'"
                       " ORDER BY rowid DESC LIMIT 1").fetchone()
    if row:
        import time as _t
        try:
            return _t.mktime(_t.strptime(json.loads(row["payload"])["at"], "%Y-%m-%dT%H:%M:%S"))
        except Exception:  # noqa: BLE001 — fall through to the reward-channel boundary
            pass
    row = conn.execute("SELECT MIN(started_at) AS t FROM attempts"
                       " WHERE reward_source='missing'").fetchone()
    return float(row["t"] or 0.0) if row else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(A / "harness.db"))
    ap.add_argument("--board", default="lucky-break-payday")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--since", default=None,
                    help="start of the window (epoch or 2026-11-15T20:00:17); default: "
                         "the newest target_binding event (the current driver run)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    since = window_start(conn, a.since)

    rows = list(conn.execute(
        "SELECT attempt_id, pair_id, delta, reward_source, judge_status, score, verdict,"
        " started_at FROM attempts WHERE board_profile=? AND started_at>=?"
        " ORDER BY started_at DESC LIMIT ?", (a.board, since, a.n)))
    if not rows:
        print("no attempts for this board")
        return 2

    local = [r for r in rows if str(r["reward_source"]) == "local"]
    verified = [r for r in rows if str(r["judge_status"]) == "verified"]
    accepted = [r for r in verified if str(r["verdict"]) in ("accepted", "solved")]
    missing = [r for r in rows if str(r["reward_source"]) == "missing"]

    # "New delta" = a delta this pair had never sent before the window opened.
    oldest = min(float(r["started_at"] or 0) for r in rows)
    novel = []
    for r in rows:
        prev = conn.execute(
            "SELECT COUNT(*) FROM attempts WHERE pair_id=? AND delta=? AND started_at<?",
            (r["pair_id"], r["delta"], oldest)).fetchone()[0]
        if not prev:
            peers = conn.execute(
                "SELECT COUNT(*) FROM attempts WHERE pair_id=? AND started_at<?",
                (r["pair_id"], oldest)).fetchone()[0]
            novel.append({"pair": r["pair_id"], "delta": r["delta"], "prior_attempts": peers})

    gate_ok = all(n["prior_attempts"] < 2 for n in novel)
    window_full = len(rows) >= a.n

    out = {
        "board": a.board, "window": len(rows), "asked": a.n,
        "reward_source": {"missing": len(missing), "local": len(local)},
        "verified": len(verified), "accepted": len(accepted),
        "unseen_deltas": len(novel),
        "unseen_deltas_ok": gate_ok,
        "verdict": ("PASS" if (window_full and not local and gate_ok)
                    else "PENDING" if not window_full else "FAIL")
    }
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if out["verdict"] == "PASS" else (2 if out["verdict"] == "PENDING" else 1)

    print(f"доска {a.board}; последних попыток: {len(rows)} (критерий — {a.n})")
    print(f"  reward_source: missing={len(missing)} local={len(local)}"
          f"{'  ← НАРУШЕНИЕ' if local else '  ← суррогат не учит'}")
    print(f"  verified={len(verified)}  accepted={len(accepted)}")
    print(f"  дельт, которых у пары не было: {len(novel)}"
          f"{'' if gate_ok else '  ← ПОРОГ НАРУШЕН'}")
    for n in novel[:6]:
        print(f"     {n['pair']} / {n['delta']} (у пары было проб: {n['prior_attempts']})")
    print(f"  ИТОГ: {out['verdict']}"
          + ("" if window_full else "  (окно ещё не набрано — критерий про накопление)"))
    return 0 if out["verdict"] == "PASS" else (2 if out["verdict"] == "PENDING" else 1)


if __name__ == "__main__":
    sys.exit(main())
