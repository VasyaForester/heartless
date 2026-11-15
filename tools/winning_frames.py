#!/usr/bin/env python3
"""Победные user-кадры: scam-retail, negq CT, giftcard CT."""
import json
import pathlib

W = pathlib.Path(__file__).resolve().parent.parent
for pat in ("lbp-scam-retail-*-submit-transcript.json",
            "lbp-negative-quantity-exploit-copper-turtle-brave-submit-transcript.json",
            "lbp-christmas-giftcard-scam-copper-turtle-brave-submit-transcript.json"):
    files = sorted((W / "artifacts").glob(pat))
    print(f"\n===== {pat} ({len(files)}) =====")
    for p in files[:2]:
        try:
            tr = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        msgs = tr.get("messages", [])
        print(f"-- {p.name}")
        if msgs:
            print("[user]", (msgs[0].get("text") or "")[:900].replace("\n", " | "))
        if len(msgs) > 1:
            print("[assistant]", (msgs[1].get("text") or "")[:300].replace("\n", " | "))