#!/usr/bin/env python3
"""Collect success criteria for every IPI Black scenario into artifacts/ipi-criteria.json."""
import json
import os
import subprocess
import sys

TARGET = "7C5A17D417AFD9BF5039984145782470"
WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS = [
    "wb3s1-retry-budget-merge-request",
    "wb3s2-premature-access-approval",
    "wb3s3-delete-production-data",
    "wb3s4-browser-walkthrough-hijack",
    "wb3s5-persist-downstream-config",
    "bb3-s1",
    "bb3-s2",
    "bb3-s3",
    "bb3-s4",
    "bb3-s5",
]


def run(args):
    return subprocess.run(args, cwd=WS, capture_output=True, text=True, timeout=120)


def main():
    out = {}
    for sid in SCENARIOS:
        r = run([sys.executable, "harness/hackathon.py", "arena", "select-scenario",
                 "--target", TARGET, "--value", sid])
        ok = r.returncode == 0
        r2 = run([sys.executable, "harness/hackathon.py", "arena", "show-criteria",
                  "--target", TARGET, "--out", f"artifacts/ipi-crit-{sid}.json"])
        text = ""
        try:
            d = json.load(open(os.path.join(WS, f"artifacts/ipi-crit-{sid}.json"), encoding="utf-8"))
            snap = d.get("result", d).get("snapshot", {})
            crits = snap.get("criteria", []) or []
            text = "\n".join(c.get("text", "") for c in crits)
            model = (snap.get("model") or {}).get("value")
        except Exception as e:
            model = None
            text = f"ERROR {e}"
        out[sid] = {"selected_ok": ok, "model": model, "criteria": text}
        print(sid, "| model:", model, "| len:", len(text), "| select_ok:", ok)
    json.dump(out, open(os.path.join(WS, "artifacts/ipi-criteria.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("saved artifacts/ipi-criteria.json")


if __name__ == "__main__":
    main()
