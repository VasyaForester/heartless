#!/usr/bin/env python3
"""Extract criteria-ish text from arena show-criteria JSON."""
import json, sys

path = sys.argv[1] if len(sys.argv) > 1 else "artifacts/criteria-wb3s1.json"
d = json.load(open(path, encoding="utf-8"))
r = d.get("result", d)


def walk(obj, depth=0):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and any(w in k.lower() for w in ("crit", "goal", "criter")):
                print(f"{k}: {v}")
            walk(v, depth + 1)
    elif isinstance(obj, list):
        for it in obj:
            walk(it, depth + 1)


walk(r)
print("---TOP---")
print(json.dumps(r, ensure_ascii=False)[:3000])
