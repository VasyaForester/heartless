#!/usr/bin/env python3
"""С 22:00: сколько попыток дали реальный вызов инструмента (есть judge_raw)."""
import json
import pathlib
import time

W = pathlib.Path(__file__).resolve().parent.parent
cut = time.mktime(time.strptime("2026-11-13 22:00", "%Y-%m-%d %H:%M"))
stats = {}
for d in (W / "artifacts" / "attempts").iterdir():
    if not d.is_dir():
        continue
    man = d / "manifest.json"
    if not man.is_file():
        continue
    try:
        m = json.loads(man.read_text(encoding="utf-8"))
    except Exception:
        continue
    ts = m.get("captured_at") or m.get("started_at") or ""
    try:
        t = time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        continue
    if t < cut:
        continue
    key = f"{m.get('scenario')}|{m.get('model')}"
    s = stats.setdefault(key, {"n": 0, "render": 0})
    s["n"] += 1
    if (d / "judge_raw.json").is_file():
        s["render"] += 1

print("since 22:00:")
for k, s in sorted(stats.items()):
    print(f"  {k:52s} probes={s['n']:3d} renders={s['render']:3d}")