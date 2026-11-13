#!/usr/bin/env python3
"""Read the Chats/Submissions modal of a Gray Swan scenario into JSON.

Usage (from workspace dir):
  python3 harness/arena_chats.py --target TID [--tab chats|submitted|auto] [--scope inputs/scope-x.json] [--out artifacts/chats.json]

- Uses the lane board tab URL (must contain chatId=...). If the current tab has no chatId,
  open a chat first and rerun.
- tab=submitted parses the default SUBMITTED list (no click needed).
- tab=chats clicks the CHATS tab first (requires --scope for the click).
Output: counters + parsed entries (status/time/model/messages best-effort) + raw snippets.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
HACK = HERE / "hackathon.py"


def sh(cmd, timeout=240):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def arena(*args, timeout=240):
    return sh([sys.executable, str(HACK), "arena", *args], timeout=timeout)


def _board_match():
    """URL substring of the board tab, from the boards.py profile (Payday default)."""
    try:
        from boards import load_board as _lb
        return str(_lb().get("match") or "lucky-break-payday")
    except Exception:
        return "lucky-break-payday"


def current_pg_url(target, board_substr=None):
    board_substr = board_substr or _board_match()
    rc, out, err = arena("tabs", timeout=120)
    try:
        d = json.loads(out)
        for t in d.get("result", []):
            url = t.get("url", "")
            if board_substr in url:
                return t.get("id"), url
    except Exception:
        pass
    return None, None


def modal_url(url, tab="chats"):
    # Canonicalize: rebuild from the bare challenge URL + chatId, then add modal params.
    # Never string-strip/re-append raw URLs — that left dangling '&chatId=...' and caused 404s.
    m = re.match(r"(https?://[^/]+/arena/challenge/[a-z0-9-]+)", url or "")
    c = re.search(r"[?&]chatId=([0-9a-fA-F]+)", url or "")
    if not m or not c:
        return None
    theme = "submitted" if tab == "submitted" else "chats"
    return f"{m.group(1)}?chatId={c.group(1)}&modal=chats&chatsTab={theme}"


def find_tab_selector(inspect_path, prefix):
    try:
        d = json.loads(pathlib.Path(inspect_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    found = []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("text")
            if isinstance(t, str) and t.startswith(prefix) and len(t) < 40 and o.get("selector"):
                found.append(o["selector"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return found[0] if found else None


# Verified live formats:
#   2026-11-06: REJECTED\nTODAY 2:37PM\n<preview>\n3. (Hard) <title>\n·\n<Model>
#   2026-11-07: ACCEPTED\nTODAY 6:29PM\n<preview>\n(Easy) <title>\n·\n<Model>
#   2026-11-10 (post-restart UI): parenthetical difficulty dropped:
#     ACCEPTED\nTODAY 5:41PM\n<preview>\n<title>\n·\n<Model>
# (leading "N." and the "(...)" label are both optional now — accept both)
ENTRY_RE = re.compile(
    r"(SUBMITTED|NOT SUBMITTED|ACCEPTED|REJECTED)\n"
    r"([^\n]*\d{1,2}:\d{2}\s?[AP]M)\n"
    r"(.*?)\n"
    r"((?:\d+\.\s*)?(?:\([^)]+\)\s*)?[^\n]+)\n·\n"
    r"([^\n]+)",
    re.S)


def parse_entries(body_text):
    entries = []
    for m in ENTRY_RE.finditer(body_text):
        status, tstamp, preview, scenario, model = m.groups()
        entries.append({
            "status": status,
            "time": tstamp.strip(),
            "model": model.strip(),
            "scenario": scenario.strip(),
            "snippet": preview.strip()[:160].replace("\n", " "),
        })
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--tab", choices=["chats", "submitted", "auto"], default="auto")
    ap.add_argument("--scope")
    ap.add_argument("--out", default="artifacts/chats-modal.json")
    ap.add_argument("--board-substr", default=_board_match(),
                    help="URL substring identifying the board tab (default: from the boards.py profile)")
    a = ap.parse_args()

    tid, url = current_pg_url(a.target, a.board_substr)
    if not url or "chatId=" not in url:
        print(json.dumps({"error": f"current {a.board_substr} tab has no chatId; open a chat first", "url": url}))
        return 1
    murl = modal_url(url, a.tab)
    if not murl:
        print(json.dumps({"error": "malformed tab URL; refusing to navigate", "url": url}))
        return 1
    rc, out, err = arena("open", "--target", a.target, "--url", murl)
    time.sleep(2.5)
    tmp = "artifacts/_chats-modal-inspect.json"
    arena("inspect", "--target", a.target, "--out", tmp)

    if a.tab in ("chats", "auto"):
        sel = find_tab_selector(tmp, "CHATS\n(")
        if sel and a.scope:
            rc, out, err = arena("click", "--scope", a.scope, "--selector", sel,
                                 "--operation-id", f"chats-tab-{int(time.time())}")
            time.sleep(2)
            arena("inspect", "--target", a.target, "--out", tmp)

    try:
        d = json.loads(pathlib.Path(tmp).read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"error": f"inspect parse failed: {e}"}))
        return 1
    bt = (d.get("bodyText") or "").replace("\r", "")

    counters = {}
    m = re.search(r"SUBMISSIONS\s*\n\s*(\d+)", bt)
    if m:
        counters["submissions"] = int(m.group(1))
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*MODELS BROKEN", bt)
    if m:
        counters["models_broken"] = f"{m.group(1)}/{m.group(2)}"
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*BREAKS", bt)
    if m:
        counters["breaks_total"] = f"{m.group(1)}/{m.group(2)}"

    # pick the right slice of bodyText: after the CHATS marker when chats tab active
    idx = bt.find("Most recent")
    slice_bt = bt[idx:] if idx >= 0 else bt
    entries = parse_entries(slice_bt)

    result = {"url": murl, "tab": a.tab, "counters": counters, "entries": entries}
    pathlib.Path(a.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"counters": counters, "n_entries": len(entries)}, ensure_ascii=False))
    for e in entries:
        print(f"  {e['status']:<14} {e['time'] or '':<14} {e['model'] or '?':<28} {(e.get('scenario') or '')[:40]}")
    print("saved:", a.out)


if __name__ == "__main__":
    sys.exit(main())
