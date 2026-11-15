#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вторая волна правок задачи «перестать учиться у суррогата» (2026-11-15)."""
import pathlib
import sys

W = pathlib.Path(__file__).resolve().parent.parent

def edit(path, pairs, label):
    p = W / path
    t = p.read_text(encoding="utf-8")
    n = 0
    for old, new in pairs:
        if old not in t:
            print("  !! НЕ НАЙДЕНО в %s: %r" % (path, old[:70]))
            continue
        t = t.replace(old, new, 1)
        n += 1
    p.write_text(t, encoding="utf-8")
    print("%s: применено %d/%d" % (label, n, len(pairs)))
    return n == len(pairs)

ok = True

# ---------- 5. verified-канал: новые дельты только после двух проверенных ----------
NEW_FUNCS = '''
def verified_delta_stats(conn, key: str) -> dict:
    """Per-delta statistics from the VERIFIED JUDGE alone (task 2026-11-15, item 3).

    "Выбор среди старых дельт — по среднему проверенному счёту": the arm chosen inside a
    pair must be ranked by what the JUDGE paid, not by the local proxy — and not by the
    composite either, which still carries 10% of the surrogate.  A delta with no verified
    observation simply does not appear, so it cannot enter any mean.

    Score is normalised to [0, 1] by /100 — the same rule `strategy.judge_reward` uses for
    a bare score, and the same scale the legacy aggregate used before v4.
    """
    out: dict = {}
    for r in conn.execute(
            "SELECT delta, score FROM attempts"
            " WHERE pair_id=? AND delta IS NOT NULL AND judge_status='verified'"
            " AND score IS NOT NULL ORDER BY COALESCE(started_at, 0), attempt_id", (key,)):
        b = out.setdefault(r["delta"], {"n": 0, "sum": 0.0, "sq": 0.0, "wins": 0})
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


'''
ok &= edit("harness/driver.py", [(
    "def catalog_exhausted(conn, key: str) -> bool:",
    NEW_FUNCS.lstrip("\n") + "def catalog_exhausted(conn, key: str) -> bool:"
)], "5a. verified-канал")

# make_variant: выбор через choosable_arms
ok &= edit("harness/driver.py", [(
    """    hl = strategy.half_life_probes(strategy_policy)
    stats = delta_stats(conn, key, hl)
    pooled = None""",
    """    hl = strategy.half_life_probes(strategy_policy)
    # The gate and the ranking of item 3 live in ONE place (choosable_arms): how many
    # deltas may compete, and by whose numbers.  The verified channel is the teacher when
    # it exists; the local/reward channel survives only as the documented fallback.
    arms, stats_source = choosable_arms(conn, key, arms, log)
    verified = verified_delta_stats(conn, key)
    stats = verified or delta_stats(conn, key, hl)
    if not verified:
        log(f"delta choice for {key}: no verified judge score yet — falling back to the "
            f"reward channel ({stats_source})")
    pooled = None"""
)], "5b. make_variant: выбор")

# make_generated_variant: новая кадровая дельта — тоже новая дельта
ok &= edit("harness/driver.py", [(
    """def make_generated_variant(conn, lease: str, key: str, rng: random.Random, model_rows: list,""",
    """def make_generated_variant(conn, lease: str, key: str, rng: random.Random, model_rows: list,"""
)], "5c. (проверка сигнатуры)")

# ---------- 6. solved из попыток ----------
ok &= edit("harness/driver.py", [(
    """            solved = 1 if (b.get("solved") or model in SOLVED.get(sid, set())) else 0""",
    """            # Never a flag without an attempt (task 2026-11-15, item 4): the seed
            # file's `solved` and SOLVED's seed truth both claimed pairs solved that have
            # no accepted+verified attempt in this database (12 pairs Payday, 5 Proving
            # Ground).  `recompute_solved` sets the flag from the attempts themselves.
            solved = 0"""
)], "6a. seed: solved из попыток")

ok &= edit("harness/driver.py", [(
    "def load_parked() -> set:",
    '''def recompute_solved(conn) -> dict:
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


def load_parked() -> set:'''
)], "6b. recompute_solved")

import ast
ast.parse((W / "harness" / "driver.py").read_text(encoding="utf-8"))
print("синтаксис driver.py OK")
sys.exit(0 if ok else 1)
