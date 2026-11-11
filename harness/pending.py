#!/usr/bin/env python3
"""Pending-results ledger: track judge outcomes that have not materialized yet.

Ledger file: artifacts/pending_ledger.json  (single local source of "evaluation expected").
Statuses: waiting | found | expired | cancelled | error — `expired` is NOT a negative
result, it stays visible in the ledger.

Subcommands:
  add     --model M --scenario S [--track Chat] [--chat-id ID] [--opid OP] [--note N]
          [--deadline-hours 24]
  list    [--status waiting]
  due
  poll    --target T [--limit 8] [--bootstrap-chat-id ID] [--base-url U] [--board-substr S]
          Re-check due items against the live platform (read-only):
          path 1 — items with a chatId: open the chat, read its verdict banner;
          path 2 — everything else: read the SUBMITTED list, match model+scenario filter.
          ALWAYS pass --base-url/--board-substr for non-Proving-Ground boards (a stale ledger
          chatId once dragged the tab off Lucky Break: bootstrap preference + passthrough fix).
          Backoff: <1m +15s; <5m +1m; <30m +5m; <2h +15m; else +1h.
  resolve --id pend-NNNN --status found|expired|cancelled --evidence "..."
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timedelta

HERE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
from scenario_filters import filter_for  # noqa: E402

LEDGER = pathlib.Path("artifacts/pending_ledger.json")


def sh(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_iso(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return datetime.now()


def load():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"schemaVersion": 1, "nextId": 1, "items": []}


def save(led):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=2, ensure_ascii=False), encoding="utf-8")


def backoff(age_s: float) -> int:
    if age_s < 60:
        return 15
    if age_s < 300:
        return 60
    if age_s < 1800:
        return 300
    if age_s < 7200:
        return 900
    return 3600


def touch(it, ok=True):
    now = datetime.now()
    it["lastPolledAt"] = iso(now)
    it["pollCount"] = it.get("pollCount", 0) + 1
    it["nextPollAt"] = iso(now + timedelta(seconds=backoff((now - parse_iso(it["createdAt"])).total_seconds())))
    if ok:
        it["errors"] = 0
    else:
        it["errors"] = it.get("errors", 0) + 1
        if it["errors"] >= 3 and it["status"] == "waiting":
            it["status"] = "error"
            it["evidence"] = "poll failed 3+ times; needs manual review"


def settle(it, status, evidence):
    it["status"] = status
    it["evidence"] = evidence
    it["resolvedAt"] = iso(datetime.now())


def do_add(a):
    led = load()
    for it in led["items"]:
        if (it.get("status") == "waiting" and it.get("model") == a.model
                and it.get("scenario") == a.scenario
                and ((a.opid and it.get("opid") == a.opid)
                     or (a.chat_id and it.get("chatId") == a.chat_id))):
            print(json.dumps({"ok": True, "skipped": "duplicate waiting item", "id": it["id"]},
                             ensure_ascii=False))
            return 0
    now = datetime.now()
    it = {
        "id": f"pend-{led['nextId']:04d}",
        "model": a.model, "scenario": a.scenario, "track": a.track,
        "chatId": a.chat_id, "opid": a.opid, "note": a.note or "",
        "createdAt": iso(now), "lastPolledAt": None, "pollCount": 0, "errors": 0,
        "nextPollAt": iso(now + timedelta(seconds=15)),
        "deadline": iso(now + timedelta(hours=a.deadline_hours)),
        "status": "waiting", "evidence": "",
    }
    led["nextId"] += 1
    led["items"].append(it)
    save(led)
    print(json.dumps({"ok": True, "added": it}, ensure_ascii=False))
    return 0


def do_list(a):
    led = load()
    items = led["items"]
    if a.status:
        items = [i for i in items if i.get("status") == a.status]
    for it in items:
        print(f"{it['id']} | {it['status']:<9} | {it['model']:<28} | {it['scenario']:<34} | "
              f"chat={str(it.get('chatId'))[:10]:<10} | polls={it.get('pollCount', 0)} | "
              f"next={it.get('nextPollAt')} | {it.get('note', '')[:40]}")
    print(json.dumps({"total": len(items)}, ensure_ascii=False))
    return 0


def do_due(a):
    led = load()
    now = datetime.now()
    due = [i for i in led["items"]
           if i.get("status") == "waiting" and parse_iso(i.get("nextPollAt", "")) <= now]
    for it in due:
        print(f"{it['id']} | {it['model']} | {it['scenario']} | next was {it.get('nextPollAt')}")
    print(json.dumps({"due": len(due)}, ensure_ascii=False))
    return 0


def chat_meta(target, chat_id, base_url=None):
    cmd = [sys.executable, str(HERE / "chat_ops.py"), "meta",
           "--target", target, "--chat-id", chat_id]
    if base_url:
        cmd += ["--base-url", base_url]
    rc, out, err = sh(cmd)
    try:
        return json.loads(out)
    except Exception:
        return {"error": "meta parse failed", "detail": (out + err)[:200]}


def do_poll(a):
    led = load()
    now = datetime.now()
    due = [i for i in led["items"]
           if i.get("status") == "waiting" and parse_iso(i.get("nextPollAt", "")) <= now]
    due = due[:a.limit]
    out = {"due": len(due), "resolved": [], "still_waiting": [], "errors": []}
    if not due:
        print(json.dumps({"due": 0, "note": "nothing due"}, ensure_ascii=False))
        return 0

    # path 1: items with a chatId — open the chat and read its verdict banner
    unresolved = []
    for it in due:
        if not it.get("chatId"):
            unresolved.append(it)
            continue
        meta = chat_meta(a.target, it["chatId"], a.base_url)
        banner = (meta or {}).get("banner") or "none"
        if "ACCEPTED" in banner:
            settle(it, "found", f"chat banner BREAK ACCEPTED ({iso(now)}); verify in SUBMITTED")
            out["resolved"].append({"id": it["id"], "to": "found", "src": "banner-accepted"})
        elif "REJECTED" in banner:
            settle(it, "found", f"chat banner BREAK REJECTED ({iso(now)})")
            out["resolved"].append({"id": it["id"], "to": "found", "src": "banner-rejected"})
        elif meta.get("error"):
            touch(it, ok=False)
            out["errors"].append({"id": it["id"], "detail": str(meta)[:160]})
        else:
            unresolved.append(it)

    # path 2: everything still unresolved — read the SUBMITTED list once
    if unresolved:
        # Operator-provided bootstrap wins; the ledger's first chatId can belong to ANOTHER board
        # (incident 2026-11-10: a stale Proving-Ground chat dragged the tab off Lucky Break).
        boot = a.bootstrap_chat_id or next((x.get("chatId") for x in led["items"] if x.get("chatId")), None)
        if boot:
            open_cmd = [sys.executable, str(HERE / "chat_ops.py"), "open",
                        "--target", a.target, "--chat-id", boot]
            if a.base_url:
                open_cmd += ["--base-url", a.base_url]
            sh(open_cmd)
            time.sleep(1.5)
        tmp = f"artifacts/_pending_submitted_{int(time.time())}.json"
        ac_cmd = [sys.executable, str(HERE / "arena_chats.py"), "--target", a.target,
                  "--tab", "submitted", "--out", tmp]
        if a.board_substr:
            ac_cmd += ["--board-substr", a.board_substr]
        rc, o, e = sh(ac_cmd)
        entries = None
        if rc == 0:
            try:
                entries = json.loads(pathlib.Path(tmp).read_text(encoding="utf-8")).get("entries", [])
            except Exception:
                entries = None
        if entries is None:
            for it in unresolved:
                touch(it, ok=False)
                out["errors"].append({"id": it["id"], "detail": (o + e)[:160]})
        else:
            for it in unresolved:
                filt = filter_for(it.get("scenario"))
                if not filt:
                    touch(it)
                    out["still_waiting"].append({"id": it["id"], "note": "no scenario filter"})
                    continue
                match = next((x for x in entries
                              if (x.get("model") or "") == it.get("model")
                              and x.get("status") in ("ACCEPTED", "REJECTED")
                              and filt.lower() in (x.get("scenario") or "").lower()), None)
                if match:
                    settle(it, "found", f"SUBMITTED {match['status']} {match['time']}")
                    out["resolved"].append({"id": it["id"], "to": "found",
                                            "src": f"submitted-{match['status'].lower()}"})
                else:
                    touch(it)
                    out["still_waiting"].append({"id": it["id"]})

    # expiry pass over ALL waiting items (expired is not a negative result)
    for it in led["items"]:
        if it.get("status") == "waiting" and parse_iso(it.get("deadline", "")) <= now:
            settle(it, "expired", (it.get("evidence", "") + " | expired, not negative").strip(" |"))

    save(led)
    print(json.dumps(out, ensure_ascii=False))
    print("ledger:", str(LEDGER))
    return 0


def do_resolve(a):
    led = load()
    for it in led["items"]:
        if it["id"] == a.id:
            settle(it, a.status, a.evidence or "")
            save(led)
            print(json.dumps({"ok": True, "item": it}, ensure_ascii=False))
            return 0
    print(json.dumps({"error": f"id not found: {a.id}"}))
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add")
    p.add_argument("--model", required=True)
    p.add_argument("--scenario", required=True)
    p.add_argument("--track", default="Chat", choices=["Chat", "Image", "Agent", "Indirect"])
    p.add_argument("--chat-id")
    p.add_argument("--opid")
    p.add_argument("--note")
    p.add_argument("--deadline-hours", type=int, default=24)
    p.set_defaults(fn=do_add)

    p = sub.add_parser("list")
    p.add_argument("--status")
    p.set_defaults(fn=do_list)

    p = sub.add_parser("due")
    p.set_defaults(fn=do_due)

    p = sub.add_parser("poll")
    p.add_argument("--target", required=True)
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--bootstrap-chat-id")
    p.add_argument("--base-url", default=None,
                   help="board base URL override — ALWAYS set for non-Proving-Ground boards")
    p.add_argument("--board-substr", default=None,
                   help="passthrough to arena_chats --board-substr (e.g. lucky-break-payday)")
    p.set_defaults(fn=do_poll)

    p = sub.add_parser("resolve")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=["found", "expired", "cancelled", "error"])
    p.add_argument("--evidence")
    p.set_defaults(fn=do_resolve)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
