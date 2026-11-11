#!/usr/bin/env python3
"""Captures judge receipts for specific submissions (variant of `lbp.py eval`).

Modes:
  --list            dump submissionId links currently rendered in the modal
  --sid <id>        open the submission page directly (?submissionId=..&panel=evaluation),
                    click SEE EVALUATION if needed, dump the panel
  --row <N>         legacy: click the N-th (0-based) submission link in the modal

Row/sid order on the SUBMITTED page (newest first). Run `python3 harness/lbp.py reload`
first if an eval panel may still be open (the dump would show the OLD panel).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))
import chat_ops  # noqa: E402

MATCH = "lucky-break-payday"
BOARD_URL = "https://app.grayswan.ai/arena/challenge/lucky-break-payday"


def raw(jsfile):
    rc, out, err = chat_ops.evaljs(HERE / "lbp_js" / jsfile, match=MATCH)
    if rc != 0:
        raise SystemExit(json.dumps({"error": f"eval failed: {jsfile}", "detail": (out + err)[:300]}))
    return out


def lbp_tab():
    rc, out, err = chat_ops.arena("tabs", timeout=120)
    for t in json.loads(out).get("result", []):
        if "lucky-break-payday" in (t.get("url") or ""):
            return t["id"]
    raise SystemExit(json.dumps({"error": "no lucky-break-payday tab found"}))


def save_receipt(receipt, tag):
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = WORK / f"artifacts/lbp-eval-{tag}-{ts}.txt"
    out_path.write_text(receipt, encoding="utf-8")
    print(receipt[:1500])
    print(f"...\nreceipt saved: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", type=int)
    ap.add_argument("--sid")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        print(raw("submission_links.js"))
        return 0

    if a.sid:
        tid = lbp_tab()
        url = f"{BOARD_URL}?submissionId={a.sid}&panel=evaluation"
        rc, out, err = chat_ops.arena("open", "--target", tid, "--url", url, timeout=180)
        if rc != 0:
            raise SystemExit(json.dumps({"error": "open failed", "detail": (out + err)[:300]}))
        time.sleep(3)
        print(raw("full_eval.js"))
        time.sleep(2)
        save_receipt(raw("eval_panel_dump.js"), f"sid-{a.sid[:10]}")
        return 0

    if a.row is not None:
        print(raw(f"full_eval_row{a.row}.js"))
        time.sleep(2)
        save_receipt(raw("eval_panel_dump.js"), f"row{a.row}")
        return 0

    raise SystemExit("specify --list, --sid <id> or --row <N>")


if __name__ == "__main__":
    sys.exit(main())
