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
import online_learning  # noqa: E402
import policy_classify  # noqa: E402
import store  # noqa: E402
import strategy  # noqa: E402
from boards import load_board  # noqa: E402
from arena import get_adapter  # noqa: E402
from lbcore import (LBP, MODELS, SCENARIOS, SOLVED, newest_input, sh, slug,  # noqa: E402
                    models_for, loop_input_name, judge_path as core_judge_path,
                    transcript_path as core_transcript_path, PAIRS_SEED, PAIR_STATUS)

# board comes from $HERMES_BOARD (default: lucky-break-payday)
BOARD = load_board()
BOARD_NAME = BOARD["name"]
PROFILE_HASH = BOARD["_profile_hash"]
# The arena seam: everything platform-specific the loop needs goes through this
# adapter (harness/arena.py).  A second arena = one adapter + one board profile,
# not an edit to the loop.
PLATFORM = get_adapter(BOARD)


def log(msg: str) -> None:
    """Append one line to the lane log.

    `HERMES_DRIVER_LOG` redirects it: the offline test suite imports this module
    and would otherwise write its synthetic attempts (":test:" ids) into the
    operational log the lane watchdog and the operator read.
    """
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        path = os.environ.get("HERMES_DRIVER_LOG") or str(WORK / "artifacts" / "driver.log")
        with open(path, "a", encoding="utf-8") as f:
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
            # Never a flag without an attempt (task 2026-11-15, item 4): the seed
            # file's `solved` and SOLVED's seed truth both claimed pairs solved that have
            # no accepted+verified attempt in this database (12 pairs Payday, 5 Proving
            # Ground).  `recompute_solved` sets the flag from the attempts themselves.
            solved = 0
            best = b.get("best_input") or PLATFORM.newest_input(sid, model)
            if best:
                best = str(best)  # the protocol says path-like (str or Path)
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


def recompute_solved(conn) -> dict:
    """`pairs.solved` follows the ATTEMPTS, not the bookkeeping (task 2026-11-15, item 4).

    `solved=1` only where some attempt of the pair carries `judge_status='verified'` AND a
    verdict of `accepted`/`solved`.  Every other flag is cleared, and each change is written
    to `events` with the reason, so a pair that loses its flag can be traced to the attempt
    that never existed.  Local reward, the judge file's name and a seed flag are all NOT
    evidence of a solve.
    """
    changed: list = []
    solved_now = 0
    for r in conn.execute(
            "SELECT p.id AS id, p.solved AS flag,"
            " (SELECT COUNT(*) FROM attempts a WHERE a.pair_id=p.id"
            "   AND a.judge_status='verified' AND a.verdict IN ('accepted','solved')) AS hits"
            " FROM pairs p"):
        want = 1 if int(r["hits"] or 0) > 0 else 0
        solved_now += want
        if int(r["flag"] or 0) != want:
            conn.execute("UPDATE pairs SET solved=? WHERE id=?", (want, r["id"]))
            changed.append({"pair": r["id"], "from": int(r["flag"] or 0), "to": want,
                            "verified_accepted": int(r["hits"] or 0)})
    for c in changed:
        store.event(conn, "solved_recomputed", c)
        log(f"SOLVED {c['pair']}: {c['from']} -> {c['to']} "
            f"(verified accepted/solved attempts: {c['verified_accepted']})")
    conn.commit()
    return {"changed": changed, "solved": solved_now}


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


def pair_recent(conn, ids, window_s: float, now: float | None = None) -> dict:
    """per-pair (last probe time, attempts inside the window)."""
    now = now or time.time()
    out = {k: {"last": 0.0, "n": 0} for k in ids}
    for r in conn.execute(
            "SELECT pair_id, MAX(started_at) AS last, COUNT(*) AS n FROM attempts"
            " WHERE started_at > ? GROUP BY pair_id", (now - window_s,)):
        if r["pair_id"] in out:
            out[r["pair_id"]] = {"last": float(r["last"] or 0.0), "n": int(r["n"] or 0)}
    # a pair never probed in the window may still have older attempts
    for r in conn.execute(
            "SELECT pair_id, MAX(started_at) AS last FROM attempts GROUP BY pair_id"):
        if r["pair_id"] in out and not out[r["pair_id"]]["last"]:
            out[r["pair_id"]]["last"] = float(r["last"] or 0.0)
    return out


GIVE_UP = {"window_hours": 12.0, "min_probes": 20, "max_reward": 0.02,
           "park_hours": 6.0, "state": "artifacts/give-up.json"}


def _give_up_load() -> dict:
    try:
        return json.loads((WORK / GIVE_UP["state"]).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _give_up_save(state: dict) -> None:
    path = WORK / GIVE_UP["state"]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001 — bookkeeping must never stop the lane
        log(f"give-up: cannot persist state ({type(exc).__name__}: {exc})")


def _give_up_pairs(conn, ids: list, now: float) -> set:
    """Pairs parked by the give-up rule (advice #6), decided from a RECENT window.

    Pre-registered (RULES 92, written before the live data): a pair with at least
    `min_probes` probes inside the last `window_hours` and NOTHING the judge ever paid for
    has stopped moving, so it yields its slot for `park_hours`.

    Task 2026-11-15 (item 2): the decision reads the VERIFIED JUDGE, never the `reward`
    column.  "No movement" now means: no attempt in the window with
    `judge_status='verified'` and a score above zero.  The reward column carried the local
    surrogate (0.32 mean against the judge's 0.08), which sits almost always above the old
    0.02 threshold — so a pair with hundreds of judge zeros never yielded its slot
    (Negative-quantity: 921 attempts, best verified score 0).

    Two corrections paid for with data (2026-11-15, before enabling it live):
      * the first version asked about the LIFETIME best reward — every one of our
        pairs carries a best of 0.35-0.70 from days ago, so the rule could never
        fire, ever.  It has to look at a window, not at history;
      * the thresholds come from the measured pace: a pair here gets ~2 probes/hour
        (12 per 6 h, ~48 per day), so `min_probes=20` inside 12 h is a full day of
        that pair's share — long enough not to fire on noise, short enough to notice
        a patched mock.
    The park is SOFT: `pick_pair` ignores it when it would leave no candidate (the
    lane must never stall) and it EXPIRES by itself, so the pair is retested later.
    """
    if not ids:
        return set()
    state = _give_up_load()
    parked = {k for k, v in state.items()
              if float((v or {}).get("until", 0)) > now}
    since = now - GIVE_UP["window_hours"] * 3600.0
    for k in ids:
        if k in parked:
            continue
        row = conn.execute(
            "SELECT COUNT(*) AS n,"
            " SUM(CASE WHEN judge_status='verified' AND COALESCE(score, 0) > 0"
            "          THEN 1 ELSE 0 END) AS paid"
            " FROM attempts WHERE pair_id=? AND COALESCE(started_at, 0) >= ?",
            (k, since)).fetchone()
        if not row or int(row["n"] or 0) < GIVE_UP["min_probes"]:
            continue
        if int(row["paid"] or 0) > 0:
            continue
        state[k] = {"until": now + GIVE_UP["park_hours"] * 3600.0,
                    "parked_at": now, "probes": int(row["n"]),
                    "verified_paid": int(row["paid"] or 0),
                    "window_hours": GIVE_UP["window_hours"],
                    "reason": (f"{row['n']} probes in the last "
                               f"{GIVE_UP['window_hours']:g}h, none with a verified "
                               f"judge score above zero")}
        parked.add(k)
        log(f"GIVE-UP park {k}: {state[k]['reason']}; free again in "
            f"{GIVE_UP['park_hours']:.0f}h")
    if state:
        state = {k: v for k, v in state.items()
                 if float((v or {}).get("until", 0)) > now - 86400}
        _give_up_save(state)
    return parked


def pick_pair(conn, rng: random.Random, *, cooldown_s: float = 900.0,
              window_s: float = 21600.0):
    """Choose the next pair by COVERAGE, not by the local proxy reward.

    Measured defect (2026-11-13 ~21:50): ranking pairs by the mean local reward
    sent 131 of 133 probes into two cells (`negq|YK`, `negq|DW`) — the local
    validator scores a tool call ~0.5 there, so the bandit believed those pairs
    were the best and starved the other six unsolved pairs.  The local reward is
    a fair comparison *between deltas of one pair*; it is NOT comparable across
    pairs, where only a judge verdict means "solved".  So the bandit now decides
    the DELTA inside the chosen pair, and the pair itself is chosen by coverage.

    Priority: pairs not probed within `cooldown_s` first, least recently probed
    first; then the fewest attempts inside the window; ties break on the
    judge-verified score, and finally at random.
    """
    rows = conn.execute(
        "SELECT id,best_score,attempts FROM pairs WHERE solved=0 AND best_input IS NOT NULL "
        "AND board_profile=?", (BOARD_NAME,)).fetchall()
    parked = load_parked()
    ids = [r["id"] for r in rows if r["id"] not in parked]
    if not ids:
        return None
    now = time.time()
    recent = pair_recent(conn, ids, window_s, now)
    verified = {r["pair_id"]: float(r["mean"] or 0.0) for r in conn.execute(
        "SELECT pair_id, AVG(score) AS mean FROM attempts"
        " WHERE judge_status='verified' AND score IS NOT NULL GROUP BY pair_id")}
    cooled = [k for k in ids if now - recent[k]["last"] >= cooldown_s]
    pool = cooled or ids
    if not cooled:
        # every unsolved pair is inside the cooldown: fall back to the least
        # recently probed one, so the loop can never lock onto a single cell
        pool = sorted(ids, key=lambda k: recent[k]["last"])[:max(1, len(ids) // 3)]
    # Give-up rule (advice #6, pre-registered in RULES 92): a pair that has shown no
    # movement in `min_probes` probes yields its slot for a few hours.  SOFT on both
    # ends: it never removes the last candidate (the lane must not stall) and the
    # park expires by itself.
    given_up = _give_up_pairs(conn, pool, now)
    trimmed = [k for k in pool if k not in given_up]
    if trimmed:
        pool = trimmed
    elif given_up:
        log(f"give-up: all {len(given_up)} candidates are parked; probing anyway")
    best = sorted(pool, key=lambda k: (recent[k]["n"], -verified.get(k, 0.0),
                                       recent[k]["last"], rng.random()))
    return best[0]


def _num(x: float):
    """Keep whole numbers integral (decay makes counts fractional).

    Rounding first matters: with a huge half-life the decay factor is 0.9999993,
    so a count of three comes out as 2.9999979 — a float that would leak into
    downstream code comparing counts to integers.
    """
    v = round(float(x), 4)
    return int(v) if float(v).is_integer() else v


def delta_stats(conn, key: str, half_life_probes: float | None = None) -> dict:
    """Per-delta statistics of a pair, normalised to [0, 1].

    v5: computed from `attempts.reward` — the judge-anchored, fault-excluded
    channel — instead of the legacy `deltas` aggregate.  That table mixed two
    scales (judge score SUMS 0..300 written before v4, normalised rewards 0..100
    written by bump_delta after), so 62 of its rows read as means up to 1.93 and
    the selector was comparing apples with oranges (found 2026-11-13).

    Falls back to the legacy aggregate only when the pair has no rewarded
    attempts at all (a fresh workspace), and says so in the log.

    `half_life_probes` (advice #7, per-policy default from strategy.py): with a
    half-life an observation ages by 0.5 ** (probes_since / half_life), so an arm
    that paid an hour ago outranks one that paid a day ago at the same rate.  The
    unit is PROBES, not hours: an idle night must not erase what the lane learned.
    """
    if half_life_probes is None:
        out: dict = {}
        for r in conn.execute(
                "SELECT delta, reward FROM attempts"
                " WHERE pair_id=? AND delta IS NOT NULL AND reward IS NOT NULL", (key,)):
            arm = r["delta"]
            bucket = out.setdefault(arm, {"n": 0, "sum": 0.0, "wins": 0, "sq": 0.0})
            value = float(r["reward"])
            bucket["n"] += 1
            bucket["sum"] += value
            bucket["sq"] += value * value
            if value >= 0.5:
                bucket["wins"] += 1
        if out:
            for arm, b in out.items():
                n = b["n"]
                mean = b["sum"] / n
                var = max(0.0, b["sq"] / n - mean * mean)
                out[arm] = {"n": n, "mean": round(mean, 4), "sd": round(math.sqrt(var), 4),
                            "var": round(var, 6), "wins": b["wins"]}
    else:
        accs: dict = {}
        step = 0
        for r in conn.execute(
                "SELECT delta, reward FROM attempts"
                " WHERE pair_id=? AND delta IS NOT NULL AND reward IS NOT NULL"
                " ORDER BY COALESCE(started_at, 0), attempt_id", (key,)):
            acc = accs.setdefault(r["delta"], strategy.ArmAcc())
            acc.add(step, float(r["reward"]), half_life_probes)
            step += 1
        out = {}
        for arm, acc in accs.items():
            s = acc.stats(step, half_life_probes)
            out[arm] = {"n": _num(s["n"]), "mean": round(s["mean"], 4),
                        "sd": round(s["sd"], 4), "var": round(s["var"], 6),
                        "wins": _num(s["wins"])}
    if out:
        return out
    legacy = {}
    for r in conn.execute("SELECT delta,n,sum_score FROM deltas WHERE pair_id=?", (key,)):
        n = int(r["n"] or 0)
        if n:
            mean = float(r["sum_score"] or 0) / n / 100.0
            legacy[r["delta"]] = {"n": n, "mean": mean, "sd": 0.0, "var": 0.0,
                                  "wins": 1 if mean >= 0.5 else 0}
    if legacy:
        log(f"delta_stats({key}): no rewarded attempts yet — using the legacy "
            f"aggregate for {len(legacy)} arms (mixed scale, pre-v4 only)")
    return legacy


def _pcts_of(raw) -> list:
    """Criterion percentages of an attempt row (the column stores JSON text)."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [float(x) for x in raw if isinstance(x, (int, float))]
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 — one broken cell must not hide the others
        return []
    return [float(x) for x in data if isinstance(x, (int, float))] if isinstance(data, list) else []


def blocking_criterion(conn, key: str) -> tuple | None:
    """(index, mean%, layout) of the criterion that blocks this pair — the one worth working on.

    Review 2026-11-15, cause #4: the search maximises the mean score, but a cell is solved
    only when EVERY criterion stands at 100%, so at [30, 100, 30, 100, 20] the only useful
    target is the criterion at 20 — lifting the three that already pass buys nothing.
    Per-criterion means come from the verified attempts' `pcts`; the blocking one is the
    lowest, ties broken by the earlier index so the choice is stable across runs.

    Vectors of different lengths are NOT mixed: index i would stand for different criteria in
    different probes (this journal holds both 3- and 6-entry vectors of the same cell), so
    only the modal layout decides, and the disagreement is reported in `layout.layouts`.
    None when the pair has no verified attempt carrying a pct vector at all.
    """
    sums: dict = {}
    lengths: dict = {}
    for r in conn.execute(
            "SELECT pcts FROM attempts WHERE pair_id=? AND judge_status='verified'"
            " AND pcts IS NOT NULL", (key,)):
        pcts = _pcts_of(r["pcts"])
        if pcts:
            lengths[len(pcts)] = lengths.get(len(pcts), 0) + 1
    if not lengths:
        return None
    # Criterion VECTORS of different lengths (3 vs 6 entries on the same cell in this
    # journal) would make index-wise means mix different criteria, so only the modal layout
    # decides the blocking index.  The disagreement is returned, not hidden.
    modal = max(lengths, key=lambda n: (lengths[n], n))
    for r in conn.execute(
            "SELECT pcts FROM attempts WHERE pair_id=? AND judge_status='verified'"
            " AND pcts IS NOT NULL", (key,)):
        pcts = _pcts_of(r["pcts"])
        if len(pcts) != modal:
            continue
        for i, p in enumerate(pcts):
            acc = sums.setdefault(i, [0.0, 0])
            acc[0] += p
            acc[1] += 1
    means = {i: acc[0] / acc[1] for i, acc in sums.items() if acc[1]}
    if not means:
        return None
    worst = min(means, key=lambda i: (means[i], i))
    return worst, round(means[worst], 1), {"layout": modal, "layouts": lengths}


def verified_delta_stats(conn, key: str, focus: int | None = None) -> dict:
    """Per-delta statistics from the VERIFIED JUDGE alone (task 2026-11-15, item 3).

    "Выбор среди старых дельт — по среднему проверенному счёту": the arm chosen inside a
    pair must be ranked by what the JUDGE paid, not by the local proxy — and not by the
    composite either, which still carries 10% of the surrogate.  A delta with no verified
    observation simply does not appear, so it cannot enter any mean.

    `focus` (review 2026-11-15, cause #4): with a known BLOCKING criterion the arms are
    ranked by THAT criterion's percentage instead of the overall mean.  An observation whose
    pct vector does not carry the index falls back to its own criterion mean — the same
    scale — and only a row with no vector at all uses score/100.

    Why the criterion mean and not `score/100`: on a multi-criterion cell `score` is the SUM
    (260, 280 in this journal), so dividing it by 100 saturates every probe at 1.0 and the
    "mean" stops telling arms apart (found by the focus test, 2026-11-15).  The mean over the
    probe's own criteria is the number the task asked for and is comparable across probes.

    Score is normalised to [0, 1] by /100 — the same rule `strategy.judge_reward` uses for
    a bare score, and the same scale the legacy aggregate used before v4.
    """
    out: dict = {}
    for r in conn.execute(
            "SELECT delta, score, pcts FROM attempts"
            " WHERE pair_id=? AND delta IS NOT NULL AND judge_status='verified'"
            " AND score IS NOT NULL ORDER BY COALESCE(started_at, 0), attempt_id", (key,)):
        b = out.setdefault(r["delta"], {"n": 0, "sum": 0.0, "sq": 0.0, "wins": 0})
        pcts = _pcts_of(r["pcts"])
        value = None
        if focus is not None and len(pcts) > focus:
            value = max(0.0, min(1.0, pcts[focus] / 100.0))
        elif pcts:
            value = max(0.0, min(1.0, sum(pcts) / (100.0 * len(pcts))))
        if value is None:
            value = max(0.0, min(1.0, float(r["score"]) / 100.0))
        b["n"] += 1
        b["sum"] += value
        b["sq"] += value * value
        if value >= 0.5:
            b["wins"] += 1
    for arm, b in out.items():
        n = b["n"]
        mean = b["sum"] / n
        var = max(0.0, b["sq"] / n - mean * mean)
        out[arm] = {"n": n, "mean": round(mean, 4), "sd": round(math.sqrt(var), 4),
                    "var": round(var, 6), "wins": b["wins"]}
    return out


MIN_VERIFIED_FOR_NEW_DELTA = 2


def verified_count(conn, key: str) -> int:
    """Verified judges this pair has.  The gate for PROPOSING a delta nobody tried."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM attempts"
        " WHERE pair_id=? AND judge_status='verified'", (key,)).fetchone()
    return int(row["n"] or 0)


def probed_deltas(conn, key: str) -> list:
    """Deltas of this pair that were already sent (order of first probe)."""
    seen: list = []
    for r in conn.execute(
            "SELECT delta, MIN(COALESCE(started_at, 0)) AS first FROM attempts"
            " WHERE pair_id=? AND delta IS NOT NULL GROUP BY delta ORDER BY first",
            (key,)):
        seen.append(r["delta"])
    return seen


def choosable_arms(conn, key: str, catalog: list, log_fn=None) -> tuple:
    """(arms, stats_source) for a pair — the ONE place the new-delta gate lives.

    Task 2026-11-15, item 3: do not propose a delta nobody has tried until the pair has
    `MIN_VERIFIED_FOR_NEW_DELTA` verified judges; choose among the already-probed deltas by
    their mean VERIFIED score.  A pair that has never been probed is allowed its catalogue:
    the gate exists to stop expanding the catalogue under a silent judge, not to stall a
    fresh pair (RULES: the lane must never stall).
    """
    probed = probed_deltas(conn, key)
    verified = verified_delta_stats(conn, key)
    if not probed:
        return list(catalog), "catalog (fresh pair: first probe)"
    if verified_count(conn, key) < MIN_VERIFIED_FOR_NEW_DELTA:
        arms = [a for a in probed]
        if log_fn:
            log_fn("DELTA GATE %s: %d verified judge(s) < %d — staying inside the %d "
                   "already-probed delta(s), no new one"
                   % (key, verified_count(conn, key), MIN_VERIFIED_FOR_NEW_DELTA, len(arms)))
        return arms, "probed (gate)"
    if verified:
        return list(catalog), "verified means"
    if log_fn:
        log_fn("DELTA GATE %s: %d verified judges but none with a score — staying inside "
               "the %d probed delta(s)"
               % (key, verified_count(conn, key), len(probed)))
    return [a for a in probed], "probed (no scored judge yet)"


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


_LIVE: dict = {}


def _live(conn, rows):
    """One LiveObservations per DB connection (watermark persisted on disk)."""
    key = id(conn)
    if key not in _LIVE:
        _LIVE[key] = online_learning.LiveObservations(conn, rows, board=BOARD_NAME)
    return _LIVE[key]


def make_generated_variant(conn, lease, key: str, rng: random.Random, model_rows: list,
                           target: str = ""):
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
    # Task 2026-11-15, item 3: a composed frame IS a new delta, so it waits for the same
    # two verified judges as any other catalogue expansion.  Under a silent judge the lane
    # keeps probing deltas that were already sent (choosable_arms); it does not invent more.
    if verified_count(conn, key) < MIN_VERIFIED_FOR_NEW_DELTA:
        log(f"GENERATED SKIP {key}: {verified_count(conn, key)} verified judge(s) < "
            f"{MIN_VERIFIED_FOR_NEW_DELTA} — no new delta until the judge has spoken twice")
        return None
    row = conn.execute("SELECT scenario,model FROM pairs WHERE id=?", (key,)).fetchone()
    if not row:
        return None
    sid, model = row["scenario"], row["model"]
    base_text, base_path = base_of(conn, key)
    if base_text is None:
        return None
    n_new = _live(conn, model_rows).pull()
    if n_new:
        log(f"ONLINE LEARN +{n_new} observations -> {len(model_rows)} total")
    cmodel = candidate.ComponentModel().fit(model_rows)
    got = candidate.propose(cmodel, context=f"{BOARD_NAME}|{sid}|{model}", scenario=sid,
                            k=6, seen=spec_seen(conn, key))
    if not got:
        return None
    pick = rng.choice(got)                       # exploration, not exploitation
    spec = tuple(pick["spec"])
    arm = frames.spec_id(spec)
    nonce = f"{time.strftime('%Y%m%d-%H%M%S')}-{rng.randint(1000, 9999)}"
    text = frames.compose(spec, base_text, nonce, profile_hash=PROFILE_HASH)
    out = WORK / "inputs" / PLATFORM.input_name(sid, arm, int(time.time()), rng.randint(100, 999))
    out.write_text(text, encoding="utf-8")
    attempt_id = attempts.allocate(conn, lease, pair_id=key, board=BOARD_NAME,
                                   scenario=sid, model=model, lane=lease.lane,
                                   profile_hash=PROFILE_HASH, models_hash=_models_hash(),
                                   target_id=str(target))
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
        base = PLATFORM.newest_input(sid, model)
        if base is None or not base.is_file():
            return None, None
        log(f"BASE fallback for {key}: best_input missing -> {base.name}")
    return base.read_text(encoding="utf-8", errors="replace"), base


def spec_seen(conn, key: str) -> set:
    """Already-probed generated frames of a pair (never propose one twice)."""
    return {r["delta"] for r in conn.execute(
        "SELECT delta FROM deltas WHERE pair_id=? AND n>0", (key,))
        if frames.parse_spec(r["delta"])}


def _bind_target(conn, lane: str, target: str) -> dict:
    """Каждая проба привязана к ОДНОМУ target на всю жизнь; смена — НОВАЯ привязка.

    Обзор Grok 2026-11-15 («транспорт», ось-10).  Пишем привязку в журнал при старте
    полосы: если id вкладки сменился, в журнале появляется `target_rebound` со старым и
    новым id — смена видна как событие, а не как молчаливое переиспользование.
    """
    import store  # noqa: PLC0415
    prev = store.last_event(conn, "target_binding")
    rec = {"lane": str(lane), "target": str(target), "pid": os.getpid(),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if prev and str(prev.get("target") or "") != str(target):
        rec["previous"] = prev.get("target")
        store.event(conn, "target_rebound", rec)
        store.event(conn, "target_binding", rec)
        log(f"TARGET REBOUND lane={lane} {prev.get('target')} -> {target} "
            f"(new binding recorded; an in-flight attempt never changes target)")
        return rec
    store.event(conn, "target_binding", rec)
    log(f"TARGET BOUND lane={lane} target={target} (one target per attempt, for life)")
    return rec


def _models_hash() -> str:
    """The model roster hash from the run manifest (empty when there is no manifest).

    Recorded with every attempt so a replay knows which roster produced the probe
    (Grok review 2026-11-15, axis "reproducibility").  The manifest is written by the
    supervisor; a driver started by hand may legitimately have none, and then the
    attempts say "unknown" instead of inventing a roster.
    """
    try:
        man = manifest.load() or {}
        return str(man.get("model_roster_hash") or "unknown")
    except Exception:  # noqa: BLE001 — provenance must never stop a probe
        return "unknown"


def _pooled_arm_stats(conn, sid: str | None, half_life_probes: float | None = None) -> dict:
    """Arm statistics from the authoritative reward channel (attempts.reward).

    `sid` = one scenario (the arm's own task family); None = the whole board.  Both
    levels feed the parent chain in strategy.py (advice #5: pair -> scenario ->
    board -> global), so a scenario with two probes cannot outvote a board with
    two hundred.
    """
    sql = ("SELECT a.delta AS delta, a.reward AS reward FROM attempts a"
           " JOIN pairs p ON p.id=a.pair_id"
           " WHERE p.board_profile=? AND a.reward IS NOT NULL AND a.delta IS NOT NULL")
    params: tuple = (BOARD_NAME,)
    if sid:
        sql += " AND p.scenario=?"
        params = (BOARD_NAME, sid)
    if half_life_probes is not None:
        sql += " ORDER BY COALESCE(a.started_at, 0), a.attempt_id"
        accs: dict = {}
        step = 0
        for r in conn.execute(sql, params):
            acc = accs.setdefault(r["delta"], strategy.ArmAcc())
            acc.add(step, float(r["reward"]), half_life_probes)
            step += 1
        out = {}
        for arm, acc in accs.items():
            s = acc.stats(step, half_life_probes)
            out[arm] = {"n": _num(s["n"]), "mean": round(s["mean"], 4),
                        "sd": round(s["sd"], 4), "var": round(s["var"], 6),
                        "wins": _num(s["wins"])}
        return out
    acc: dict = {}
    for r in conn.execute(sql, params):
        b = acc.setdefault(r["delta"], {"n": 0, "sum": 0.0, "wins": 0})
        b["n"] += 1
        b["sum"] += float(r["reward"])
        if float(r["reward"]) >= 0.5:
            b["wins"] += 1
    out = {}
    for arm, b in acc.items():
        n = b["n"]
        out[arm] = {"n": n, "mean": b["sum"] / n, "sd": 0.0, "var": 0.0,
                    "wins": b["wins"]}
    return out


def make_variant(conn, lease: str, key: str, rng: random.Random, engine, strategy_policy: str,
                 target: str = ""):
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
    hl = strategy.half_life_probes(strategy_policy)
    # The gate and the ranking of item 3 live in ONE place (choosable_arms): how many
    # deltas may compete, and by whose numbers.  The verified channel is the teacher when
    # it exists; the local/reward channel survives only as the documented fallback.
    arms, stats_source = choosable_arms(conn, key, arms, log)
    # Review 2026-11-15, cause #4: rank the arms by the criterion that BLOCKS the solve, not
    # by the mean — a cell needs every criterion at 100%, so lifting three that already pass
    # buys nothing (giftcard YK sat at [30, 100, 30, 100, 20]).
    focus = blocking_criterion(conn, key)
    verified = verified_delta_stats(conn, key, focus=focus[0] if focus else None)
    stats = verified or delta_stats(conn, key, hl)
    if focus and verified:
        log(f"CRITERION FOCUS {key}: criterion #{focus[0]} (mean {focus[1]}%) blocks the solve "
            f"— arms ranked by it, not by the mean score")
    if not verified:
        log(f"delta choice for {key}: no verified judge score yet — falling back to the "
            f"reward channel ({stats_source})")
    pooled = None
    board_stats = None
    novelty = None
    if strategy_policy == "contextual_ts":
        # Pooled statistics come from the same authoritative channel as delta_stats
        # (attempts.reward), never from the legacy mixed-scale aggregate.  Two levels
        # are built here: the scenario (the arm's own task family) and the board
        # (everything else this board ever tried) — the chain in strategy.py mixes
        # them by observation count.
        pooled = _pooled_arm_stats(conn, sid, hl)
        board_stats = _pooled_arm_stats(conn, None, hl)
        novelty = {a: engine.generator.novelty(a) for a in arms}
    delta = engine.scheduler.choose(arms, stats, rng=rng, pooled_stats=pooled,
                                    novelty=novelty, board_stats=board_stats)
    nonce = f"{time.strftime('%Y%m%d-%H%M%S')}-{rng.randint(1000, 9999)}"
    text = generation.generate(base_text, delta, nonce, profile_hash=PROFILE_HASH)
    out = WORK / "inputs" / PLATFORM.input_name(sid, delta, int(time.time()), rng.randint(100, 999))
    out.write_text(text, encoding="utf-8")
    attempt_id = attempts.allocate(
        conn, lease, pair_id=key, board=BOARD_NAME, scenario=sid, model=model,
        lane=lease.lane, profile_hash=PROFILE_HASH, models_hash=_models_hash(),
        target_id=str(target))
    attempts.prepare(
        conn, lease, attempt_id, input_text=text,
        input_path=str(out.relative_to(WORK)),
        parent_input_hash=attempts.sha256_text(base_text),
        parent_input_path=rel_or_abs(base),
        delta=delta, delta_version=generation.DELTA_VERSION,
        seed=None, nonce=nonce, strategy_version=3)
    return attempt_id, delta, str(out.relative_to(WORK)), sid, model


def energy_now(target: str = "") -> int:
    """Platform energy (or -1 = unknown: the gate is skipped, never fenced)."""
    return PLATFORM.energy(target)


def run_attempt_v2(target: str, key: str, input_path: str, wait_s: int,
                   attempt_id: str):
    """Send one probe through the platform adapter; returns the (rc, out, err)
    tuple the loop has always used."""
    r = PLATFORM.probe(target, key, input_path, wait_s, attempt_id)
    return r.rc, r.out, r.err


def judge_path(key: str) -> pathlib.Path:
    return PLATFORM.judge_artifact(key)


def transcript_path(key: str) -> pathlib.Path:
    return PLATFORM.transcript(key)[0]


def transcript_info(key: str):
    _path, text, chat = PLATFORM.transcript(key)
    return text, chat


def local_signals(attempt_id: str, input_path: str = "") -> dict:
    """The probe's own run record (local signals), via the arena adapter.

    Bound to the operation id (fallback: the input-file basename).  Reading a
    per-unit shared record would attribute the previous probe's evidence to this
    one — the channel defect this workspace rebuilt around.
    """
    return PLATFORM.signals(attempt_id, input_path)


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
    # Immutability of a finished attempt (Grok review 2026-11-15, axis "judge
    # reconciliation": 8/10).  The judge ARTIFACT is a cache: it can be rewritten by a
    # later attempt, a re-render or a manual edit, and a rewrite is NOT evidence.  The
    # binding recorded WITH the attempt is.  So once an attempt is terminal, nothing —
    # not even a fresher, better verdict for the same operation id — may change it.
    row = store.get_attempt(conn, attempt_id)
    if row and str(row["state"]) in ("finalized", "execution_failed",
                                     "submission_uncertain", "judge_failed", "cancelled"):
        # `attempts` has no `solved` column (that lives on `pairs`): a finalized attempt
        # is the proof of a solve, everything else terminal is not.
        log(f"{log_prefix}IMMUTABLE {attempt_id}: state={row['state']} "
            f"verdict={row['judge_status']} reward={row['reward']} kept; "
            f"ignoring a fresh judge result (status={status})")
        return {"outcome": "immutable", "reward": row["reward"],
                "solved": str(row["state"]) == "finalized"}
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
    # No verdict attributable to this attempt.  The attempt stays `unjudged` and a LATE
    # judge can still claim it (judge_ledger.reconcile_unjudged), but there is NO teaching
    # signal: `evaluate` returns reward=None/source="missing" and the local validator stays
    # a diagnostic.  Teaching the selector from the surrogate here is what made it optimise
    # the tool-call proxy on 87% of the data (task 2026-11-15): calling a tool pays 0.70 and
    # `check_ready` pays 0.80, while the judge pays 0.00-0.04 on the same attempts.
    ev = engine.observe(context=strategy.context_key(board=BOARD_NAME, scenario=sid, model=model),
                        arm=delta, signals=signals, judge=None, scenario=sid, model=model,
                        board=BOARD_NAME, lineage=attempt_id)
    attempts.mark_unjudged(conn, lease, attempt_id,
                           reason=f"{status}: {result.get('reason')}")
    store.set_reward(conn, lease, attempt_id, ev["reward"], ev["source"])
    if ev["reward"] is not None:  # belt and braces: bump_delta refuses None as well
        store.bump_delta(conn, lease, key, delta, ev["reward"])
    log(f"{log_prefix}UNJUDGED {attempt_id} judge={status} ({result.get('reason')}) "
        f"teacher=missing local_diagnostic={ev['local_reward']} "
        f"(this attempt teaches the selector nothing)")
    return {"outcome": "unjudged", "reward": None}


def lane_flags() -> dict:
    """Persisted per-lane flag defaults: `artifacts/lane-flags.json`.

    Why a file and not an env var: the lane is auto-restarted (watchdog,
    supervisor, operator), and an env var exported once is forgotten by the next
    restart — a live experiment would silently stop collecting its control arm.
    Precedence stays CLI > env > this file > built-in default.
    """
    path = WORK / "artifacts" / "lane-flags.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log(f"WARN lane-flags.json unreadable; ignoring it ({path})")
        return {}
    return data if isinstance(data, dict) else {}


def flag_default(name: str, env_key: str, hard, flags: dict):
    """CLI > env > lane-flags.json > hard default."""
    env = os.environ.get(env_key)
    if env is not None:
        return env
    if name in flags:
        return flags[name]
    return hard


def main(argv=None) -> int:
    flags = lane_flags()
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
    ap.add_argument("--strategy",
                    default=flag_default("strategy", "HERMES_STRATEGY",
                                         "contextual_ts", flags),
                    choices=strategy.POLICIES,
                    help="adaptive-search policy.  Default contextual_ts: measured on the "
                         "corrected reward channel (harness/reward_audit.py; our own dropped "
                         "probes no longer count as model refusals) it leads on mean reward, "
                         "success rate AND good-arm rate at budgets 100/300/1000, 21 seeds, "
                         "non-overlapping CI vs ucb_improved (0.2326/0.2222/0.355 against "
                         "0.1603/0.1700/0.250).  On the OLD channel ucb_improved won — the "
                         "channel was what changed, not the task: see "
                         "harness/strategy_bench.py --reward-map v1|faults|v2")
    ap.add_argument("--generate", default=flag_default("generate", "HERMES_GENERATE",
                                                      "exhausted", flags),
                    choices=("off", "exhausted", "always"),
                    help="compose NEW frames (frames.py/candidate.py): off | only when the "
                         "fixed catalog of a pair is exhausted | always")
    ap.add_argument("--ab-generate", type=float,
                    default=float(flag_default("ab_generate", "HERMES_AB_GENERATE", "1.0",
                                               flags)),
                    help="randomized control for the generator (0..1): the probability that a "
                         "would-be generation step actually composes a new frame; otherwise the "
                         "probe re-runs the best catalog delta (control). 1.0 = always generate "
                         "(the pre-experiment behaviour). Both branches cost one probe, so the "
                         "ledger measures which one buys more reward — the offline bench cannot "
                         "answer this, a brand-new frame has no reward by construction.")
    ap.add_argument("--pair-cooldown", type=float,
                    default=float(os.environ.get("HERMES_PAIR_COOLDOWN", "900")),
                    help="seconds before an unsolved pair may be probed again (coverage "
                         "scheduling; prevents the loop from locking onto one cell)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    conn = store.connect(a.db)
    seed(conn)
    # Task 2026-11-15, item 4: the solve flag follows the attempts, and this runs on every
    # driver start so a flag seeded from bookkeeping (or re-added by hand) is cleared the
    # next time the lane comes up.  The reason for each change lands in `events`.
    recompute_solved(conn)
    store.insert_board_profile(conn, BOARD, PROFILE_HASH)
    target = a.target
    if not target:
        rc, out, err = sh([sys.executable, str(WORK / "harness" / "pick_target.py")], timeout=30)
        target = (out or "").strip()
        if not target and (err or "").strip():
            # "no tab" vs "ambiguous: 2 tabs" — the operator must be able to tell the
            # difference in the log (Grok review 2026-11-15: an empty target with two
            # tabs is an attempt error, not a guess).
            log(f"pick_target: {(err or '').strip()[:160]}")
    if not target:
        # An adapter can declare that it needs no browser (the offline sandbox:
        # harness/arena_fake.py).  Every other arena keeps the loud refusal, so a
        # missing browser is still a hard error rather than a silent no-op.
        if getattr(PLATFORM, "NEEDS_BROWSER", True):
            log("no target (pick_target empty); is the lane browser up?")
            return 3
        target = "no-browser"
        log(f"target not required by platform {PLATFORM.name()!r}; using {target!r}")

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
    try:
        _bind_target(store.connect(a.db), a.lane, target)
    except Exception as exc:  # noqa: BLE001 — привязка не должна ронять полосу
        log(f"target binding not recorded ({type(exc).__name__}: {exc})")
    log(f"DRIVER START lane={a.lane} target={target} pid={os.getpid()} db={a.db} "
        f"board={BOARD_NAME} profile={PROFILE_HASH}")
    log(f"FLAGS strategy={a.strategy} generate={a.generate} ab_generate={a.ab_generate} "
        f"pair_cooldown={a.pair_cooldown:.0f}s "
        f"decay_half_life={strategy.half_life_probes(a.strategy) or 'off'}probes"
        + (" [from lane-flags.json]" if flags.get("ab_generate") is not None else ""))
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
            key = pick_pair(conn, rng, cooldown_s=a.pair_cooldown)
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
            arm_source = "catalog"
            if a.generate != "off" and (a.generate == "always" or catalog_exhausted(conn, key)):
                # Randomized control (hermes ab-generate): composing a new frame
                # and re-probing the best catalog delta cost the same one probe,
                # so the coin flip decides, and the tag lets the ledger compare
                # them later.  Without it "generation pays off" stays an opinion.
                if a.ab_generate >= 1.0 or rng.random() < a.ab_generate:
                    try:
                        mv = make_generated_variant(conn, lease, key, rng, gen_rows, target)
                        arm_source = "generated"
                    except Exception as exc:  # noqa: BLE001
                        log(f"GENERATE failed ({type(exc).__name__}: {exc}); falling back to the catalog")
                        mv = None
                else:
                    arm_source = "control_repeat"
                    log(f"AB-CONTROL {key}: coin says re-probe the best catalog delta "
                        f"instead of composing a new frame")
            if not mv:
                mv = make_variant(conn, lease, key, rng, engine, a.strategy, target)
            if not mv:
                log(f"no base input for {key}; sleep 30")
                time.sleep(30)
                continue
            attempt_id, delta, input_path, sid, model = mv
            try:
                store.set_arm_source(conn, lease, attempt_id, arm_source)
            except Exception as exc:  # noqa: BLE001 — tagging must never kill a probe
                log(f"WARN {attempt_id}: arm_source tag failed ({type(exc).__name__}: {exc})")
            log(f"ATTEMPT {attempt_id} {key} delta={delta} src={arm_source} "
                f"input={input_path} energy={en}")
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
