#!/usr/bin/env python3
"""Read-only reconciliation between the four state owners.

Ownership policy:
  * datasets/lbp/pairs.jsonl   — v1 live lane journal (authoritative for v1)
  * artifacts/harness.db       — v2 SQLite (authoritative for v2)
  * datasets/lbp/pairs-v2.jsonl — derived export, never authoritative
  * artifacts/lbp-board.json   — v1 board snapshot, never authoritative for v2

This command reports discrepancies; it never writes to any store.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def _rows(path):
    out = []
    p = pathlib.Path(path)
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def v1_pairs(path):
    """Latest row per scenario|model from the v1 journal."""
    latest = {}
    for row in _rows(path):
        key = f"{row.get('scenario_id')}|{row.get('model_id')}"
        latest[key] = row
    return latest


def v2_db_pairs(db_path):
    if not pathlib.Path(db_path).is_file():
        return {}
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    out = {}
    try:
        for row in conn.execute("SELECT * FROM pairs"):
            out[row["id"]] = dict(row)
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def v2_export_pairs(path):
    return {row.get("pair_id"): row for row in _rows(path) if row.get("pair_id")}


def board_pairs(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return data.get("pairs") or {}


def _solved_v1(row):
    return str(row.get("outcome") or "").upper() == "SUCCESS" or row.get("judge") == "accepted"


def reconcile(db_path, pairs_path, export_path, board_path) -> dict:
    v1 = v1_pairs(pairs_path)
    db = v2_db_pairs(db_path)
    exp = v2_export_pairs(export_path)
    board = board_pairs(board_path)
    keys = sorted(set(v1) | set(db) | set(exp) | set(board))
    report = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "counts": {"v1_pairs": len(v1), "db_pairs": len(db),
                   "export_pairs": len(exp), "board_pairs": len(board)},
        "missing_in_db": [], "missing_in_v1": [],
        "missing_in_export": [], "missing_in_board": [],
        "status_conflicts": [], "newer_records": [],
        "attempts_absent": [], "inconsistent_judge_refs": [],
        "board_identity_mismatches": [],
    }
    for key in keys:
        a, b, c, d = v1.get(key), db.get(key), exp.get(key), board.get(key)
        if a and not b:
            report["missing_in_db"].append(key)
        if b and not a:
            report["missing_in_v1"].append(key)
        if b and not c:
            report["missing_in_export"].append(key)
        if b and not d:
            report["missing_in_board"].append(key)
        states = {}
        if a:
            states["v1"] = _solved_v1(a)
        if b:
            states["db"] = bool(b.get("solved"))
        if c:
            states["export"] = bool(c.get("solved"))
        if d:
            states["board"] = bool(d.get("solved"))
        if len(set(states.values())) > 1:
            report["status_conflicts"].append({"pair": key, "states": states})
        if b and a and int(b.get("attempts") or 0) < int(a.get("attempts") or 0):
            report["attempts_absent"].append(
                {"pair": key, "db_attempts": int(b.get("attempts") or 0),
                 "v1_attempts": int(a.get("attempts") or 0)})
        if b and b.get("judge_ref"):
            jr = pathlib.Path(b["judge_ref"])
            if not jr.is_absolute():
                jr = WORK / jr
            if not jr.is_file():
                report["inconsistent_judge_refs"].append(
                    {"pair": key, "judge_ref": b["judge_ref"]})
        if b and d:
            if str(b.get("board_profile") or "lucky-break-payday") != "lucky-break-payday" \
                    and "lucky-break-payday" in key:
                report["board_identity_mismatches"].append(
                    {"pair": key, "board_profile": b.get("board_profile")})
    # The v2 DB version is a monotonic per-pair counter; a derived export that
    # predates it is stale.  We report, never overwrite.
    for key, b in db.items():
        if int(b.get("version") or 0) > 0 and key not in exp:
            report["newer_records"].append({"pair": key, "db_version": b.get("version")})
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--pairs", default=str(WORK / "datasets" / "lbp" / "pairs.jsonl"))
    ap.add_argument("--v2", default=str(WORK / "datasets" / "lbp" / "pairs-v2.jsonl"))
    ap.add_argument("--board", default=str(WORK / "artifacts" / "lbp-board.json"))
    a = ap.parse_args()
    print(json.dumps(reconcile(a.db, a.pairs, a.v2, a.board), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())