#!/usr/bin/env python3
"""Что рендерило в bank|SA после 22:00: дельта, вердикт, текст ответа."""
import json
import pathlib
import time

W = pathlib.Path(__file__).resolve().parent.parent
cut = time.mktime(time.strptime("2026-11-13 22:00", "%Y-%m-%d %H:%M"))
rows = []
for d in (W / "artifacts" / "attempts").iterdir():
    if not d.is_dir() or "banking-idor-exploit_Sand" not in d.name:
        continue
    man, jr = d / "manifest.json", d / "judge_raw.json"
    if not man.is_file() or not jr.is_file():
        continue
    try:
        m = json.loads(man.read_text(encoding="utf-8"))
        ts = m.get("captured_at") or ""
        t = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        continue
    if t < cut:
        continue
    txt = ""
    tp = d / "transcript.json"
    if tp.is_file():
        try:
            tr = json.loads(tp.read_text(encoding="utf-8", errors="replace"))
            txt = " ".join(m2.get("text") or "" for m2 in tr.get("messages", [])
                           if m2.get("role") == "assistant")[:400]
        except Exception:
            pass
    rows.append({"dir": d.name, "delta": m.get("delta"), "ts": ts[11:19], "txt": txt})

print(f"bank|SA renders since 22:00: {len(rows)}")
for r in rows:
    print(f"\n  {r['ts']} delta={r['delta']}  {r['dir']}")
    print("   ", r["txt"][:260].replace("\n", " | "))