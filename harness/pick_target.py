#!/usr/bin/env python3
"""pick_target.py — печатает tabId grayswan-вкладки активной доски (профиль boards.py; --pg = Proving Ground)."""
import json, os, sys, urllib.request
from urllib.parse import urlsplit

# Порт CDP берём из HACKATHON_CDP_URL (лейны: main=9223, auto=9224), по умолчанию 9223.
PORT = 9223
try:
    _u = urlsplit(os.environ.get("HACKATHON_CDP_URL", ""))
    if _u.port:
        PORT = _u.port
except Exception:
    pass
needle = None
if "--pg" in sys.argv:
    needle = "proving-ground"
else:
    # board profile is the single source of the tab match ($HERMES_BOARD; default payday)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from boards import load_board  # noqa: E402
        needle = str(load_board().get("match") or "lucky-break-payday")
    except Exception:
        needle = "lucky-break-payday"
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
