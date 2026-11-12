#!/usr/bin/env python3
"""LBP driver v2.1: reliable attempt identity, fenced leases, explicit states.

Differences from the first v2 draft:
  * SQLite schema v3 (`store.py`): versioning, FK, busy timeout, attempt events.
  * Every attempt gets an id before execution; the id is passed through
    `lbp.py repeat --opid` and must match the judge's `operationId`.
  * Judge correlation is explicit (`judge_correlation.py`): stale, duplicate,
    mismatched operation/chat/transcript and pending are distinct; only a
    verified judge can finalize a pair.
  * Delta generation is data (`generation.py`): parent hash, delta version,
    nonce and seed are persisted; `replay.py` reconstructs the input offline.
  * Lease fencing: every state write proves generation + owner token.

Run: python3 harness/driver.py --lane auto --target <tab> --max-hours 0
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import random
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import attempts  # noqa: E402
import generation  # noqa: E402
import judge_correlation  # noqa: E402
import store  # noqa: E402
from boards import load_board  # noqa: E402
from loop import LBP, MODELS, SCENARIOS, SOLVED, newest_input, sh, slug  # noqa: E402

BOARD = load_board("lucky-break-payday")
BOARD_NAME = BOARD["name"]
PROFILE_HASH = BOARD["_profile_hash"]


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(WORK / "artifacts" / "driver.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def seed(conn) -> None:
    """Seed the 20 pairs from the v1 board; never overwrite newer v2 rows."""
    board = {}
    p = WORK / "artifacts" / "lbp-board.json"
    if p.exists():
        try:
            board = (json.loads(p.read_text(encoding="utf-8")) or {}).get("pairs", {}) or {}
        except Exception:
            board = {}
    for sid in SCENARIOS:
        for model in MODELS:
            key = f"{sid}|{model}"
            b = board.get(key) or {}
            solved = 1 if (b.get("solved") or model in SOLVED.get(sid, set())) else 0
            best = b.get("best_input") or newest_input(sid, model)
            if best:
                bp = pathlib.Path(best)
                if bp.is_absolute():
                    try:
                        best = str(bp.relative_to(WORK))
                    except ValueError:
                        best = str(bp)
            conn.execute(
                "INSERT OR IGNORE INTO pairs(id,board_profile,scenario,model,solved,"
                "best_score,best_input,attempts,last_verdict) VALUES(?,?,?,?,?,?,?,?,?)",
                (key, BOARD_NAME, sid, model, solved, int(b.get("best_score", -1)),
                 best, int(b.get("attempts", 0)), b.get("last_verdict")))
            for delta, st in (b.get("deltas") or {}).items():
                conn.execute(
                    "INSERT OR IGNORE INTO deltas(pair_id,delta,n,sum_score) VALUES(?,?,?,?)",
                    (key, delta, int(st.get("n", 0)), int(st.get("sum", 0))))
    conn.commit()


def pick_pair(conn, rng: random.Random):
    rows = conn.execute("SELECT id,best_score,attempts FROM pairs WHERE solved=0").fetchall()
    if not rows:
        return None
    cold = [r for r in rows if int(r["attempts"] or 0) == 0]
    if cold:
        return rng.choice(cold)["id"]
    total = sum(int(r["attempts"] or 0) for r in rows) or 1
    if rng.random() < 0.35:
        return rng.choice(rows)["id"]
    scored = []
    for r in rows:
        att = max(int(r["attempts"] or 0), 1)
        ucb = int(r["best_score"] or 0) + 45.0 * math.sqrt(2.0 * math.log(total + 1) / att)
        scored.append((ucb, r["id"]))
    scored.sort(reverse=True)
    return scored[0][1]


def make_variant(conn, lease, key: str, rng: random.Random):
    row = conn.execute("SELECT scenario,model,best_input FROM pairs WHERE id=?", (key,)).fetchone()
    if not row:
        return None
    sid, model, best = row["scenario"], row["model"], row["best_input"]
    base = (WORK / best) if best else None
    newest = newest_input(sid, model)
    if newest and (base is None or not base.is_file()
                   or newest.stat().st_mtime > base.stat().st_mtime + 60):
        base = newest
        conn.execute("UPDATE pairs SET best_input=? WHERE id=?",
                     (str(base.relative_to(WORK)), key))
        conn.commit()
    if base is None or not base.is_file():
        return None
    base_text = base.read_text(encoding="utf-8", errors="replace")
    rows = {d: (int(n or 0), int(s or 0)) for d, n, s in
            conn.execute("SELECT delta,n,sum_score FROM deltas WHERE pair_id=?", (key,))}
    for name in generation.DELTAS:
        rows.setdefault(name, (0, 0))
    total = sum(n for n, _ in rows.values()) + 1
    ucb = []
    for name, (n, s) in rows.items():
        if n == 0:
            ucb.append((1e9, name))
        else:
            ucb.append((s / n + 45.0 * math.sqrt(2.0 * math.log(total) / n), name))
    ucb.sort(reverse=True)
    delta = ucb[0][1]
    nonce = f"{time.strftime('%Y%m%d-%H%M%S')}-{rng.randint(1000, 9999)}"
    text = generation.generate(base_text, delta, nonce)
    out = WORK / "inputs" / f"lbp-{sid}-loop2-{delta}-{int(time.time())}-{rng.randint(100, 999)}.txt"
    out.write_text(text, encoding="utf-8")
    attempt_id = attempts.allocate(
        conn, lease, pair_id=key, board=BOARD_NAME, scenario=sid, model=model,
        lane=lease.lane)
    attempts.prepare(
        conn, lease, attempt_id, input_text=text,
        input_path=str(out.relative_to(WORK)),
        parent_input_hash=attempts.sha256_text(base_text),
        parent_input_path=str(base.relative_to(WORK)),
        delta=delta, delta_version=generation.DELTA_VERSION,
        seed=None, nonce=nonce, strategy_version=2)
    return attempt_id, delta, str(out.relative_to(WORK)), sid, model


def energy_now(target: str = "") -> int:
    cmd = [sys.executable, str(LBP), "state"]
    if target:
        cmd += ["--target", target]
    rc, out, err = sh(cmd, timeout=90)
    try:
        d = json.loads(out)
        return int((d.get("energy") or {}).get("current") or 0)
    except Exception:
        return -1


def run_attempt_v2(target: str, key: str, input_path: str, wait_s: int,
                   attempt_id: str):
    sid, model = key.split("|")
    cmd = [sys.executable, str(LBP), "repeat", "--scenario", sid, "--model", model,
           "--input", input_path, "--n", "1", "--wait-s", str(wait_s), "--submit",
           "--opid", attempt_id]
    if target:
        cmd += ["--target", target]
    return sh(cmd, timeout=wait_s + 260)


def judge_path(key: str) -> pathlib.Path:
    sid, model = key.split("|")
    return WORK / "artifacts" / f"lbp-{sid}-{slug(model)}-judge.json"


def transcript_path(key: str) -> pathlib.Path:
    sid, model = key.split("|")
    return WORK / "artifacts" / f"lbp-{sid}-{slug(model)}-submit-transcript.json"


def transcript_info(key: str):
    p = transcript_path(key)
    if not p.is_file():
        return "", None
    text = p.read_text(encoding="utf-8", errors="replace")
    try:
        d = json.loads(text)
        chat = d.get("chatId") or d.get("chat_id")
    except Exception:
        chat = None
    return text, chat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="auto")
    ap.add_argument("--target", default=os.environ.get("CHAT_TARGET", ""))
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--wait-s", type=int, default=60)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--energy-floor", type=int, default=60)
    ap.add_argument("--energy-wait", type=int, default=900)
    ap.add_argument("--max-errors", type=int, default=8)
    ap.add_argument("--max-hours", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    conn = store.connect(a.db)
    seed(conn)
    store.insert_board_profile(conn, BOARD, PROFILE_HASH)
    target = a.target
    if not target:
        rc, out, err = sh([sys.executable, str(WORK / "harness" / "pick_target.py")], timeout=30)
        target = (out or "").strip()
    if not target:
        log("no target (pick_target empty); is the lane browser up?")
        return 3

    lease = store.acquire_lease(conn, a.lane, target)
    if not lease:
        log(f"another worker holds lane {a.lane}; refuse to start")
        return 3
    log(f"DRIVER START lane={a.lane} target={target} pid={os.getpid()} db={a.db} "
        f"board={BOARD_NAME} profile={PROFILE_HASH}")
    recovered = attempts.recover(conn, lease)
    if recovered:
        log(f"RECOVERED {len(recovered)} in-progress attempts: {recovered}")

    rng = random.Random(a.seed)
    started = time.time()
    errors = 0
    try:
        while True:
            if a.max_hours and time.time() - started >= a.max_hours * 3600:
                log("STOP max_hours")
                return 0
            try:
                rr = pathlib.Path(os.environ.get("LOOP_STATE_DIR", str(WORK / "artifacts"))) / "restart.requested"
                if rr.exists():
                    rr.unlink()
                    log("RESTART requested — graceful exit")
                    return 0
            except Exception:
                pass
            store.heartbeat(conn, lease)
            key = pick_pair(conn, rng)
            if not key:
                log("all 20 pairs solved — nothing left")
                return 0
            en = energy_now(target)
            if 0 <= en < a.energy_floor:
                log(f"energy low ({en}) — wait {a.energy_wait}s")
                deadline = time.time() + a.energy_wait
                while time.time() < deadline:
                    store.heartbeat(conn, lease)
                    time.sleep(60)
                    en = energy_now(target)
                    if en >= a.energy_floor:
                        break
                continue
            mv = make_variant(conn, lease, key, rng)
            if not mv:
                log(f"no base input for {key}; sleep 30")
                time.sleep(30)
                continue
            attempt_id, delta, input_path, sid, model = mv
            log(f"ATTEMPT {attempt_id} {key} delta={delta} input={input_path} energy={en}")
            if a.dry_run:
                attempts.mark_failed(conn, lease, attempt_id, "dry-run: not sent")
                log("dry-run: attempt allocated/prepared, not sent")
                return 0
            t0 = time.time()
            try:
                rc, out, err = run_attempt_v2(target, key, input_path, a.wait_s, attempt_id)
            except subprocess.TimeoutExpired:
                rc, out, err = -9, "", "timeout"
            if rc != 0:
                attempts.mark_failed(conn, lease, attempt_id, f"repeat rc={rc}")
                errors += 1
                log(f"ATTEMPT-FAIL {attempt_id} rc={rc} out={(out or '')[-160:]} "
                    f"err={(err or '')[-160:]}")
            else:
                errors = 0
                text, chat = transcript_info(key)
                attempts.mark_submitted(conn, lease, attempt_id, chat_id=chat,
                                        transcript_text=text)
                attempt_row = store.get_attempt(conn, attempt_id)
                result = judge_correlation.correlate(
                    attempt_row, judge_path(key), transcript_text=text,
                    known_operations=store.known_judge_operations(conn))
                if result["status"] == "pending":
                    attempts.mark_awaiting(conn, lease, attempt_id,
                                           judge_ref=result["judge_ref"])
                    log(f"JUDGE pending {attempt_id}: {result['reason']}")
                else:
                    attempts.mark_judge(conn, lease, attempt_id, result)
                    if result["status"] == "verified":
                        solved = result["verdict"] in ("accepted", "solved")
                        attempts.finalize(conn, lease, attempt_id, solved=solved)
                        log(f"RESULT {attempt_id} verdict={result['verdict']} "
                            f"score={result['score']} solved={solved}")
                    else:
                        log(f"JUDGE {result['status']} {attempt_id}: {result['reason']}")
            store.heartbeat(conn, lease)
            solved_count = conn.execute(
                "SELECT COUNT(*) AS c FROM pairs WHERE solved=1").fetchone()["c"]
            log(f"BOARD {solved_count}/20")
            if errors >= a.max_errors:
                log(f"BACKOFF {errors} consecutive failures — sleep 300, not stopping")
                time.sleep(300)
                errors = 0
            time.sleep(a.sleep)
            if a.once:
                return 0
    except KeyboardInterrupt:
        log("interrupted")
        return 0
    finally:
        store.release(conn, lease)
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
