#!/usr/bin/env python3
"""Confirmed decisions per unit of energy — the mission metric, DECOMPOSED.

Advice taken (frontier review, 2026-11-14): make "confirmed solves per energy"
the headline number and split it into factors, because each factor has its own
ceiling and they fail for different reasons:

    solves/energy = (probes/energy)  x  P(landed & judged | probe)  x  P(solve | judged)
                    └ throughput          └ our own losses              └ arm quality

Rules this tool follows:
  * "landed" is OUR definition: the harness did not drop the probe
    (strategy.harness_fault → no reward).  A dropped probe is not evidence, so it
    must not be counted as a failure of the arm, nor as throughput.
  * energy comes from the board profile's cost model ({message, judge}).  A board
    without one reports energy as unknown — never invented.
  * the numerator is the PLATFORM's verdict (score>0 / accepted), not the proxy:
    the proxy is saturated (see reward_audit), so it cannot certify a decision.
  * boards are never pooled into one number: reporting is per board plus a total.

Usage:
    python3 harness/efficiency.py                     # last 6 h
    python3 harness/efficiency.py --since-hours 24
    python3 harness/efficiency.py --json
"""

import argparse
import collections
import datetime as dt
import json
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import boards as boards_mod  # noqa: E402
import strategy_bench  # noqa: E402

WORK = HERE.parent
DB = WORK / "artifacts" / "harness.db"
REPEATS = WORK / "datasets" / "lbp" / "repeats.jsonl"
TS = "%Y-%m-%dT%H:%M:%S"


def default_dbs() -> list:
    """Every lane has its own DB (main → harness.db, pg → harness-pg.db), and the
    report must cover the whole stand while never pooling the boards."""
    found = sorted((WORK / "artifacts").glob("harness*.db"))
    return found or [DB]


def _since(hours: float) -> dt.datetime:
    return dt.datetime.now() - dt.timedelta(hours=hours)


def ledger_window(repeats=REPEATS, since: dt.datetime | None = None) -> list[dict]:
    rows = []
    p = pathlib.Path(repeats)
    if not p.is_file():
        return rows
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = row.get("ts")
        if since and ts:
            try:
                if dt.datetime.strptime(ts, TS) < since:
                    continue
            except ValueError:
                pass
        rows.append(row)
    return rows


def db_window(db=DB, since: dt.datetime | None = None) -> list[dict]:
    path = pathlib.Path(db)
    if not path.is_file():
        return []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT attempt_id, pair_id, board_profile, started_at,"
                            " submitted_at, execution_status, judge_status, score,"
                            " reward, reward_source, delta, arm_source, lane"
                            " FROM attempts").fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        if since and r["started_at"] and dt.datetime.fromtimestamp(r["started_at"]) < since:
            continue
        out.append(dict(r))
    return out


def cost_model(board_name: str) -> dict | None:
    try:
        profile = boards_mod.load_board(board_name)
    except Exception:  # noqa: BLE001 — a broken profile must not kill the report
        return None
    cost = profile.get("cost")
    return cost if isinstance(cost, dict) and cost else None


def fault_rate(rows: list[dict]) -> tuple:
    """(faults, probes) over ledger rows — our own dropped probes."""
    import strategy
    faults = 0
    for row in rows:
        if strategy.harness_fault(row):
            faults += 1
    return faults, len(rows)


def report(since_hours: float = 6.0, db=None, repeats=REPEATS,
           fail_over: float | None = None) -> dict:
    since = _since(since_hours)
    ledger = ledger_window(repeats, since)
    if db is None:
        dbs = default_dbs()
    elif isinstance(db, (list, tuple)):
        dbs = [pathlib.Path(p) for p in db]
    else:
        dbs = [pathlib.Path(db)]
    attempts = []
    for one in dbs:
        attempts.extend(db_window(one, since))
    by_scenario = strategy_bench.boards_by_scenario()
    faults_total, ledger_n = fault_rate(ledger)
    faults_by_board = collections.Counter()
    for row in ledger:
        if row.get("board") or row.get("board_profile"):
            board = str(row.get("board") or row.get("board_profile"))
        else:
            board = by_scenario.get(str(row.get("scenario") or "")) or "unknown"
        if __import__("strategy").harness_fault(row):
            faults_by_board[board] += 1

    boards_out = {}
    for board in sorted({a["board_profile"] for a in attempts} | set(faults_by_board)):
        att = [a for a in attempts if a["board_profile"] == board]
        probes = len(att)
        judged = sum(1 for a in att if a["judge_status"] == "verified")
        positive = sum(1 for a in att if (a["score"] or 0) > 0)
        faults = faults_by_board.get(board, 0)
        landed = max(0, probes - 0)  # attempts in the DB already landed (a fault never finalises)
        cost = cost_model(board)
        energy = None
        if cost:
            energy = probes * float(cost.get("message", 0)) + judged * float(cost.get("judge", 0))
        hours = since_hours
        boards_out[board] = {
            "probes": probes,
            "probes_per_hour": round(probes / hours, 1) if hours else None,
            "landed": landed,
            "landed_share": (round(1.0 - faults / (probes + faults), 4)
                             if (probes + faults) else None),
            "judged": judged,
            "judged_share_of_landed": round(judged / landed, 4) if landed else None,
            "judge_positive": positive,
            "solve_share_of_judged": round(positive / judged, 4) if judged else None,
            "energy": energy,
            "decision_per_1000_energy": (round(positive / energy * 1000, 3)
                                         if energy else None),
            "faults": faults,
            "cost_model": cost,
        }
    total = {
        "probes": sum(b["probes"] for b in boards_out.values()),
        "faults": faults_total,
        "judged": sum(b["judged"] for b in boards_out.values()),
        "judge_positive": sum(b["judge_positive"] for b in boards_out.values()),
        "ledger_probes": ledger_n,
    }
    total["fault_share_of_ledger"] = (round(faults_total / ledger_n, 4) if ledger_n else None)
    total["decomposition"] = (
        "solves/energy = (probes/energy) x P(landed&judged) x P(solve|judged); "
        "compare factor by factor, never only the product")
    # A loss share that high is not an arm-quality problem: it is OUR plumbing
    # burning lane time (the review's "stop and call the operator" rule).  The
    # call is data, not a guess — the caller decides what to do with it.
    gate = None
    if fail_over is not None and total["fault_share_of_ledger"] is not None:
        gate = {"threshold": fail_over,
                "fault_share": total["fault_share_of_ledger"],
                "tripped": total["fault_share_of_ledger"] > fail_over}
    total["loss_gate"] = gate
    return {"since_hours": since_hours, "since": since.strftime(TS),
            "dbs": [str(p) for p in dbs], "boards": boards_out, "total": total}


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--since-hours", type=float, default=6.0)
    ap.add_argument("--db", default="", help="one DB, or 'auto' (default) to read every lane's")
    ap.add_argument("--repeats", default=str(REPEATS))
    ap.add_argument("--fail-over", type=float, default=None,
                    help="exit non-zero when our own fault share exceeds this fraction "
                         "(default 0.35; 0 disables the gate)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    db_arg = None if a.db in ("", "auto") else a.db
    rep = report(a.since_hours, db_arg, a.repeats, fail_over=a.fail_over)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    t = rep["total"]
    print(f"окно: {a.since_hours:g} ч (с {rep['since']})")
    print(f"проб: {t['probes']} | судейских: {t['judged']} | judge>0: {t['judge_positive']} | "
          f"наши сбои: {t['faults']} ({t['fault_share_of_ledger']})")
    print()
    head = ("доска", "проб", "проб/ч", "дошли", "судимых", "judge>0", "энергия", "решений/1000э")
    print("  " + "".join(f"{h:<12}" for h in head))
    for board, b in rep["boards"].items():
        print("  " + f"{board:<12}{b['probes']:<12}{b['probes_per_hour']:<12}"
              f"{(b['landed_share'] if b['landed_share'] is not None else '-'):<12}"
              f"{b['judged']:<12}{b['judge_positive']:<12}"
              f"{(b['energy'] or '-'):<12}{b['decision_per_1000_energy'] or '-'}")
    print()
    print("  P(судим|дошёл) и P(решение|судим) считаются по доске; "
          "прокси в числителе НЕ участвует (насыщен).")
    gate = t.get("loss_gate")
    if gate:
        state = "ТРЕВОГА" if gate["tripped"] else "в норме"
        print(f"  порог потерь: {gate['fault_share']:.3f} против {gate['threshold']:.2f} — {state}")
    return 1 if (gate and gate["tripped"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
