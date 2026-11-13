#!/usr/bin/env python3
"""Judge Calibration Lab v3 (Phase 7, offline).

Audits the trustworthiness of judge artifacts using only stored files:

  * duplicate operation ids across attempts (a judge reused for two attempts)
  * judge artifacts without an operation id (cannot be correlated)
  * solved/verdict claims not backed by an accepted judge artifact
  * status distribution of all judge snapshots (evidence store + legacy files)

Writes artifacts/judge-calib.json and prints a compact report.
Usage: python3 harness/judge_calib.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def load_judge(p: pathlib.Path):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    return {
        "path": str(p.relative_to(WORK)),
        "operationId": d.get("operationId") or d.get("operation_id") or d.get("opid"),
        "status": d.get("status"),
        "verdict": (d.get("verdict") or "").lower() or None,
        "pcts": d.get("pcts") or d.get("criterionPercentages"),
        "chatId": d.get("chatId") or d.get("chat_id"),
        "score": d.get("score"),
    }


def main() -> int:
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": 0,
           "status_hist": {}, "duplicate_operations": [], "missing_operation": [],
           "accepted_without_judge": []}
    recs = []
    for base in ("artifacts", "artifacts/attempts"):
        for p in sorted((WORK / base).glob("**/*judge*.json")):
            if p.name == "judge_result.json":  # correlation record, not raw judge
                continue
            if not (p.name == "judge_raw.json" or p.name.startswith("lbp-")):
                continue  # diagnostic context-*.json files are not judges
            rec = load_judge(p)
            if rec is None:
                continue
            rec["dir"] = str(p.parent.relative_to(WORK))
            recs.append(rec)
    out["files"] = len(recs)
    hist = collections.Counter(str(r["status"] or "unknown") for r in recs)
    out["status_hist"] = dict(hist)

    by_op = collections.defaultdict(set)
    for r in recs:
        if r["operationId"]:
            by_op[r["operationId"]].add(r["dir"])
    out["duplicate_operations"] = [
        {"operationId": op, "dirs": sorted(dirs)} for op, dirs in by_op.items() if len(dirs) > 1]
    out["missing_operation"] = [r["path"] for r in recs if not r["operationId"]]

    # solved claims vs accepted judge artifacts
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{WORK / 'artifacts' / 'harness.db'}?mode=ro", uri=True)
        solved = [r[0] for r in conn.execute("SELECT id FROM pairs WHERE solved=1")]
        accepted = {r["operationId"] for r in recs if (r["verdict"] or "") in ("accepted", "solved")}
        out["solved_pairs"] = len(solved)
        out["accepted_judges"] = len(accepted)
        if solved and not accepted:
            out["accepted_without_judge"] = sorted(solved)[:20]
    except Exception as exc:  # noqa: BLE001
        out["db_error"] = str(exc)

    (WORK / "artifacts" / "judge-calib.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"judge files: {out['files']}  statuses: {out['status_hist']}")
    print(f"duplicate operations: {len(out['duplicate_operations'])}")
    for d in out["duplicate_operations"][:5]:
        print(f"  op {d['operationId']} -> {d['dirs']}")
    print(f"missing operationId: {len(out['missing_operation'])}")
    for m in out["missing_operation"][:5]:
        print(f"  {m}")
    print(f"solved pairs (db): {out.get('solved_pairs')}  accepted judge ops: {out.get('accepted_judges')}")
    if out["accepted_without_judge"]:
        print(f"  ⚠ solved pairs without an accepted judge artifact: {out['accepted_without_judge'][:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())