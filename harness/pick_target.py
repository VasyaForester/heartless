#!/usr/bin/env python3
"""pick_target.py — печатает tabId grayswan-вкладки доски Lucky Break: Payday (или PG, если --pg)."""
import json, sys, urllib.request

PORT = 9223
needle = "--pg" if "--pg" in sys.argv else "lucky-break-payday"
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=5) as r:
        tabs = json.load(r)
except Exception as e:
    print("", end="")
    sys.exit(1)

cands = []
for t in tabs:
    if t.get("type") != "page":
        continue
    url = t.get("url") or ""
    if "grayswan.ai" in url and needle in url:
        cands.append(t)
if not cands:
    sys.exit(1)
# самая свежая вкладка с доской
print(cands[-1]["id"])
