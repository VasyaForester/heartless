#!/usr/bin/env python3
"""Does the generator actually generalise?  Offline evidence, honestly framed.

Three questions, all answerable from the 1870 real probes:

1. COVERAGE — how much of the composition space was ever tried?  (The argument
   for generation: the catalog explores a vanishing fraction of its own space.)

2. HELD-OUT COMPONENTS — fit the component model on a train split with whole
   component values REMOVED (e.g. everything delivered as json/yaml/table, or
   every pricing claim), then ask whether it still ranks the held-out specs
   correctly.  Rank correlation (Spearman) between predicted P(win) and the
   mean reward those specs really earned.  Baselines: a constant predictor
   (no information) and a "tried-most" predictor (frequency, no reward).

3. SEARCH SIMULATION — the generator proposes top-k frames per context; the
   proposals that reproduce a catalog frame are paid that frame's real
   observed reward.  Compare cumulative reward against random-over-36 and the
   v4 bandit (strategy.AdaptiveScheduler) on the same held-out probes.
   Match rate is reported: the generator mostly proposes frames that were
   NEVER tried, and those cannot be scored offline — that is the honest limit
   of this measurement, and why the live driver records them.

Usage: python3 harness/generator_bench.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import statistics
import sys
import time
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import candidate  # noqa: E402
import frames  # noqa: E402
import strategy  # noqa: E402
from strategy import AdaptiveScheduler  # noqa: E402

REPEATS = WORK / "datasets" / "lbp" / "repeats.jsonl"
OUT_JSON = WORK / "artifacts" / "generator-bench.json"

HOLDOUT_GROUPS = {
    "deliveries": (("delivery", ("json", "yaml", "table", "markup", "aria")),),
    "claims": (("claim", ("pricing_terms", "delivery_terms", "escrow_terms",
                          "balance_proof", "preservation")),),
    "carriers": (("carrier", ("legal", "bounty", "incident", "quote", "counterparty")),),
}


def load_observations(path=REPEATS):
    """Real probes -> (context, spec, reward) using the component decomposition."""
    import strategy_bench
    rows = []
    p = pathlib.Path(path)
    if not p.is_file():
        return rows
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
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
        spec = frames.decompose(arm)
        if not spec:
            continue
        reward, _ = strategy.local_reward(row)
        if reward is None:
            continue
        rows.append({"context": f"{row.get('scenario')}|{row.get('model')}",
                     "scenario": row.get("scenario"), "arm": arm, "spec": spec,
                     "reward": reward, "ts": row.get("ts")})
    return rows


def _rank(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys) -> float | None:
    if len(xs) < 3:
        return None
    rx, ry = _rank(xs), _rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 4) if den else None


def coverage(rows, budget_arms: int | None = None) -> dict:
    specs = {r["spec"] for r in rows}
    space = len(frames.catalog())
    return {"probes": len(rows), "specs_tried": len(specs),
            "space": space, "coverage_pct": round(100.0 * len(specs) / space, 3)}


def heldout_test(rows, group: str, *, split: float = 0.5, seed: int = 11) -> dict:
    """Fit without a whole set of component values; rank the held-out specs."""
    field, values = HOLDOUT_GROUPS[group][0]
    idx = {"carrier": 0, "delivery": 1, "claim": 2}[field]
    held_specs = {s for s in frames.catalog() if s[idx] in values}
    by_ctx = defaultdict(list)
    for r in rows:
        by_ctx[r["context"]].append(r)
    train, test = [], []
    for ctx, items in by_ctx.items():
        items = sorted(items, key=lambda r: str(r.get("ts") or ""))
        cut = max(1, int(len(items) * split))
        train += [r for r in items[:cut] if r["spec"] not in held_specs]
        test += [r for r in items[cut:] if r["spec"] in held_specs]
    model = candidate.ComponentModel().fit(train)
    if not test:
        return {"group": group, "skipped": "no held-out probes in the test half"}
    # observed mean reward per (context, held-out spec)
    agg = defaultdict(list)
    for r in test:
        agg[(r["context"], r["spec"])].append(r["reward"])
    pairs = [(ctx, spec, statistics.fmean(v)) for (ctx, spec), v in agg.items() if len(v) >= 1]
    preds = [model.p_win(ctx, spec) for ctx, spec, _ in pairs]
    actual = [mean for _, _, mean in pairs]
    freq = []
    for ctx, spec, _ in pairs:
        f = 0
        for fld, val in zip(candidate.SPEC_FIELDS, spec):
            f += model.n[(fld, val)]
        freq.append(f)
    return {
        "group": group, "field": field, "holdout_values": list(values),
        "train_probes": len(train), "test_probes": len(test), "pairs": len(pairs),
        "spearman_model": spearman(preds, actual),
        "spearman_frequency_baseline": spearman(freq, actual),
        "obs_mean_reward": round(statistics.fmean(actual), 4) if actual else None,
    }


def search_simulation(rows, *, k: int = 5, split: float = 0.7, seeds: int = 5,
                      rounds: int = 8) -> dict:
    """Generator top-k vs random vs the v4 bandit, paid with real held-out rewards."""
    by_ctx = defaultdict(list)
    for r in rows:
        by_ctx[r["context"]].append(r)
    train, pay = [], defaultdict(list)
    for ctx, items in by_ctx.items():
        items = sorted(items, key=lambda r: str(r.get("ts") or ""))
        cut = max(1, int(len(items) * split))
        train += items[:cut]
        for r in items[cut:]:
            pay[(ctx, r["arm"])].append(r["reward"])
    payoff = {key: statistics.fmean(v) for key, v in pay.items()}
    train_by_ctx = defaultdict(list)
    for r in train:
        train_by_ctx[r["context"]].append(r)

    contexts = sorted({r["context"] for r in train} & {c for c, _ in pay})
    out = {"contexts": len(contexts), "mapped_proposals": 0, "proposals": 0,
           "generator": 0.0, "generator_on_mapped_pulls": 0.0, "random": 0.0,
           "random_same_pulls": 0.0, "bandit": 0.0, "per_context": []}
    if not contexts:
        return out
    rng = random.Random(1234)
    gen_total = rnd_total = band_total = 0.0
    gen_scored = rnd_scored = 0.0
    gen_scored_n = 0
    for ctx in contexts:
        scenario = ctx.split("|")[0]
        model = candidate.ComponentModel().fit(train_by_ctx[ctx])
        seen = {frames.spec_id(r["spec"]) for r in train_by_ctx[ctx]}
        got = propose_mapped(model, ctx, scenario, k=k, rounds=rounds, seen=seen)
        out["proposals"] += len(got["all"])
        out["mapped_proposals"] += len(got["mapped"])
        gen_rew = sum(payoff.get((ctx, d), 0.0) for d in got["mapped"])
        # baselines on the same contexts / rounds
        arms = sorted(frames.CATALOG_SPECS)
        rnd_rew = 0.0
        for _ in range(rounds * k):          # same pull budget as the generator list
            rnd_rew += payoff.get((ctx, rng.choice(arms)), 0.0)
        # apples-to-apples: only the pulls that CAN be scored offline (the
        # proposals reproducing a catalog frame) against the same number of
        # random pulls over the same arms
        rnd_same = 0.0
        for _ in range(len(got["mapped"])):
            rnd_same += payoff.get((ctx, rng.choice(arms)), 0.0)
        stats = {}
        for r in train_by_ctx[ctx]:
            s = stats.setdefault(r["arm"], {"n": 0, "sum": 0.0, "sumsq": 0.0,
                                            "wins": 0, "var": 0.0, "sd": 0.0, "mean": 0.0})
            s["n"] += 1
            s["sum"] += r["reward"]
            if r["reward"] >= 0.5:
                s["wins"] += 1
        for s in stats.values():
            s["mean"] = s["sum"] / s["n"]
        sch = AdaptiveScheduler("ucb_improved", seed=7)
        band_rew = 0.0
        open_arms = list(stats)
        if open_arms:
            for _ in range(rounds * k):
                arm = sch.choose(open_arms, stats, rng=rng)
                band_rew += payoff.get((ctx, arm), 0.0)
        gen_total += gen_rew
        rnd_total += rnd_rew
        band_total += band_rew
        gen_scored += gen_rew
        rnd_scored += rnd_same
        gen_scored_n += len(got["mapped"])
        out["per_context"].append({"context": ctx, "generator": round(gen_rew, 3),
                                   "random": round(rnd_rew, 3), "bandit": round(band_rew, 3),
                                   "mapped": len(got["mapped"])})
    out["generator"] = round(gen_total, 3)
    out["random"] = round(rnd_total, 3)
    out["bandit"] = round(band_total, 3)
    out["generator_on_mapped_pulls"] = (round(gen_scored / gen_scored_n, 4)
                                        if gen_scored_n else None)
    out["random_same_pulls"] = (round(rnd_scored / gen_scored_n, 4)
                               if gen_scored_n else None)
    out["scored_pulls"] = gen_scored_n
    out["match_rate"] = round(out["mapped_proposals"] / max(1, out["proposals"]), 3)
    return out


def propose_mapped(model, ctx, scenario, *, k: int, rounds: int, seen) -> dict:
    """Proposals for `rounds` steps; keep the ids and their catalog analogues."""
    out = {"all": [], "mapped": [], "arm_of": {}}
    local_seen = set(seen)
    for _ in range(rounds):
        got = candidate.propose(model, context=ctx, scenario=scenario, k=k, seen=local_seen)
        if not got:
            break
        for item in got:
            out["all"].append(item["id"])
            local_seen.add(item["id"])
            if item["delta"]:
                out["mapped"].append(item["delta"])
                out["arm_of"][item["id"]] = item["delta"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=str(OUT_JSON))
    ap.add_argument("--history", default=str(REPEATS))
    a = ap.parse_args()
    rows = load_observations(a.history)
    if not rows:
        print(json.dumps({"error": "no observations", "path": a.history}))
        return 1
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "data": {"observations": len(rows),
                 "contexts": len({r["context"] for r in rows}),
                 "source": str(REPEATS.relative_to(WORK))},
        "coverage": coverage(rows),
        "heldout": [heldout_test(rows, g) for g in HOLDOUT_GROUPS],
        "search_simulation": search_simulation(rows),
    }
    pathlib.Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    c = report["coverage"]
    print(f"observations: {report['data']['observations']} over "
          f"{report['data']['contexts']} contexts")
    print(f"coverage: {c['specs_tried']} distinct component specs tried out of "
          f"{c['space']} ({c['coverage_pct']}% of the composition space)")
    print("\nheld-out components (Spearman between predicted P(win) and observed reward):")
    for h in report["heldout"]:
        if h.get("skipped"):
            print(f"  {h['group']:<12} skipped: {h['skipped']}")
            continue
        print(f"  {h['group']:<12} pairs={h['pairs']:<4} model={h['spearman_model']} "
              f"frequency-baseline={h['spearman_frequency_baseline']} "
              f"obs_mean={h['obs_mean_reward']}")
    s = report["search_simulation"]
    print(f"\nsearch simulation ({s['contexts']} contexts, "
          f"match_rate={s.get('match_rate')} of proposals map to a known arm):")
    print(f"  generator={s['generator']}  random={s['random']}  bandit={s['bandit']}")
    print(f"  scored pulls only ({s.get('scored_pulls')}): "
          f"generator={s.get('generator_on_mapped_pulls')} "
          f"vs random={s.get('random_same_pulls')}")
    print("  NOTE: an unmapped proposal is a frame that was never tried, so it has no "
          "offline reward — the generator cannot be scored on it here by construction.")
    print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
