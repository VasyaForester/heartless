#!/usr/bin/env python3
"""DW/SA bank: есть ли реальный mock-ответ на get_user_info(47539)?"""
import json
import pathlib

W = pathlib.Path(__file__).resolve().parent.parent


def check(sub):
    print(f"\n== {sub} ==")
    dirs = [d for d in (W / "artifacts" / "attempts").iterdir()
            if "banking-idor-exploit_" in d.name and sub in d.name
            and (d / "transcript.json").is_file()]
    dirs.sort(key=lambda p: (p / "transcript.json").stat().st_mtime, reverse=True)
    mock = 0
    for d in dirs[:25]:
        txt = (d / "transcript.json").read_text(encoding="utf-8", errors="replace")
        if "get_user_info_response" in txt:
            mock += 1
    print(f"  transcripts scanned: {min(len(dirs),25)}  with mock-response: {mock}")
    for d in dirs[:2]:
        try:
            tr = json.loads((d / "transcript.json").read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        a = [m.get("text") or "" for m in tr.get("messages", []) if m.get("role") == "assistant"]
        print(f"  -- {d.name[-14:]}: {(a[-1] if a else '')[:320].replace(chr(10),' | ')}")


check("Diamond Whale Bold")
check("Sand Ant Plus Ultra")