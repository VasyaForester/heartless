#!/usr/bin/env python3
"""Inventory the Proving Ground wave boards into one JSON (scenarios + slots text).

Usage (from workspace, no farm running — this drives the same tab):
  python3 harness/wave_scan.py --waves 2-26 --out artifacts/waves-scan.json

Each step runs switch-wave.mjs (opens the wave selector, clicks the requested
wave card) and records the behavior ids + card texts visible afterwards.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def sh(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def node_exe():
    import hackathon
    node, _ = hackathon.discover_node()
    return node


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--waves", default="2-26", help="inclusive range, e.g. 2-26")
    ap.add_argument("--out", default="artifacts/waves-scan.json")
    ap.add_argument("--cdp", default="http://127.0.0.1:9223")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.waves.split("-"))
    node = node_exe()
    out = {}
    ok = 0
    for n in range(lo, hi + 1):
        rc, o, e = sh([node, str(HERE / "switch-wave.mjs"), "--wave", f"Wave {n}", "--cdp", a.cdp])
        d = None
        for line in reversed(o.strip().splitlines()):
            try:
                d = json.loads(line)
                break
            except Exception:
                continue
        if d is None:
            d = {"error": (o + e)[:220]}
        out[f"wave{n}"] = d
        # incremental save: a mid-scan timeout must not lose collected waves
        pathlib.Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        nsc = len(d.get("scenarios") or [])
        if d.get("ok"):
            ok += 1
        print(f"Wave {n}: ok={bool(d.get('ok'))} scenarios={nsc} {('ERR: ' + str(d.get('error'))[:80]) if d.get('error') else ''}")
        for s in (d.get("scenarios") or []):
            if isinstance(s, dict):
                print(f"    {s.get('id')} [{s.get('track')}] | {s.get('text')}")
    pathlib.Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved: {a.out} ({ok}/{hi - lo + 1} waves ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
