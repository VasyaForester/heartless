#!/usr/bin/env python3
"""Nightly custodian: keep the lane alive, finish the open experiments, record.

Runs unattended (cron, no LLM): everything here is deterministic, logged and
reversible.  It is the piece that makes "work through the night" a property of
the stand rather than of a chat session.

What it does, in order
----------------------
1. LANE HEALTH — supervisor lock pid alive?  driver log fresh?  A stale log with
   a live supervisor is the wedge the supervisor's own watchdog is supposed to
   catch; if both look wrong, it restarts the lane (lanes/lane_restart.py), which
   is the documented, test-covered path (RULES 71).

2. REGRESSION GUARD — the offline suite and config_check.  A failure is reported
   loudly and recorded; nothing else is touched until it passes.

3. A/B GENERATOR EXPERIMENT (pre-registered decision rule, written BEFORE the
   data arrived, so the decision cannot be chosen after seeing it):
     * verdict "control_repeat" (composing new frames LOSES) -> set
       generate="off" in artifacts/lane-flags.json: stop spending probes on new
       frames, keep the catalog.
     * verdict "generated" (frames WIN) -> keep generating; record the decision.
     * verdict "undecided" -> nothing but a recorded plan (how many probes the
       power analysis says are still needed).
   The verdict function itself enforces the sample guard and non-overlapping
   intervals, so a decision here is a real decision.  Applied at most once.

4. PROXY CALIBRATION — once >= 30 paired (judge, proxy) probes exist, record
   whether the proxy is monotone with the judge.  The reward mapping is NOT
   changed automatically: that is a design choice with a wider blast radius, so
   it is recorded and left to a human/labelled decision.

5. LEDGER — one compact status line appended to artifacts/nightly.log and a JSON
   record to artifacts/nightly.jsonl, so the night can be read back in the
   morning.

Usage:
    python3 harness/nightly.py                 # one pass
    python3 harness/nightly.py --dry-run       # decide, act on nothing
    python3 harness/nightly.py --skip-tests    # quick pass (no suite)
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import winquiet  # noqa: E402

ARTIFACTS = WORK / "artifacts"
NIGHTLY_LOG = ARTIFACTS / "nightly.log"
NIGHTLY_JSONL = ARTIFACTS / "nightly.jsonl"
AB_DECISION = ARTIFACTS / "ab-decision.json"
CALIB = ARTIFACTS / "reward-calibration.json"
LOCK = ARTIFACTS / "supervisor.lock"
FLAGS = ARTIFACTS / "lane-flags.json"
DRIVER_LOG = ARTIFACTS / "driver.log"
LANE = os.environ.get("HERMES_LANE", "main")
STALE_LANE_S = 30 * 60
RESTART_COOLDOWN_S = 10 * 60
LAST_RESTART = ARTIFACTS / "nightly-last-restart.json"


def now() -> float:
    return time.time()


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def run(cmd: list, timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(WORK), capture_output=True, text=True,
                           timeout=timeout, **winquiet.windowless_kwargs())
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -9, f"timeout after {timeout}s"


def lane_health() -> dict:
    """(alive, log_age_s, note) — read-only, and LANE-AWARE.

    artifacts/driver.log is shared by every lane, so the file's mtime alone can be
    refreshed by the other lane while THIS lane is wedged (measured 2026-11-14:
    main and pg lines interleave in one file).  Progress is therefore counted from
    this lane's own markers, compared with the previous custodian pass.
    """
    import store
    import logwatch
    pid, age = None, None
    try:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        pid = int(lock.get("pid"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pid = None
    alive = bool(pid) and store.pid_alive(pid)
    if DRIVER_LOG.is_file():
        age = now() - DRIVER_LOG.stat().st_mtime
    paused = (ARTIFACTS / "supervisor.paused").is_file()
    progress = logwatch.lane_progress(DRIVER_LOG, LANE) if DRIVER_LOG.is_file() else -1
    state_path = ARTIFACTS / "nightly-lane-progress.json"
    previous = {}
    try:
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}
    advanced = previous.get("progress") != progress
    if not paused:
        try:
            state_path.write_text(json.dumps({"progress": progress, "ts": now(),
                                              "lane": LANE}), encoding="utf-8")
        except OSError:
            pass
    note = "ok"
    if paused:
        note = "paused by operator flag — not restarting"
    elif not alive:
        note = "supervisor not alive"
    elif previous and not advanced and now() - float(previous.get("ts") or now()) > STALE_LANE_S:
        note = (f"no {LANE}-lane lines since the last pass "
                f"({int(now() - float(previous.get('ts') or now()))}s) — supervisor alive")
    return {"supervisor_pid": pid, "alive": alive, "log_age_s": age,
            "lane_progress": progress, "lane_advanced": advanced,
            "paused": paused, "note": note, "lane": LANE}


def maybe_restart(health: dict, dry_run: bool) -> dict:
    """Restart only when the lane is genuinely not running (never on a pause)."""
    if health["paused"]:
        return {"restarted": False, "why": "paused"}
    if health["alive"] and (health["log_age_s"] is None or health["log_age_s"] <= STALE_LANE_S):
        return {"restarted": False, "why": "healthy"}
    if health["alive"]:
        # supervisor alive but the log stopped: its own stale-log watchdog owns
        # this case (terminate -> rc=124 -> restart).  Do not double-act.
        return {"restarted": False, "why": "leaving the wedge to the supervisor watchdog"}
    last = 0.0
    try:
        last = float(json.loads(LAST_RESTART.read_text(encoding="utf-8")).get("ts", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    if now() - last < RESTART_COOLDOWN_S:
        return {"restarted": False, "why": f"cooldown ({now() - last:.0f}s since last restart)"}
    if dry_run:
        return {"restarted": False, "why": "dry-run: would restart the lane"}
    rc, out = run([sys.executable, str(WORK / "tools" / "lane_restart.py")], timeout=300)
    LAST_RESTART.write_text(json.dumps({"ts": now(), "rc": rc, "tail": out[-400:]}),
                            encoding="utf-8")
    return {"restarted": True, "rc": rc, "tail": out[-200:]}


def regression_guard() -> dict:
    rc, out = run([sys.executable, str(HERE / "run_offline_tests.py")], timeout=1800)
    tests = [ln for ln in out.splitlines() if ln.startswith("SUMMARY")]
    failing = " | ".join(ln.strip() for ln in out.splitlines() if ln.startswith("FAIL:"))[:400]
    rc2, out2 = run([sys.executable, str(HERE / "config_check.py"), "--quiet"], timeout=600)
    return {"tests_rc": rc, "tests": tests[-1] if tests else out[-160:].strip(),
            "failing": failing, "config_check_rc": rc2, "ok": rc == 0 and rc2 == 0}


def apply_decision(call: str, dry_run: bool) -> dict:
    """Apply the pre-registered action for a decided A/B (see module docstring).

    Extracted so the rule can be tested without running the report:
      control_repeat (new frames lose) -> generate="off" + restart requested
      generated      (new frames win)  -> no change
    Applied at most once per call value; every application is recorded.
    """
    try:
        previous = json.loads(AB_DECISION.read_text(encoding="utf-8")).get("call")
    except (OSError, json.JSONDecodeError):
        previous = None
    if previous == call:
        return {"action": "already decided earlier — no change"}
    action = "recorded"
    if call == "control_repeat":
        try:
            flags = json.loads(FLAGS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            flags = {}
        flags["generate"] = "off"
        if dry_run:
            action = "dry-run: would set generate=off in lane-flags.json"
        else:
            FLAGS.write_text(json.dumps(flags, ensure_ascii=False, indent=2), encoding="utf-8")
            (ARTIFACTS / "restart.requested").touch()
            action = "applied: generate=off (takes effect on the next driver start)"
    if not dry_run:
        AB_DECISION.write_text(
            json.dumps({"ts": now(), "call": call, "action": action},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    return {"action": action}


def ab_verdict(dry_run: bool) -> dict:
    rc, out = run([sys.executable, str(HERE / "ab_report.py"), "--json"], timeout=600)
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        return {"call": "error", "detail": out[-200:].strip()}
    (ARTIFACTS / "ab-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    verdict = report.get("verdict", {})
    call = verdict.get("call")
    result = {"call": call, "reason": verdict.get("reason"),
              "n": {"generated": report["generated"]["n"],
                    "control_repeat": report["control_repeat"]["n"]},
              "action": "none"}
    if call not in ("generated", "control_repeat"):
        result["still_needed"] = (verdict.get("power") or {}).get("still_needed")
        return result
    result.update(apply_decision(call, dry_run))
    return result


def calibration() -> dict:
    rc, out = run([sys.executable, str(HERE / "reward_audit.py"), "--tail", "0",
                   "--calibrate", "--json"], timeout=600)
    try:
        report = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "detail": out[-160:].strip()}
    cal = report.get("calibration", {})
    cal["ok"] = True
    CALIB.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return cal


def bench_quick() -> dict:
    rc, out = run([sys.executable, str(HERE / "strategy_bench.py"), "--budget", "300",
                   "--seeds", "9", "--min-probes-per-context", "20", "--arms", "catalog",
                   "--out", str(ARTIFACTS / "strategy-bench-nightly.json")], timeout=1200)
    line = [ln for ln in out.splitlines() if ln.startswith("winner:")]
    return {"rc": rc, "winner": line[-1].strip() if line else out[-120:].strip()}


def console_audit() -> dict:
    """Any VISIBLE console window from our chain is a defect (2026-11-14).

    The windows flash because a console program was spawned by a parent without a
    console (a DETACHED supervisor, a GUI app, a scheduler).  Closing such a window
    kills the child (STATUS_CONTROL_C_EXIT).  Run the audit every pass so a leak is
    reported instead of being rediscovered by the user.
    """
    rc, out = run([sys.executable, str(WORK / "tools" / "console_audit.py"), "--json"],
                  timeout=120)
    try:
        leaks = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "detail": out[-160:].strip()}
    return {"ok": not leaks, "leaks": leaks[:5], "n": len(leaks)}


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    a = ap.parse_args()
    record: dict = {"ts": now(), "at": stamp()}
    health = lane_health()
    record["lane"] = health
    record["restart"] = maybe_restart(health, a.dry_run)
    if not a.skip_tests:
        record["regression"] = regression_guard()
    record["ab"] = ab_verdict(a.dry_run)
    record["calibration"] = calibration()
    record["bench"] = bench_quick()
    record["console"] = console_audit()
    import sqlite3
    try:
        conn = sqlite3.connect(f"file:{ARTIFACTS / 'harness.db'}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        hour = conn.execute("SELECT COUNT(*) n FROM attempts WHERE started_at>?",
                            (now() - 3600,)).fetchone()["n"]
        wins = conn.execute("SELECT COUNT(*) n FROM attempts WHERE started_at>? AND reward>=0.5",
                            (now() - 3600,)).fetchone()["n"]
        best = conn.execute("SELECT MAX(score) s FROM attempts WHERE judge_status='verified'"
                            ).fetchone()["s"]
        record["throughput"] = {"attempts_1h": hour, "reward_ge_0.5_1h": wins,
                                "best_verified_score": best}
    except Exception as exc:  # noqa: BLE001
        record["throughput"] = {"error": f"{type(exc).__name__}: {exc}"}
    if not a.dry_run:
        with NIGHTLY_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        line = (f"[{record['at']}] lane={'ok' if health['alive'] and not health['paused'] else health['note']}"
                f" tests={record.get('regression', {}).get('tests', 'skipped')}"
                f" ab={record['ab'].get('call')}({record['ab'].get('action')})"
                f" calib={record['calibration'].get('pairs', '?')}pairs"
                f" bench={record['bench'].get('winner', '?')}"
                f" probes1h={record['throughput'].get('attempts_1h')}")
        with NIGHTLY_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    # A non-zero exit is reserved for things a human must look at — and the message
    # must say WHICH thing: the earlier version printed the JSON tail, hiding the
    # failing part (a red suite ran for hours as a wall of numbers).
    problems = []
    if not health["alive"] and not health["paused"]:
        problems.append(f"lane down: {health['note']}")
    if record.get("restart", {}).get("restarted"):
        problems.append(f"lane restarted: {record['restart'].get('tail', '')[:120]}")
    reg = record.get("regression") or {}
    if reg and not reg.get("ok"):
        problems.append(f"regression guard failed ({reg.get('tests')}) {reg.get('failing', '')}".strip())
    if record["ab"].get("call") == "error":
        problems.append(f"A/B report error: {record['ab'].get('detail')}")
    if not record["console"].get("ok", True):
        problems.append(f"console leak: {record['console'].get('leaks')}")
    record["problems"] = problems
    if problems and not a.dry_run:
        print("PROBLEMS: " + "; ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
