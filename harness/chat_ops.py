#!/usr/bin/env python3
"""Unified CLI for dialog operations on Gray Swan chats (one entry point).

Subcommands (stdout is machine-readable JSON):
  find    --target T [--model M] [--scenario S] [--scope S] [--bootstrap-chat-id ID] [--out F]
            Open the CHATS modal and list rows paired with their chatId links.
  open    --target T --chat-id ID            # plain navigation to the chat
  meta    --target T --chat-id ID            # open + probe (model/banner/judge state)
  read    --target T --chat-id ID [--out F]  # full text dump + message-block summary
  followup --target T --chat-id ID --scenario-id X --track TRACK --file F
            [--scope F] [--opid ID] [--board B]
            Open chat -> probe its model -> bind scope to THAT model -> send follow-up.
  judge   --target T --chat-id ID --scenario-id X --track TRACK
            [--scope F] [--opid ID] [--timeout-ms N] [--board B]
            Open chat -> bind scope to its model -> arena_heal judge.

Only `followup` and `judge` produce external sends; the rest are read-only.
Never run while repo-wide external actions are paused (except read-only use).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
HACK = HERE / "hackathon.py"
HEAL = HERE / "arena_heal.py"
BASE_URL = "https://app.grayswan.ai/arena/challenge/proving-ground"

sys.path.insert(0, str(HERE))


def sh(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def arena(*args, timeout=300):
    return sh([sys.executable, str(HACK), "arena", *args], timeout=timeout)


def node_exe():
    import hackathon
    node, _ = hackathon.discover_node()
    return node


def evaljs(jsfile, timeout=120, match=None, target=None):
    cmd = [node_exe(), str(HERE / "eval-page.mjs"), "--jsfile", str(jsfile)]
    cdp = os.environ.get("HACKATHON_CDP_URL")
    if cdp:
        cmd += ["--cdp", cdp]
    tgt = target or os.environ.get("CHAT_TARGET")
    if tgt:
        cmd += ["--target", tgt]           # deterministic addressing; wins over --match
    elif match:
        cmd += ["--match", str(match)]
    return sh(cmd, timeout=timeout)


def chat_id_from_href(href):
    m = re.search(r"chatId=([0-9a-fA-F]+)", href or "")
    return m.group(1) if m else None


def open_chat(target, chat_id, base_url=None):
    base = base_url or BASE_URL
    return arena("open", "--target", target, "--url", f"{base}?chatId={chat_id}")


def read_meta(target, chat_id):
    """Probe the already-open chat: model/banner/judgeDisabled/pcts/msgHead."""
    # target MUST be forwarded explicitly: with an empty CHAT_TARGET env the runner
    # otherwise falls back to substring matching and can read ANOTHER session's tab
    # (incident 2026-11-10: probe read the sibling's proving-ground tab).
    rc, out, err = evaljs(HERE / "probe-chat.js", target=target)
    if rc != 0:
        return {"error": "probe failed", "detail": (out + err)[:300]}
    try:
        d = json.loads(out)
        d["chatId"] = chat_id
        return d
    except Exception:
        return {"error": "probe parse failed", "raw": out[:300], "chatId": chat_id}


def open_and_meta(target, chat_id, base_url=None, settle=2.5):
    open_chat(target, chat_id, base_url)
    time.sleep(settle)
    return read_meta(target, chat_id)


def read_submitted_rows(target, out_path):
    rc, out, err = sh([sys.executable, str(HERE / "arena_chats.py"), "--target", target,
                       "--tab", "submitted", "--out", out_path], timeout=300)
    if rc != 0:
        return None, (out + err)[:400]
    try:
        d = json.loads(pathlib.Path(out_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"parse failed: {exc}"
    return d.get("entries", []), None


def do_find(a):
    if a.bootstrap_chat_id:
        open_chat(a.target, a.bootstrap_chat_id, a.base_url)
        time.sleep(2)
    tmp = f"artifacts/_chatops_chats_{int(time.time())}.json"
    args = [sys.executable, str(HERE / "arena_chats.py"), "--target", a.target,
            "--tab", a.tab, "--out", tmp]
    if a.scope:
        args += ["--scope", a.scope]
    if getattr(a, "board_substr", None):
        args += ["--board-substr", a.board_substr]
    rc, out, err = sh(args, timeout=300)
    if rc != 0:
        print(json.dumps({"error": "arena_chats failed (pass --bootstrap-chat-id?); "
                                   "current tab needs a chatId",
                          "detail": (out + err)[:400]}, ensure_ascii=False))
        return 1
    d = json.loads(pathlib.Path(tmp).read_text(encoding="utf-8"))
    entries = d.get("entries", [])
    rc2, out2, err2 = evaljs(HERE / "chat-links.js", target=a.target)
    links = []
    if rc2 == 0:
        try:
            links = json.loads(out2).get("rows", [])
        except Exception:
            links = []
    # Pair entries with row links: prefer text match on the exact model name,
    # fall back to DOM-order index pairing. Ragged pairing is only a warning.
    used = set()
    rows = []
    for i, e in enumerate(entries):
        cid, pair = None, "index"
        for j, l in enumerate(links):
            if j in used:
                continue
            if e.get("model") and e["model"] in (l.get("text") or ""):
                cid, used, pair = chat_id_from_href(l.get("href")), used | {j}, "model-text"
                break
        if cid is None and i < len(links) and i not in used:
            cid, used = chat_id_from_href(links[i].get("href")), used | {i}
        rows.append({**e, "chatId": cid, "pairing": pair})
    if a.model:
        rows = [r for r in rows if a.model.lower() in (r.get("model") or "").lower()]
    if a.scenario:
        rows = [r for r in rows if a.scenario.lower() in (r.get("scenario") or "").lower()]
    result = {"counters": d.get("counters", {}), "n_entries": len(entries),
              "n_links": len(links), "n_matched": len(rows),
              "pairing_ok": len(links) == len(entries), "rows": rows}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def do_open(a):
    open_chat(a.target, a.chat_id, a.base_url)
    print(json.dumps({"ok": True, "chatId": a.chat_id}))
    return 0


def do_meta(a):
    meta = open_and_meta(a.target, a.chat_id, a.base_url)
    print(json.dumps(meta, ensure_ascii=False))
    return 0 if not meta.get("error") else 1


def do_read(a):
    open_chat(a.target, a.chat_id, a.base_url)
    time.sleep(2.5)
    rc, out, err = evaljs(HERE / "read-text.js", target=a.target)
    if rc != 0:
        print(json.dumps({"error": "read failed", "detail": (out + err)[:300]}))
        return 1
    text = out
    out_path = a.out or f"artifacts/chat-{a.chat_id[:8]}.txt"
    pathlib.Path(out_path).write_text(text, encoding="utf-8")
    parts = re.split(r"(Today \d{1,2}:\d{2}\s?[APap][Mm])", text)
    blocks = [{"time": parts[i].strip(), "text": parts[i + 1].strip()[:400]}
              for i in range(1, len(parts) - 1, 2)
              if parts[i + 1].strip()]
    print(json.dumps({"saved": out_path, "chars": len(text), "n_blocks": len(blocks),
                      "last_block": blocks[-1] if blocks else None}, ensure_ascii=False))
    return 0


def bind_for_chat(a, model):
    scope = a.scope or f"inputs/scope-chatops-{a.chat_id[:8]}.json"
    from farm import bind_scope  # local helper with model-unknown retry
    ok, note = bind_scope(a.target, a.track, a.scenario_id, model, a.board, scope,
                          f"chat_ops {a.cmd} in chat {a.chat_id}")
    return ok, note, scope


def do_followup(a):
    meta = open_and_meta(a.target, a.chat_id, a.base_url)
    model = meta.get("model")
    if not model or meta.get("error"):
        print(json.dumps({"error": "chat model not resolved", "meta": meta}, ensure_ascii=False))
        return 1
    ok, note, scope = bind_for_chat(a, model)
    if not ok:
        print(json.dumps({"error": "bind failed", "detail": note, "model": model}, ensure_ascii=False))
        return 1
    opid = a.opid or f"chatops-{a.chat_id[:8]}-followup-{int(time.time())}"
    sf = f"artifacts/chatops-{a.chat_id[:8]}-followup-send.json"
    rc, out, err = arena("send", "--scope", scope, "--file", a.file,
                         "--operation-id", opid, "--timeout-ms", "180000", "--out", sf)
    status = None
    try:
        d = json.loads(pathlib.Path(sf).read_text(encoding="utf-8"))
        res = d.get("result", d)
        status = res.get("status")
    except Exception:
        pass
    print(json.dumps({"ok": rc == 0, "model": model, "opid": opid, "send_file": sf,
                      "status": status, "detail": (out + err)[:300]}, ensure_ascii=False))
    return 0 if rc == 0 else 1


def do_judge(a):
    meta = open_and_meta(a.target, a.chat_id, a.base_url)
    model = meta.get("model")
    if not model or meta.get("error"):
        print(json.dumps({"error": "chat model not resolved", "meta": meta}, ensure_ascii=False))
        return 1
    ok, note, scope = bind_for_chat(a, model)
    if not ok:
        print(json.dumps({"error": "bind failed", "detail": note, "model": model}, ensure_ascii=False))
        return 1
    opid = a.opid or f"chatops-{a.chat_id[:8]}-judge-{int(time.time())}"
    jf = f"artifacts/chatops-{a.chat_id[:8]}-judge.json"
    rc, out, err = sh([sys.executable, str(HEAL), "judge", "--target", a.target,
                       "--scope", scope, "--operation-id", opid,
                       "--timeout-ms", str(a.timeout_ms), "--out", jf],
                      timeout=(a.timeout_ms // 1000 + 150))
    verdict = None
    try:
        d = json.loads(pathlib.Path(jf).read_text(encoding="utf-8"))
        res = d.get("result", d)
        verdict = res.get("status")
    except Exception:
        pass
    if verdict in (None, "unknown"):
        m = re.search(r'"status": "(accepted|rejected)"', out)
        if m:
            verdict = m.group(1)
    print(json.dumps({"ok": rc == 0, "model": model, "opid": opid, "verdict": verdict,
                      "judge_file": jf, "detail": (out + err)[:300]}, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, need_chat_id=True):
        p.add_argument("--target", required=True)
        p.add_argument("--base-url", default=None,
                       help="board base URL override (e.g. Lucky Break: Payday); default Proving Ground")
        if need_chat_id:
            p.add_argument("--chat-id", required=True)

    p = sub.add_parser("find")
    common(p, need_chat_id=False)
    p.add_argument("--model")
    p.add_argument("--scenario")
    p.add_argument("--scope")
    p.add_argument("--tab", default="chats", choices=["chats", "submitted"])
    p.add_argument("--bootstrap-chat-id")
    p.add_argument("--board-substr", default=None,
                   help="passthrough to arena_chats --board-substr (e.g. lucky-break-payday)")
    p.add_argument("--out")
    p.set_defaults(fn=do_find)

    p = sub.add_parser("open")
    common(p)
    p.set_defaults(fn=do_open)

    p = sub.add_parser("meta")
    common(p)
    p.set_defaults(fn=do_meta)

    p = sub.add_parser("read")
    common(p)
    p.add_argument("--out")
    p.set_defaults(fn=do_read)

    p = sub.add_parser("followup")
    common(p)
    p.add_argument("--scenario-id", required=True)
    p.add_argument("--track", default="Chat", choices=["Chat", "Image", "Agent", "Indirect"])
    p.add_argument("--file", required=True)
    p.add_argument("--scope")
    p.add_argument("--opid")
    p.add_argument("--board", default="Proving Ground")
    p.set_defaults(fn=do_followup)

    p = sub.add_parser("judge")
    common(p)
    p.add_argument("--scenario-id", required=True)
    p.add_argument("--track", default="Chat", choices=["Chat", "Image", "Agent", "Indirect"])
    p.add_argument("--scope")
    p.add_argument("--opid")
    p.add_argument("--board", default="Proving Ground")
    p.add_argument("--timeout-ms", type=int, default=90000)
    p.set_defaults(fn=do_judge)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
