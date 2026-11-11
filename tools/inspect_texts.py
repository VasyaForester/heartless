#!/usr/bin/env python3
"""Extract readable text regions from a GS inspect dump.

Usage:
  python3 tools/inspect_texts.py artifacts/inspect-scenario2.json [--filter criteria,chat,log] [--max 800]

Prints distinct text blocks with their selectors; useful for recon of scenario pages
(criteria panels, chat message area, tool panels, persona text).
"""
from __future__ import annotations
import json
import pathlib
import sys


def walk(o, out):
    if isinstance(o, dict):
        t = o.get("text")
        if isinstance(t, str) and len(t.strip()) > 25:
            out.append((o.get("selector") or o.get("tag") or "", t.strip()))
        for v in o.values():
            walk(v, out)
    elif isinstance(o, list):
        for v in o:
            walk(v, out)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    fp = args[0]
    filt = None
    maxlen = 800
    if "--filter" in args:
        filt = [w.strip().lower() for w in args[args.index("--filter") + 1].split(",")]
    if "--max" in args:
        maxlen = int(args[args.index("--max") + 1])
    d = json.loads(pathlib.Path(fp).read_text(encoding="utf-8"))
    out = []
    walk(d, out)
    seen = set()
    n = 0
    for sel, t in out:
        key = t[:60]
        if key in seen:
            continue
        seen.add(key)
        if filt and not any(f in (sel + " " + t).lower() for f in filt):
            continue
        n += 1
        print(f"--- [{sel[:50]}]")
        print(t[:maxlen].replace("\n", " | "))
        print()
    print(f"# blocks: {n} (distinct, filter={filt})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
