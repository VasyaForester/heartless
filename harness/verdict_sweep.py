#!/usr/bin/env python3
"""Reconcile farm checkpoints with the SUBMITTED list in the chats modal.

Usage (from workspace dir):
  python3 harness/verdict_sweep.py --target TID --scope inputs/scope-<scenario>.json \
      [--ckpt artifacts/farm-<scenario>.json] [--out artifacts/sweep-<name>.json]

Reads the modal via arena_chats.py, matches entries to checkpoint models whose judge
is pending/unknown/not-judged, updates the checkpoint (judge: passed/failed + verdictTime),
and prints the full entry table. Facts only — no guessing: unmatched stays untouched.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
from scenario_filters import filter_for  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--scope", required=True, help="scope used for the chats-tab click")
    ap.add_argument("--ckpt")
    ap.add_argument("--out")
    ap.add_argument("--tab", default="auto", choices=["chats", "submitted", "auto"])
    ap.add_argument("--scenario-id", help="checkpoint scenario id (resolved to a scenario filter)")
    ap.add_argument("--scenario-filter", help="substring that must appear in the entry's scenario")
    a = ap.parse_args()

    # scenario filters prevent cross-scenario false positives (a model accepted elsewhere).
    # The map lives in scenario_filters.py (shared with verdict_verify.py / pending.py).
    filt = a.scenario_filter
    if not filt and a.scenario_id:
        filt = filter_for(a.scenario_id)
        if not filt:
            print(f"WARN: no scenario filter for {a.scenario_id}; matching ALL entries (risk of "
                  "cross-scenario false positives)")
    if filt:
        print("scenario filter:", filt)

    tmp = f"artifacts/_sweep_chats_{int(time.time())}.json"
    rc = subprocess.run([sys.executable, str(HERE / "arena_chats.py"), "--target", a.target,
                         "--scope", a.scope, "--tab", a.tab, "--out", tmp],
                        capture_output=True, text=True)
    if rc.returncode != 0:
        print("arena_chats failed:", (rc.stdout + rc.stderr)[:400])
        return 1
    d = json.loads(pathlib.Path(tmp).read_text(encoding="utf-8"))
    entries = d.get("entries", [])
    counters = d.get("counters", {})

    print("counters:", counters)
    for e in entries:
        print(f"  {e['status']:<13} {e['time']:<14} {e['model']:<28} {e.get('scenario', '')[:40]}")

    updates = []
    if a.ckpt:
        ck = json.loads(pathlib.Path(a.ckpt).read_text(encoding="utf-8"))
        models = ck.get("models", {})
        for name, m in models.items():
            if m.get("judge") not in ("pending", "unknown", None) and m.get("stage") != "sent":
                pass  # only targeted states below
            if m.get("judge") in ("pending", "unknown") or (
                    m.get("stage") in ("sent",) and m.get("judge") in (None, "not-judged")):
                match = next((e for e in entries if e["model"] == name
                              and e["status"] in ("ACCEPTED", "REJECTED")
                              and (not filt or filt.lower() in (e.get("scenario") or "").lower())),
                             None)
                if match:
                    m["judge"] = "passed" if match["status"] == "ACCEPTED" else "failed"
                    m["verdictTime"] = match["time"]
                    m["stage"] = "judged"
                    updates.append((name, match["status"], match["time"]))
        if updates:
            pathlib.Path(a.ckpt).write_text(json.dumps(ck, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
            print(f"\nupdated checkpoint {a.ckpt}:")
            for name, st, t in updates:
                print(f"  {name}: {st} ({t})")
        else:
            print("\nno checkpoint updates (no new verdicts matched)")

    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(
            {"counters": counters, "entries": entries, "updates": updates},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print("saved:", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
