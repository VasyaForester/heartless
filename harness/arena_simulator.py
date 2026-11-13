#!/usr/bin/env python3
"""Arena Simulator v3 (Phase 4, offline regression harness).

Replays synthetic attempt lifecycles through the REAL state machine
(attempts.mark_submitted / mark_judge / finalize + store.transition) inside a
temporary SQLite DB — no browser, no submissions. Covers the judge-status
matrix that broke the live driver on 2026-11-13:

  verified -> judged -> finalized          pending -> awaiting_judge
  stale / missing / mismatched -> judge_failed   (the 14:31 crash case)
  submission_uncertain -> submission_uncertain

Usage: python3 harness/arena_simulator.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import attempts  # noqa: E402
import store  # noqa: E402

CASES = [
    {"status": "verified", "score": 210, "pcts": [20, 100, 90], "verdict": "rejected"},
    {"status": "pending"},
    {"status": "stale"},
    {"status": "missing"},
    {"status": "mismatched_operation"},
    {"status": "submission_uncertain"},
    {"status": "verified", "score": 300, "pcts": [100, 100, 100], "verdict": "accepted"},
]
EXPECTED = {"verified": "finalized", "pending": "awaiting_judge", "stale": "judge_failed",
            "missing": "judge_failed", "mismatched_operation": "judge_failed",
            "submission_uncertain": "submission_uncertain"}


def sim(conn, lease, case) -> dict:
    """One attempt lifecycle through the production code path."""
    aid = attempts.allocate(conn, lease, pair_id="sim", board="sim",
                            scenario="sim-scn", model="sim-model", lane="sim")
    attempts.prepare(conn, lease, aid, input_text="probe", input_path="inputs/sim.txt",
                     delta="append_test")
    st = case["status"]
    if st == "submission_uncertain":
        attempts.mark_submitted(conn, lease, aid, chat_id="sim-chat",
                                transcript_text="sim transcript")
        attempts.mark_uncertain(conn, lease, aid, "sim")
    else:
        attempts.mark_submitted(conn, lease, aid, chat_id="sim-chat",
                                transcript_text="sim transcript")
        if st == "pending":
            attempts.mark_awaiting(conn, lease, aid, judge_ref=f"j-{aid}")
        else:
            result = {"status": st, "judge_ref": f"j-{aid}",
                      "score": case.get("score"), "pcts": case.get("pcts"),
                      "verdict": case.get("verdict"), "reason": "sim"}
            attempts.mark_judge(conn, lease, aid, result)
            if st == "verified":
                attempts.finalize(conn, lease, aid, solved=case.get("verdict") == "accepted")
    row = conn.execute("SELECT state FROM attempts WHERE attempt_id=?", (aid,)).fetchone()
    return {"case": st, "attempt": aid, "final": row["state"] if row else "?"}


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="arena-sim-")) / "sim.db"
    conn = store.connect(tmp)  # connect() migrates automatically
    # FK seed: attempts.pair_id references pairs(id)
    conn.execute("INSERT OR REPLACE INTO board_profiles(profile_id,name,version,url,win_string,"
                 "profile_hash,loaded_at) VALUES('sim@1','sim',1,'https://sim.invalid','WIN','sim',0)")
    conn.execute("INSERT OR REPLACE INTO pairs(id,board_profile,scenario,model,solved,"
                 "best_score,attempts,version) VALUES('sim','sim','sim-scn','sim-model',0,-1,0,0)")
    lease = store.acquire_lease(conn, "sim", "sim-target")
    if not lease:
        print(json.dumps({"error": "cannot acquire lease"}))
        return 1
    failures, trace = [], []
    for case in CASES:
        try:
            tr = sim(conn, lease, case)
        except Exception as exc:  # noqa: BLE001
            failures.append({"case": case["status"], "error": f"{type(exc).__name__}: {exc}"})
            continue
        trace.append(tr)
        if tr["final"] != EXPECTED[case["status"]]:
            failures.append({"case": case["status"], "final": tr["final"],
                             "expected": EXPECTED[case["status"]]})
    print(json.dumps({"cases": len(CASES), "passed": len(CASES) - len(failures),
                      "failures": failures, "trace": trace}, ensure_ascii=False, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())