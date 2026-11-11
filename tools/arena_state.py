#!/usr/bin/env python3
"""Print scenario/model/criteria from an arena inspect/show-criteria JSON."""
import json, sys

path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
r = d.get("result", d)
snap = r.get("snapshot", r)
print("URL:", snap.get("url"))
print("SCENARIO:", (snap.get("scenario") or {}).get("id"), "|", ((snap.get("scenario") or {}).get("text") or "").split("\n")[0])
print("MODEL:", (snap.get("model") or {}).get("value"), "|", (snap.get("model") or {}).get("status"))
for c in snap.get("criteria", []) or []:
    print("---CRITERIA---")
    print(c.get("text"))
