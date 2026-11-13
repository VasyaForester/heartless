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
import candidate  # noqa: E402
import evidence  # noqa: E402
import frames  # noqa: E402
import generation  # noqa: E402
import judge_correlation  # noqa: E402
import judge_ledger  # noqa: E402
import manifest  # noqa: E402
import policy_classify  # noqa: E402
import store  # noqa: E402
import strategy  # noqa: E402
from boards import load_board  # noqa: E402
from lbcore import (LBP, MODELS, SCENARIOS, SOLVED, newest_input, sh, slug,  # noqa: E402
                    models_for, loop_input_name, judge_path as core_judge_path,
                    transcript_path as core_transcript_path, PAIRS_SEED, PAIR_STATUS)

# board comes from $HERMES_BOARD (default: lucky-break-payday)
BOARD = load_board()
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
    p = (WORK / "artifacts" / PAIRS_SEED) if PAIRS_SEED else None
    if p and p.exists():
        try:
            board = (json.loads(p.read_text(encoding="utf-8")) or {}).get("pairs", {}) or {}
        except Exception:
            board = {}
    for sid in SCENARIOS:
        for model in models_for(sid):
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


def load_parked() -> set:
    """Pairs our bookkeeping has parked (datasets/lbp/pair-status.json)."""
    if not PAIR_STATUS:
        return set()
    try:
        d = json.loads((WORK / PAIR_STATUS).read_text(encoding="utf-8"))
    except Exception:
        return set()
    parked = set()
    for k, v in (d.get("pairs") or {}).items():
        st = str((v or {}).get("status", "")).upper()
        if st in ("POLICY_BLOCKED", "UNSAFE_OBJECTIVE", "PARKED", "PARK"):
            parked.add(k)
    return parked


def pair_stats(conn) -> dict:
    """Normalised reward statistics per pair (mean + spread, never the maximum).

    v4: the selector used `best_score` (a running maximum), so one lucky probe
    could keep a pair at the top for hours.  The reward now comes from every
    rewarded attempt, whatever produced it (judge or the independent local
    validator).
    """
    out = {}
    for r in conn.execute(
            "SELECT pair_id, COUNT(*) AS n, AVG(reward) AS mean, AVG(reward*reward) AS m2,"
            " SUM(CASE WHEN reward>=0.5 THEN 1 ELSE 0 END) AS wins"
            " FROM attempts WHERE reward IS NOT NULL GROUP BY pair_id"):
        n = int(r["n"] or 0)
        mean = float(r["mean"] or 0.0)
        var = max(0.0, float(r["m2"] or 0.0) - mean * mean)
        out[r["pair_id"]] = {"n": n, "mean": mean, "var": var, "sd": math.sqrt(var),
                             "wins": int(r["wins"] or 0)}
    return out


def pick_pair(conn, rng: random.Random, engine):
    # board-scoped: a shared DB may seed several boards (board_profile column);
    # pairs without a base probe cannot be variant-generated yet — keep them out of
    # the selection so the loop never spins on "no base input" (added 2026-11-13)
    rows = conn.execute(
        "SELECT id,best_score,attempts FROM pairs WHERE solved=0 AND best_input IS NOT NULL "
        "AND board_profile=?", (BOARD_NAME,)).fetchall()
    parked = load_parked()
    ids = [r["id"] for r in rows if r["id"] not in parked]
    if not ids:
        return None
    stats = pair_stats(conn)
    known = {k: v for k, v in stats.items() if k in ids}
    return engine.scheduler.choose(ids, known, rng=rng)


def delta_stats(conn, key: str) -> dict:
    """Per-delta statistics of a pair, normalised to [0, 1]."""
    out = {}
    for r in conn.execute("SELECT delta,n,sum_score FROM deltas WHERE pair_id=?", (key,)):
        n = int(r["n"] or 0)
        if n:
            mean = float(r["sum_score"] or 0) / n / 100.0
            out[r["delta"]] = {"n": n, "mean": mean, "sd": 0.0, "var": 0.0,
                               "wins": 1 if mean >= 0.5 else 0}
    return out


def catalog_exhausted(conn, key: str) -> bool:
    """True when every fixed delta of the pair has been probed at least once."""
    seen = {r["delta"] for r in conn.execute(
        "SELECT delta FROM deltas WHERE pair_id=? AND n>0", (key,))}
    return bool(generation.DELTAS) and all(d in seen for d in generation.DELTAS)


def generator_observations(conn, history_rows=None, limit: int = 4000) -> list[dict]:
    """(context, spec, reward) rows for the component model.

    Two sources: the live v4 attempts (reward column) and the historical repeats
    ledger, so a fresh run starts from everything the workspace already knows.
    """
    out = []
    for r in conn.execute(
            "SELECT pair_id, delta, reward FROM attempts WHERE reward IS NOT NULL"
            " ORDER BY started_at DESC LIMIT ?", (int(limit),)):
        spec = frames.decompose(r["delta"])
        if spec:
            out.append({"context": f"{BOARD_NAME}|{r['pair_id']}", "spec": spec,
                        "reward": float(r["reward"])})
    if history_rows is not None:
        for row in history_rows:
            spec = frames.decompose(row.get("arm"))
            if spec:
                out.append({"context": row["context"], "spec": spec,
                            "reward": row["reward"]})
    return out


def load_repeats_observations(limit: int = 4000) -> list[dict]:
    """Historical probe ledger -> (context, arm, reward); used to seed the model."""
    path = WORK / "datasets" / "lbp" / "repeats.jsonl"
    if not path.is_file():
        return []
    out = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]
    except OSError:
        return []
    import strategy_bench
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        arm = strategy_bench.delta_of_input(row.get("input"))
        if not arm:
            continue
        reward, _ = strategy.local_reward(row)
        if reward is None:
            continue
        out.append({"context": f"{BOARD_NAME}|{row.get('scenario')}|{row.get('model')}",
                    "arm": arm, "reward": reward})
    return out


def make_generated_variant(conn, lease, key: str, rng: random.Random, model_rows: list):
    """Compose a NEW frame for a pair whose fixed catalog has nothing new to offer.

    Honest framing: the component model is fitted on real rewards, but the
    offline benchmark could NOT confirm that component effects transfer to
    unseen combinations (Spearman ≈ 0 on held-out components, see
    reports/strategy-engine-v2-2026-11-13.md).  So the model is used only as a
    weak prior for ORDERING, and the actual pick is random among the top
    proposals — pure exploration where the fixed catalog is exhausted, with the
    reward recorded exactly like any other arm, so the bandit can learn which
    generated frames survive.
    """
    row = conn.execute("SELECT scenario,model FROM pairs WHERE id=?", (key,)).fetchone()
    if not row:
        return None
    sid, model = row["scenario"], row["model"]
    base_text, base_path = base_of(conn, key)
    if base_text is None:
        return None
    cmodel = candidate.ComponentModel().fit(model_rows)
    got = candidate.propose(cmodel, context=f"{BOARD_NAME}|{sid}|{model}", scenario=sid,
                            k=6, seen=spec_seen(conn, key))
    if not got:
        return None
    pick = rng.choice(got)                       # exploration, not exploitation
    spec = tuple(pick["spec"])
    arm = frames.spec_id(spec)
    nonce = f"{time.strftime('%Y%m%d-%H%M%S')}-{rng.randint(1000, 9999)}"
    text = frames.compose(spec, base_text, nonce)
    out = WORK / "inputs" / loop_input_name(sid, arm, int(time.time()), rng.randint(100, 999))
    out.write_text(text, encoding="utf-8")
    attempt_id = attempts.allocate(conn, lease, pair_id=key, board=BOARD_NAME,
                                   scenario=sid, model=model, lane=lease.lane)
    attempts.prepare(conn, lease, attempt_id, input_text=text,
                     input_path=str(out.relative_to(WORK)),
                     parent_input_hash=attempts.sha256_text(base_text),
                     parent_input_path=rel_or_abs(base_path),
                     delta=arm, delta_version=generation.DELTA_VERSION,
                     seed=None, nonce=nonce, strategy_version=4)
    log(f"GENERATED {attempt_id} spec={arm} p_win={pick['p_win']} "
        f"conf={pick['confidence']} (component model: weak prior, exploratory pick)")
    return attempt_id, arm, str(out.relative_to(WORK)), sid, model


def rel_or_abs(path) -> str:
    """Workspace-relative path when possible; absolute otherwise.

    A pair's base pointer may legitimately live outside the workspace (imported
    fixtures, tests): silently raising there used to kill the probe.
    """
    try:
        return str(pathlib.Path(path).relative_to(WORK))
    except ValueError:
        return str(path)


def base_of(conn, key: str):
    """The read-only search base of a pair: (text, path) or (None, None).

    v4: `best_input` is read-only here.  The old code promoted the newest input
    file to the base whenever it was 60s fresher, which silently replaced the
    best confirmed probe with an arbitrary later one (defect #2).
    """
    row = conn.execute("SELECT scenario,model,best_input FROM pairs WHERE id=?", (key,)).fetchone()
    if not row:
        return None, None
    sid, model, best = row["scenario"], row["model"], row["best_input"]
    base = (WORK / best) if best else None
    if base is None or not base.is_file():
        base = newest_input(sid, model)
        if base is None or not base.is_file():
            return None, None
        log(f"BASE fallback for {key}: best_input missing -> {base.name}")
    return base.read_text(encoding="utf-8", errors="replace"), base


def spec_seen(conn, key: str) -> set:
    """Already-probed generated frames of a pair (never propose one twice)."""
    return {r["delta"] for r in conn.execute(
        "SELECT delta FROM deltas WHERE pair_id=? AND n>0", (key,))
        if frames.parse_spec(r["delta"])}


def make_variant(conn, lease, key: str, rng: random.Random, engine, strategy_policy: str):
    row = conn.execute("SELECT scenario,model FROM pairs WHERE id=?", (key,)).fetchone()
    if not row:
        return None
    sid, model = row["scenario"], row["model"]
    base_text, base = base_of(conn, key)
    if base_text is None:
        return None
    arms = list(generation.DELTAS)
    if not arms:
        log(f"no delta catalog for board {BOARD_NAME}; cannot generate a variant")
        return None
    stats = delta_stats(conn, key)
    pooled = None
    novelty = None
    if strategy_policy == "contextual_ts":
        pooled = {}
        for r in conn.execute(
                "SELECT delta, SUM(n) AS n, SUM(sum_score) AS s FROM deltas d"
                " JOIN pairs p ON p.id=d.pair_id"
                " WHERE p.scenario=? AND p.board_profile=? GROUP BY delta",
                (sid, BOARD_NAME)):
            n = int(r["n"] or 0)
            if n:
                mean = float(r["s"] or 0) / n / 100.0
                pooled[r["delta"]] = {"n": n, "mean": mean, "sd": 0.0, "var": 0.0,
                                      "wins": 1 if mean >= 0.5 else 0}
        novelty = {a: engine.generator.novelty(a) for a in arms}
    delta = engine.scheduler.choose(arms, stats, rng=rng, pooled_stats=pooled, novelty=novelty)
    nonce = f"{time.strftime('%Y%m%d-%H%M%S')}-{rng.randint(1000, 9999)}"
    text = generation.generate(base_text, delta, nonce)
    out = WORK / "inputs" / loop_input_name(sid, delta, int(time.time()), rng.randint(100, 999))
    out.write_text(text, encoding="utf-8")
    attempt_id = attempts.allocate(
        conn, lease, pair_id=key, board=BOARD_NAME, scenario=sid, model=model,
        lane=lease.lane)
    attempts.prepare(
        conn, lease, attempt_id, input_text=text,
        input_path=str(out.relative_to(WORK)),
        parent_input_hash=attempts.sha256_text(base_text),
        parent_input_path=rel_or_abs(base),
        delta=delta, delta_version=generation.DELTA_VERSION,
        seed=None, nonce=nonce, strategy_version=3)
    return attempt_id, delta, str(out.relative_to(WORK)), sid, model


def energy_now(target: str = "") -> int:
    cmd = [sys.executable, str(LBP), "state"]
    if target:
        cmd += ["--target", target]
    rc, out, err = sh(cmd, timeout=90)
    try:
        d = json.loads(out)
        e = d.get("energy")
        # Unreadable energy (e.g. Proving Ground's page shows no "Energy N of M")
        # must mean "unknown" (-1: the gate is skipped), NOT zero (which would
        # fence the loop forever).  2026-11-13.
        if not isinstance(e, dict) or e.get("current") is None:
            return -1
        return int(e["current"])
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
    return core_judge_path(sid, model)


def transcript_path(key: str) -> pathlib.Path:
    sid, model = key.split("|")
    return core_transcript_path(sid, model)


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


def local_signals(attempt_id: str, input_path: str = "") -> dict:
    """The probe's own run record (local signals) from the repeats ledger.

    `lbp.py repeat` writes one JSON row per probe, tagged with the `opid` the
    driver passed (the attempt id) — that is how a live attempt is joined to its
    local validator evidence without touching the browser again.
    """
    path = WORK / "datasets" / "lbp" / "repeats.jsonl"
    if not path.is_file():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    tail = lines[-40:]
    best = {}
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if attempt_id and row.get("opid") == attempt_id:
            best = row
        elif input_path and str(row.get("input") or "").endswith(
                pathlib.Path(input_path).name):
            best = row
    return best


def apply_verdict(conn, lease, attempt_id: str, key: str, sid: str, model: str,
                  delta: str, result: dict, signals: dict, engine, log_prefix: str = ""):
    """Persist the outcome of an attempt and feed the strategy engine.

    Three cases, and the difference matters:
      * a VERIFIED judge        -> finalize, reward = judge (composite with local)
      * a judge that is pending -> await it (never resubmit)
      * no judge for THIS attempt -> `unjudged`, reward = independent local
        validator.  Before v4 this third case was a terminal `judge_failed`,
        which threw away every reward and blinded the selector.
    """
    status = result.get("status")
    if status == "pending":
        attempts.mark_awaiting(conn, lease, attempt_id, judge_ref=result.get("judge_ref"))
        log(f"{log_prefix}JUDGE pending {attempt_id}: {result.get('reason')}")
        return {"outcome": "pending"}
    if status == "verified":
        attempts.mark_judge(conn, lease, attempt_id, result)
        solved = result.get("verdict") in ("accepted", "solved")
        attempts.finalize(conn, lease, attempt_id, solved=solved)
        ev = engine.observe(context=strategy.context_key(board=BOARD_NAME, scenario=sid, model=model),
                            arm=delta, signals=signals, judge=result, scenario=sid, model=model,
                            board=BOARD_NAME, lineage=attempt_id)
        store.set_reward(conn, lease, attempt_id, ev["reward"], ev["source"])
        store.bump_delta(conn, lease, key, delta, ev["reward"])
        log(f"{log_prefix}RESULT {attempt_id} verdict={result.get('verdict')} "
            f"score={result.get('score')} solved={solved} reward={ev['reward']} ({ev['source']})")
        return {"outcome": "verified", "solved": solved, "reward": ev["reward"]}
    # no verdict attributable to this attempt
    ev = engine.observe(context=strategy.context_key(board=BOARD_NAME, scenario=sid, model=model),
                        arm=delta, signals=signals, judge=None, scenario=sid, model=model,
                        board=BOARD_NAME, lineage=attempt_id)
    attempts.mark_unjudged(conn, lease, attempt_id,
                           reason=f"{status}: {result.get('reason')}")
    store.set_reward(conn, lease, attempt_id, ev["reward"], ev["source"])
    store.bump_delta(conn, lease, key, delta, ev["reward"])
    log(f"{log_prefix}UNJUDGED {attempt_id} judge={status} "
        f"({result.get('reason')}) local_reward={ev['reward']} ({ev['source']})")
    return {"outcome": "unjudged", "reward": ev["reward"]}


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
    ap.add_argument("--strategy", default=os.environ.get("HERMES_STRATEGY", "ucb_improved"),
                    choices=strategy.POLICIES,
                    help="adaptive-search policy (see strategy_bench.py for the evidence)")
    ap.add_argument("--generate", default=os.environ.get("HERMES_GENERATE", "exhausted"),
                    choices=("off", "exhausted", "always"),
                    help="compose NEW frames (frames.py/candidate.py): off | only when the "
                         "fixed catalog of a pair is exhausted | always")
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
    man = manifest.load()
    if man:
        errs, warns = manifest.validate_split(man, board_name=BOARD_NAME, lane=a.lane,
                                              cdp=os.environ.get("HACKATHON_CDP_URL", ""))
        for w in warns:
            log(f"MANIFEST WARNING {w} (board profile edited after the manifest; "
                f"the supervisor re-baselines on the next driver start)")
        if errs:
            log(f"MANIFEST MISMATCH {errs}; fail closed (RULES 67)")
            return 2
        log(f"MANIFEST ok run_id={man.get('run_id')}")
    else:
        log("MANIFEST missing (supervisor writes it); continuing for this run")
    log(f"DRIVER START lane={a.lane} target={target} pid={os.getpid()} db={a.db} "
        f"board={BOARD_NAME} profile={PROFILE_HASH}")
    recovered = attempts.recover(conn, lease)
    if recovered:
        log(f"RECOVERED {len(recovered)} in-progress attempts: {recovered}")

    # v4: the strategy engine (standalone; see harness/strategy.py)
    engine = strategy.StrategyEngine(list(generation.DELTAS), policy=a.strategy, seed=a.seed)
    # v5: the candidate generator (frames.py + candidate.py).  Its component
    # model is fitted once from everything the workspace knows; the loop only
    # consults it where the fixed catalog has nothing new to offer.
    gen_rows = generator_observations(conn, load_repeats_observations()) \
        if a.generate != "off" else []
    if a.generate != "off":
        log(f"GENERATOR on ({a.generate}); component model fitted on {len(gen_rows)} "
            f"observations; space={len(frames.catalog())} frames")
    try:
        late = judge_ledger.reconcile_unjudged(conn, lease)
        if late:
            log(f"LATE VERDICTS {len(late)}: {late}")
    except Exception as exc:  # noqa: BLE001
        log(f"RECONCILE failed ({type(exc).__name__}: {exc}); continuing")

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
            key = pick_pair(conn, rng, engine)
            if not key:
                total = conn.execute(
                    "SELECT COUNT(*) AS c FROM pairs WHERE board_profile=?",
                    (BOARD_NAME,)).fetchone()["c"]
                log(f"all {total} pairs solved — nothing left")
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
            mv = None
            if a.generate != "off" and (a.generate == "always" or catalog_exhausted(conn, key)):
                try:
                    mv = make_generated_variant(conn, lease, key, rng, gen_rows)
                except Exception as exc:  # noqa: BLE001
                    log(f"GENERATE failed ({type(exc).__name__}: {exc}); falling back to the catalog")
                    mv = None
            if not mv:
                mv = make_variant(conn, lease, key, rng, engine, a.strategy)
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
                # v4 judge attribution: only the ledger entry for THIS operation
                # counts.  The per-pair judge file is shared by every attempt of
                # the pair, so reading it blindly attributed a previous attempt's
                # verdict to this one (104/114 live attempts, defect #1).
                pair_judge = judge_path(key)
                ledger_judge = judge_ledger.path_for(attempt_id)
                foreign = judge_ledger.is_foreign(pair_judge, attempt_id)
                if ledger_judge is None and foreign:
                    log(f"JUDGE foreign {attempt_id}: {pair_judge.name} belongs to "
                        f"{judge_ledger.operation_id_of(pair_judge)}")
                jpath = ledger_judge or (None if foreign else
                                         (pair_judge if pair_judge.is_file() else None))
                ev = evidence.capture(attempt_id, key=key, input_path=input_path,
                                      delta=delta, lane=a.lane,
                                      transcript_path=transcript_path(key),
                                      judge_path=jpath)
                attempt_row = store.get_attempt(conn, attempt_id)
                result = judge_correlation.correlate(
                    attempt_row, jpath, transcript_text=text,
                    known_operations=store.known_judge_operations(conn))
                signals = local_signals(attempt_id, input_path)
                if not signals:
                    log(f"WARN {attempt_id}: no run record in the repeats ledger; "
                        f"the local validator cannot score this probe")
                apply_verdict(conn, lease, attempt_id, key, sid, model, delta,
                              result, signals, engine)
                if result.get("status") == "verified":
                    try:
                        log(f"CAUSE {attempt_id}: {policy_classify.summarize(text)}")
                    except Exception:
                        pass
                evidence.finish(attempt_id, judge_result=result,
                                evaluation={"score": result.get("score"),
                                            "pcts": result.get("pcts"),
                                            "verdict": result.get("verdict"),
                                            "status": result.get("status"),
                                            "reward": store.get_attempt(conn, attempt_id)["reward"]})
            store.heartbeat(conn, lease)
            stats = conn.execute(
                "SELECT SUM(CASE WHEN solved=1 THEN 1 ELSE 0 END) AS s, COUNT(*) AS c "
                "FROM pairs WHERE board_profile=?", (BOARD_NAME,)).fetchone()
            log(f"BOARD {int(stats['s'] or 0)}/{int(stats['c'] or 0)}")
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
    # A lease hiccup or an unexpected error in verdict bookkeeping used to kill
    # the driver silently (2.5 h stall on 2026-11-13: store.LeaseLost escaped
    # from apply_verdict). Log and exit with a code the supervisor understands.
    try:
        sys.exit(main())
    except store.LeaseLost as exc:
        log(f"FATAL lease lost: {exc}; exit rc=3")
        sys.exit(3)
    except Exception as exc:  # noqa: BLE001
        log(f"FATAL {type(exc).__name__}: {exc}")
        sys.exit(1)
