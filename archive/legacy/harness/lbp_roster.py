#!/usr/bin/env python3
"""Snapshot current LBP rosters (scenario -> models + broken flags) for rotation watch.

Run: python3 harness/lbp_roster.py [TARGET_ID]
Writes datasets/lbp/roster_snapshot.json; on re-run prints added/removed models per scenario
(a roster rotation = fresh attackable pairs).
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

raw_target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CHAT_TARGET", "")
if not re.fullmatch(r"[0-9A-Fa-f]{32}", raw_target or ""):
    print(f"ERROR: invalid/missing TARGET id {raw_target!r}; pass [TARGET_ID] or set CHAT_TARGET",
          file=sys.stderr)
    sys.exit(2)
TARGET = raw_target
SCEN = ["scam-retail", "double-refund", "christmas-giftcard-scam",
        "negative-quantity-exploit", "banking-idor-exploit"]
HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent


def run(cmd):
    return subprocess.run(cmd, cwd=WORK, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


out = {}
for sid in SCEN:
    run(["python3", "harness/lbp.py", "switch", "--scenario", sid])
    time.sleep(1.5)
    r = run(["python3", "harness/hackathon.py", "arena", "models", "--target", TARGET])
    try:
        d = json.loads(r.stdout)
        snap = d["result"]["snapshot"]
        out[sid] = [{"name": m["name"], "broken": m.get("broken"), "disabled": m.get("disabled")}
                    for m in (snap.get("availableModels") or [])]
    except Exception as e:  # noqa: BLE001 - report and continue with other scenarios
        out[sid] = {"error": str(e), "raw_head": ((r.stdout or "") + (r.stderr or ""))[:200]}

for sid, models in out.items():
    if isinstance(models, list):
        print(sid, "->", ", ".join(f"{m['name']}{'(BROKEN)' if m['broken'] else ''}" for m in models))
    else:
        print(sid, "-> ERROR:", models.get("raw_head", models.get("error", "?")))

errors = [sid for sid, v in out.items() if not isinstance(v, list)]
if errors:
    dst_err = WORK / "datasets/lbp/roster_snapshot.error.json"
    dst_err.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"FAIL: {len(errors)}/{len(SCEN)} scenarios unreadable ({', '.join(errors)}); "
          f"snapshot NOT updated (failed run saved to {dst_err.name})")
    sys.exit(1)

dst = WORK / "datasets/lbp/roster_snapshot.json"
prev = json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else None
dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("snapshot written:", dst)
if prev and all(isinstance(prev.get(sid), list) for sid in out):
    rotations = 0
    for sid in out:
        old = {m["name"] for m in prev[sid]}
        new = {m["name"] for m in out[sid]}
        if old != new:
            rotations += 1
            print("ROTATION:", sid, "| added:", new - old, "| removed:", old - new)
    print(f"rotation check done ({rotations} changed)")
else:
    print("rotation check skipped: no valid previous snapshot to diff (baseline updated)")
