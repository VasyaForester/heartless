#!/usr/bin/env python3
"""Print message texts from adapter send/context result files (bounded).

Usage: python3 tools/show_msgs.py FILE [max_chars_per_msg]
"""
import json
import sys


def main():
    path = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    r = data.get("result", data)
    snap = r.get("snapshot", r)
    msgs = r.get("messages") or snap.get("messages") or []
    if not msgs:
        print("no messages; keys:", list(snap.keys())[:25])
        bt = snap.get("bodyText") or ""
        if bt:
            print("bodyText:", bt[:cap].replace("\n", " | "))
        return
    print(f"== {path} | messages: {len(msgs)}")
    for m in msgs:
        if isinstance(m, dict):
            text = (m.get("text") or "")[:cap]
            print(f"--- [{m.get('role')}]")
            print(text)
            print()


if __name__ == "__main__":
    main()
