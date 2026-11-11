#!/usr/bin/env python3
"""Build the typed event corpus (schema v1) from submit snapshots + judge receipts.

Usage:
  python3 harness/lbp_events.py --transcript FILE [--judge FILE] \
      --attempt-id ID --pair-id "scenario/model" --scenario SID [--force]

Appends typed rows to datasets/lbp/events/attempts.jsonl (append-only; a rerun skips an
attempt_id already present unless --force). Row types: user_msg, assistant_msg, tool_call,
validator_result, judge_verdict, system_event. Raw rows are never edited; derived metrics
are recomputed from this file.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))
import lbp_checks  # noqa: E402

OUT = WORK / "datasets/lbp/events/attempts.jsonl"
SCHEMA = 1

TOOL_CALL_PATTERNS = [
    ("offer_transaction", re.compile(r"Offering transaction\s*\(([^)]*)\)")),
    ("create_listing", re.compile(r"Creating marketplace listing\s*\(([^)]*)\)")),
    ("give_refund", re.compile(r"Issuing refund\s*\(([^)]*)\)")),
    ("purchase", re.compile(r"purchase\s*\(([^)]*)\)")),
    ("get_user_info", re.compile(r"get_user_info\s*\(([^)]*)\)")),
]


def parse_args_block(b):
    d = {}
    for m in re.finditer(r"(\w+):\s*(\"[^\"]*\"|[\d\.\-]+)", b):
        k, v = m.group(1), m.group(2)
        if v.startswith('"'):
            v = v[1:-1]
        else:
            try:
                v = float(v) if "." in v else int(v)
            except ValueError:
                pass
        d[k] = v
    return d


def rows_for_transcript(tj, attempt_id, pair_id, scenario):
    sha = hashlib.sha256(
        json.dumps(tj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    rows = []
    seq = 0
    msgs = tj.get("messages", [])
    for m in msgs:
        seq += 1
        role = "user" if m.get("role") == "user" else "agent"
        rows.append({"schema": SCHEMA, "attempt_id": attempt_id, "pair_id": pair_id,
                     "seq": seq, "type": "user_msg" if role == "user" else "assistant_msg",
                     "actor": role, "text": m.get("text", ""), "transcript_sha256": sha})
        if m.get("role") == "assistant":
            for name, pat in TOOL_CALL_PATTERNS:
                for mt in pat.finditer(m.get("text", "")):
                    seq += 1
                    rows.append({"schema": SCHEMA, "attempt_id": attempt_id, "pair_id": pair_id,
                                 "seq": seq, "type": "tool_call", "actor": "agent",
                                 "name": name, "args": parse_args_block(mt.group(1)),
                                 "transcript_sha256": sha})
    a_text = "\n".join(m.get("text", "") for m in msgs if m.get("role") == "assistant")
    last = next((m.get("text", "") for m in reversed(msgs) if m.get("role") == "assistant"), "")
    rel = lbp_checks.run_checks(scenario, a_text, last)
    for v in rel["validators"]:
        seq += 1
        rows.append({"schema": SCHEMA, "attempt_id": attempt_id, "pair_id": pair_id, "seq": seq,
                     "type": "validator_result", "name": v["id"], "status": v["status"],
                     "detail": v["detail"], "transcript_sha256": sha})
    seq += 1
    rows.append({"schema": SCHEMA, "attempt_id": attempt_id, "pair_id": pair_id, "seq": seq,
                 "type": "system_event", "name": "local_check", "ready": rel["ready"],
                 "problems": rel["problems"], "transcript_sha256": sha})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--judge")
    ap.add_argument("--attempt-id", required=True)
    ap.add_argument("--pair-id", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if OUT.exists() and not a.force:
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("attempt_id") == a.attempt_id:
                print(f"skip: attempt_id {a.attempt_id} already present in {OUT}")
                return 0

    tj = json.loads(pathlib.Path(a.transcript).read_text(encoding="utf-8"))
    rows = rows_for_transcript(tj, a.attempt_id, a.pair_id, a.scenario)
    if a.judge:
        jj = json.loads(pathlib.Path(a.judge).read_text(encoding="utf-8"))
        rows.append({"schema": SCHEMA, "attempt_id": a.attempt_id, "pair_id": a.pair_id,
                     "seq": rows[-1]["seq"] + 1, "type": "judge_verdict",
                     "status": jj.get("status"), "submittedAt": jj.get("submittedAt"),
                     "url": jj.get("url"),
                     "evidence": [e.get("text", "")[:300] for e in (jj.get("evidence") or [])]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    types = {}
    for r in rows:
        types[r["type"]] = types.get(r["type"], 0) + 1
    print(f"appended {len(rows)} rows for {a.attempt_id}: {types}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
