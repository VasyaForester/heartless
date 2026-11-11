#!/usr/bin/env python3
"""Summarize the attempts journal: per scenarioId -> solved models, counts, last events.

Read-only. Prints a compact map to pick the next unsolved PG targets.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
path = os.path.join(WS, "attempts", "attempts.jsonl")

solved = collections.defaultdict(set)
attempts = collections.defaultdict(int)
failed = collections.defaultdict(int)
pending = collections.defaultdict(int)
last = {}

with open(path, encoding="utf-8") as fh:
    for line in fh:
        try:
            d = json.loads(line)
        except Exception:
            continue
        sid = d.get("scenarioId") or "?"
        st = d.get("judgeStatus") or "?"
        m = d.get("modelId") or "?"
        attempts[sid] += 1
        last[sid] = d.get("attemptId", "")[:60]
        if st == "passed":
            solved[sid].add(m)
        elif st == "failed":
            failed[sid] += 1
        elif st in ("pending", "unknown"):
            pending[sid] += 1

rows = sorted(attempts.items(), key=lambda kv: -len(solved.get(kv[0], ())))
for sid, n in rows:
    s = solved.get(sid, set())
    print(f"{sid:48s} attempts={n:3d} solved={len(s):2d} failed={failed.get(sid,0):2d} pending/unk={pending.get(sid,0):2d}")
    if s:
        print("    solved models:", sorted(s)[:12])
