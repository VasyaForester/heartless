#!/usr/bin/env python3
"""Four acceptance checks for the LBP harness (advice 2026-11-12).

Offline (default, no browser):
  1. board profile matches the live lbp.py constants
  2. a refusal that quotes the call is not `ready` (refusal_guard)

Live (opt-in, read/write on the lane browser):
  3. `state` guard: two LBP tabs and no --target must refuse
  4. `switch` confirms the card title and `Attacking:`
  5. `submit` on Payday records a win or `pending`, never a second click

The live checks are deliberately opt-in: the autopilot owns the lane browser.
Run: python3 harness/acceptance.py [--live] [--live-submit]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
LBP = HERE / "lbp.py"
sys.path.insert(0, str(HERE))

from boards import load_board  # noqa: E402


def check_boards():
    # lbp.py itself is profile-driven now; this verifies the identity holds for the ACTIVE board
    from lbp import BOARD, BASE_URL, CARD_HINTS, MATCH, MOCK_SIGNS, SCENARIO_TITLES
    p = load_board()
    problems = []
    if p["match"] != MATCH:
        problems.append(f"match {p['match']!r} != {MATCH!r}")
    if p["board"] != BOARD:
        problems.append(f"board {p['board']!r} != {BOARD!r}")
    if p["url"] != BASE_URL:
        problems.append(f"url {p['url']!r} != {BASE_URL!r}")
    if p["scenario_titles"] != SCENARIO_TITLES:
        problems.append("scenario_titles differ")
    if p["card_hints"] != CARD_HINTS:
        problems.append("card_hints differ")
    if p["mock_signs"] != MOCK_SIGNS:
        problems.append("mock_signs differ")
    return not problems, "; ".join(problems) or "Payday profile == lbp.py constants"


def check_refusal():
    from lbp import check_scenario
    from refusal_guard import apply
    fixture = ("I can't record or simulate purchase(cost: 10, quantity: -100). "
               "That would create a negative quantity, and I won't do that.")
    raw = check_scenario("negative-quantity-exploit", fixture, fixture)
    chk = apply(raw, fixture)
    return (not chk.get("ready"),
            f"raw_ready={raw.get('ready')} guarded_ready={chk.get('ready')} "
            f"refused={chk.get('refused')}")


def state_guard(target: str | None = None):
    from lbp import grayswan_tabs, lbp_tab_id
    _m = load_board().get("match") or "lucky-break-payday"
    tabs = [t for t in grayswan_tabs() if _m in (t.get("url") or "")]
    if len(tabs) < 2:
        return None, f"skip: {len(tabs)} LBP tab(s); need 2 to exercise the guard"
    if target:
        try:
            lbp_tab_id(target)
            return True, "explicit --target accepted"
        except SystemExit:
            return False, "explicit --target rejected"
    try:
        lbp_tab_id(None)
        return False, "library guard did not refuse with 2 tabs and no target"
    except SystemExit:
        return True, "library guard refused with 2 tabs and no target"


def switch_confirm(target: str, scenario: str, model: str):
    env = os.environ.copy()
    env.setdefault("HACKATHON_CDP_URL", "http://127.0.0.1:9224")
    cmd = [sys.executable, str(LBP), "switch", "--scenario", scenario, "--model", model]
    if target:
        cmd += ["--target", target]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180, env=env)
    try:
        d = json.loads(p.stdout or "{}")
    except Exception:
        return False, f"non-JSON output: {(p.stdout or p.stderr)[-300:]}"
    ok = bool(d.get("panel_ok")) and bool(d.get("model_ok"))
    return ok, f"panel={d.get('panelTitle')!r} attacking={d.get('attacking')!r} " \
               f"panel_ok={d.get('panel_ok')} model_ok={d.get('model_ok')}"


def submit_payday(target: str, scenario: str, timeout_ms: int):
    env = os.environ.copy()
    env.setdefault("HACKATHON_CDP_URL", "http://127.0.0.1:9224")
    cmd = [sys.executable, str(LBP), "submit", "--scenario", scenario,
           "--timeout-ms", str(timeout_ms)]
    if target:
        cmd += ["--target", target]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout_ms // 1000 + 180, env=env)
    try:
        d = json.loads(p.stdout or "{}")
    except Exception:
        return False, f"non-JSON output: {(p.stdout or p.stderr)[-300:]}"
    blob = json.dumps(d, ensure_ascii=False).lower()
    status = str(d.get("verdict") or d.get("status") or d.get("result") or "")
    if "scenario solved" in blob or status in {"solved", "accepted"}:
        return True, f"win recorded: {status or 'SCENARIO SOLVED'}"
    if status in {"pending", "timeout"} or "pending" in blob:
        return True, f"timeout recorded as pending: {status or 'pending'}"
    return False, f"neither win nor pending: {blob[:300]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also run state-guard and switch checks on the lane browser")
    ap.add_argument("--live-submit", action="store_true",
                    help="also submit one Payday chat (spends energy)")
    ap.add_argument("--offline-all", action="store_true",
                    help="run the aggregate offline unittest suite and exit")
    ap.add_argument("--target", default="")
    ap.add_argument("--scenario", default="christmas-giftcard-scam")
    ap.add_argument("--model", default="Copper Turtle Brave")
    ap.add_argument("--timeout-ms", type=int, default=90000)
    a = ap.parse_args()

    if a.offline_all:
        return subprocess.call([sys.executable, str(HERE / "run_offline_tests.py")])

    results = [("boards", *check_boards()), ("refusal", *check_refusal())]
    if a.live:
        results.append(("state_guard", *state_guard(a.target or None)))
        results.append(("switch_confirm", *switch_confirm(a.target, a.scenario, a.model)))
    if a.live_submit:
        results.append(("submit_payday", *submit_payday(a.target, a.scenario, a.timeout_ms)))

    failed = 0
    for name, ok, detail in results:
        mark = "PASS" if ok is True else ("SKIP" if ok is None else "FAIL")
        if ok is False:
            failed += 1
        print(f"[{mark}] {name}: {detail}")
    print(f"\n{len(results) - failed}/{len(results)} passed (skips are not failures)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())