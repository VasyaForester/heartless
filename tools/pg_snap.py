#!/usr/bin/env python3
"""Bounded reader for Proving Ground adapter snapshots (models / inspect / context).

Usage: python3 tools/pg_snap.py FILE mode   (mode: models|inspect|context)
Prints compact essentials only; never rewrites inputs.
"""
import json
import sys


def _get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def main(path, mode):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    result = data.get("result", data)
    snap = result.get("snapshot", result)

    scenario = snap.get("scenario") or {}
    model = snap.get("model") or {}
    print(f"scenario: {scenario.get('id')} | model: {model.get('value')} ({model.get('status')})")

    if mode == "models":
        models = result.get("availableModels") or snap.get("availableModels") or []
        if not models:
            print("availableModels: EMPTY — raw keys:", list(snap.keys())[:30])
        for m in models:
            if isinstance(m, dict):
                name = m.get("name") or m.get("value") or m.get("label")
                flags = []
                for k in ("selected", "disabled", "broken", "isSelected", "isDisabled"):
                    if m.get(k):
                        flags.append(k)
                print(f"  - {name} [{','.join(flags) or 'ok'}]")
            else:
                print(f"  - {m}")
    elif mode in ("inspect", "context"):
        msgs = snap.get("messages") or []
        print(f"messages: {len(msgs)}")
        for m in msgs:
            if isinstance(m, dict):
                text = (m.get("text") or "").replace("\n", "\\n")
                print(f"--- {m.get('role')}: {text[:4000]}")
        bt = snap.get("bodyText") or ""
        idx = bt.find("Scenario criteria")
        if idx >= 0:
            seg = bt[idx:idx + 4000].replace("\n", " | ")
            print("CRITERIA-PANEL:", seg)
        else:
            print("bodyText head:", bt[:1200].replace("\n", " | "))

    crit = snap.get("criteria")
    if crit:
        print("criteria field:", str(crit)[:1000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
