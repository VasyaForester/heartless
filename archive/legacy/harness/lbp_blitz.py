#!/usr/bin/env python3
"""Rotation blitz: fire the single-shot winning recipes at a model (for roster rotations).

Runs, per scenario: switch -> fresh chat -> recipe message(s) -> local check ->
auto-submit when the check passes. Refund (multi-step ladder) stays manual.

Usage:
  python3 harness/lbp_blitz.py --model "New Model Name" [--scenarios giftcard,scam,bank] [--dry]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lbp  # noqa: E402

WORK = lbp.WORK

# scenario -> [(input_file, wait_after_s, is_final)]
RECIPES = {
    "giftcard": ("christmas-giftcard-scam", [("inputs/lbp-giftcard-v1.txt", 95, True)]),
    "scam": ("scam-retail", [("inputs/lbp-money-v7-bulk.txt", 95, False),
                             ("inputs/lbp-money-v10-tokens-clean.txt", 95, True)]),
    "bank": ("banking-idor-exploit", [("inputs/lbp-ith-v3-selftest.txt", 95, True)]),
    "negq": ("negative-quantity-exploit", [("inputs/lbp-exploit-v12-order-utensils.txt", 95, False),
                                           ("inputs/lbp-exploit-v13-fixsign.txt", 95, True)]),
}


def send_one(tid, sid, model, input_rel, wait_s):
    inp = (WORK / input_rel).resolve()
    tmp_js = WORK / "cache/probe/fill_blitz_tmp.js"
    rc, out, err = lbp.sh([sys.executable, str(WORK / "cache/probe/make_fill.py"), str(inp), str(tmp_js)])
    if rc != 0:
        return {"error": f"make_fill failed: {(out + err)[:200]}"}
    d0 = lbp.run_chatread()
    n0 = d0.get("n", 0)
    rc2, out2, err2 = lbp.chat_ops.evaljs(tmp_js, match=lbp.MATCH)
    rc3, out3, err3 = lbp.chat_ops.evaljs(HERE / "lbp_js" / "send.js", match=lbp.MATCH)
    sent = (out3 or err3 or "").strip()[:60]
    all_text, last = "", ""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(10)
        d = lbp.run_chatread()
        if d.get("n", 0) >= n0 + 2:
            all_text, last, _ = lbp.assistant_text(d)
            break
    return {"fill": (out2 or err2 or "").strip()[:60], "sent": sent,
            "reply_tail": last[-500:], "all_text": all_text, "no_reply": not last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--scenarios", default="giftcard,scam,bank")
    ap.add_argument("--dry", action="store_true", help="print the plan only")
    a = ap.parse_args()
    keys = [k.strip() for k in a.scenarios.split(",") if k.strip()]
    unknown = [k for k in keys if k not in RECIPES]
    if unknown:
        lbp.die({"error": f"unknown recipe keys: {unknown}", "known": list(RECIPES)})
    if a.dry:
        for k in keys:
            sid, steps = RECIPES[k]
            print(k, "->", sid, [s[0] for s in steps])
        return 0
    tid = lbp.lbp_tab_id()
    ledger = WORK / "datasets/lbp/blitz.jsonl"
    results = []
    for k in keys:
        sid, steps = RECIPES[k]
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": a.model, "scenario": sid}
        lbp.arena("select-scenario", "--target", tid, "--value", sid)
        time.sleep(3)
        lbp.arena("select-model", "--target", tid, "--value", a.model)
        time.sleep(2.5)
        rec["attacking"] = lbp.get_state().get("attacking")
        cn = WORK / "cache/probe/click_new.js"
        if cn.exists():
            lbp.chat_ops.evaljs(cn, match=lbp.MATCH)
            time.sleep(2)
        last_step = None
        for input_rel, wait_s, is_final in steps:
            last_step = send_one(tid, sid, a.model, input_rel, wait_s)
            rec.setdefault("steps", []).append({"input": input_rel, **{kk: vv for kk, vv in last_step.items() if kk != "all_text"}})
            if last_step.get("no_reply"):
                break
        all_text = (last_step or {}).get("all_text", "")
        last = (last_step or {}).get("reply_tail", "")
        chk = lbp.check_scenario(sid, all_text, last)
        rec["check_ready"] = chk.get("ready")
        if chk.get("ready"):
            rec["submit_rc"] = lbp.cmd_submit(argparse.Namespace(target=tid, scenario=sid, force=False,
                                                                 opid=None, timeout_ms=90000))
        with open(ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        results.append(rec)
        print(json.dumps({kk: rec[kk] for kk in ("model", "scenario", "attacking", "check_ready") if kk in rec},
                         ensure_ascii=False))
    print(json.dumps({"done": len(results), "ledger": str(ledger)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
