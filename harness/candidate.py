#!/usr/bin/env python3
"""Candidate generator: propose a NEW frame instead of picking a known delta.

`strategy.py` narrows the choice inside a fixed catalog; this module produces
frames the catalog does not contain, from the component space in `frames.py`,
scored by what the component statistics of the SAME context have taught
(plus pooled evidence from sibling models when the context is young).

    ComponentModel.fit(observations)      # (context, spec, reward) rows
    ComponentModel.p_win(context, spec)   # log-odds additive, smoothed
    propose(scenario, context, k, seen)   # diverse, unseen, objective-matched

Scoring is additive in log-odds with per-field shrinkage:

    logit p = Σ_field (n_f / (n_f + k)) · logit(p_field)
    p_field = (wins + α·p_pooled) / (n + α)

so a component seen twice does not outvote one seen two hundred times, and a
context with no history leans on the pooled estimate rather than on nothing.

Diversity: after ranking, proposals are re-ranked with a penalty on components
already used inside the same proposal set (a greedy maximal-marginal-relevance
step), so the top-k is not k variations of one carrier.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import frames  # noqa: E402

SPEC_FIELDS = ("carrier", "delivery", "claim")
WIN = 0.5


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


class ComponentModel:
    """P(win) of a composed frame, from component statistics of real probes."""

    def __init__(self, *, alpha: float = 2.0, field_weight: float = 1.0):
        self.alpha = float(alpha)
        self.field_weight = float(field_weight)
        self.n = defaultdict(int)          # (field, value) -> probes
        self.wins = defaultdict(int)       # (field, value) -> wins
        self.ctx_n = defaultdict(int)      # (context, field, value) -> probes
        self.ctx_wins = defaultdict(int)
        self.total = 0
        self.total_wins = 0
        self.fitted_contexts = set()

    # -- fitting ---------------------------------------------------------
    def fit(self, observations) -> "ComponentModel":
        for row in observations:
            spec = row.get("spec")
            if not spec:
                continue
            ctx = row["context"]
            reward = row.get("reward")
            if reward is None:
                continue
            win = 1 if float(reward) >= WIN else 0
            self.total += 1
            self.total_wins += win
            self.fitted_contexts.add(ctx)
            for field, value in zip(SPEC_FIELDS, spec):
                self.n[(field, value)] += 1
                self.wins[(field, value)] += win
                self.ctx_n[(ctx, field, value)] += 1
                self.ctx_wins[(ctx, field, value)] += win
        return self

    # -- estimation ------------------------------------------------------
    def p_pooled(self, field: str, value: str) -> float:
        # Laplace-smoothed base rate: with a single observation the prior must
        # not become 1.0 (an early probe with reward 0.8 used to make every
        # unseen component look like a guaranteed win).
        base = (self.total_wins + 1.0) / (self.total + 2.0) if self.total else 0.1
        n, w = self.n[(field, value)], self.wins[(field, value)]
        return (w + self.alpha * base) / (n + self.alpha)

    def p_field(self, ctx: str, field: str, value: str) -> float:
        pooled = self.p_pooled(field, value)
        n, w = self.ctx_n[(ctx, field, value)], self.ctx_wins[(ctx, field, value)]
        if not n and not self.n[(field, value)]:
            return pooled
        return (w + self.alpha * pooled) / (n + self.alpha)

    def confidence(self, ctx: str, field: str, value: str) -> float:
        n = self.ctx_n[(ctx, field, value)]
        return n / (n + self.alpha) if ctx in self.fitted_contexts else 0.0

    def p_win(self, ctx: str, spec) -> float:
        total = 0.0
        weight = 0.0
        for field, value in zip(SPEC_FIELDS, spec):
            w = 0.5 + self.field_weight * self.confidence(ctx, field, value)
            total += w * _logit(self.p_field(ctx, field, value))
            weight += w
        if not weight:
            return self.total_wins / self.total if self.total else 0.1
        return _sigmoid(total / weight)

    # -- diagnostics -----------------------------------------------------
    def component_table(self, ctx: str | None = None) -> dict:
        out = {}
        for field in SPEC_FIELDS:
            rows = []
            values = {v for f, v in self.n if f == field} | \
                     {v for c, f, v in self.ctx_n if f == field and (ctx is None or c == ctx)}
            for value in sorted(values):
                rows.append({
                    "value": value,
                    "n": self.ctx_n[(ctx, field, value)] if ctx else self.n[(field, value)],
                    "p": round(self.p_field(ctx, field, value) if ctx
                               else self.p_pooled(field, value), 4),
                })
            out[field] = sorted(rows, key=lambda r: -r["p"])
        return out


def propose(model: ComponentModel, *, context: str, scenario: str, k: int = 5,
            seen=None, novelty_weight: float = 0.25) -> list[dict]:
    """Top-k unseen, objective-matched specs with a diversity penalty."""
    seen = set(seen or ())
    specs = [s for s in frames.catalog_for_scenario(scenario) if frames.spec_id(s) not in seen]
    if not specs:
        return []
    scored = []
    for spec in specs:
        p = model.p_win(context, spec)
        conf = sum(model.confidence(context, f, v) for f, v in zip(SPEC_FIELDS, spec)) / 3.0
        scored.append({"spec": spec, "id": frames.spec_id(spec), "p_win": round(p, 4),
                       "confidence": round(conf, 3),
                       "delta": frames.delta_of_spec(spec)})
    scored.sort(key=lambda r: (-r["p_win"], r["id"]))
    # greedy MMR: prefer a candidate whose components are not yet in the set
    picked: list[dict] = []
    while len(picked) < k and scored:
        best, best_score = None, None
        for cand in scored:
            overlap = 0.0
            for field, value in zip(SPEC_FIELDS, cand["spec"]):
                overlap += sum(1 for p in picked
                               if value == dict(zip(SPEC_FIELDS, p["spec"]))[field])
            rank = cand["p_win"] * (1 - novelty_weight + novelty_weight / (1.0 + overlap))
            if best_score is None or rank > best_score:
                best, best_score = cand, rank
        if best is None:  # unreachable with a non-empty list; keeps the types honest
            break
        scored.remove(best)
        picked.append(best)
    return picked


def _selftest() -> int:
    ok = True
    rows = [
        {"context": "c1", "spec": ("authority", "prose_post", "keep_verbatim"), "reward": 0.8},
        {"context": "c1", "spec": ("authority", "prose_post", "keep_verbatim"), "reward": 0.7},
        {"context": "c1", "spec": ("legal", "json", "preservation"), "reward": 0.05},
        {"context": "c1", "spec": ("legal", "json", "preservation"), "reward": 0.05},
        {"context": "c2", "spec": ("authority", "table", "keep_verbatim"), "reward": 0.9},
        {"context": "c2", "spec": ("legal", "yaml", "preservation"), "reward": 0.0},
    ]
    m = ComponentModel().fit(rows)
    good = ("authority", "prose_post", "keep_verbatim")
    bad = ("legal", "json", "preservation")
    if not (m.p_win("c1", good) > m.p_win("c1", bad)):
        ok = False
        print("FAIL model does not prefer the winning frame")
    # pooling: an unseen context must still inherit the component evidence
    if m.p_win("brand-new", good) <= m.p_win("brand-new", bad):
        ok = False
        print("FAIL pooling does not transfer to a new context")
    # novelty: a seen spec is never proposed again
    got = propose(m, context="c1", scenario="negative-quantity-exploit", k=4,
                  seen={frames.spec_id(good)})
    if any(r["id"] == frames.spec_id(good) for r in got):
        ok = False
        print("FAIL proposed a spec that was already tried")
    if len({r["id"] for r in got}) != len(got):
        ok = False
        print("FAIL duplicate proposals")
    # diversity: the top-k must not be k variations of one carrier
    if len(got) >= 3 and len({r["spec"][0] for r in got[:3]}) == 1:
        ok = False
        print("FAIL no diversity in the top-3")
    # objective match: a refund scenario must not get pricing frames
    refund = propose(m, context="c1", scenario="double-refund", k=8)
    if any(r["spec"][2] in ("pricing_terms", "delivery_terms") for r in refund):
        ok = False
        print("FAIL objective mismatch")
    print(json.dumps([r["id"] for r in got], ensure_ascii=False))
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fit", action="store_true", help="fit from strategy-memory.db")
    ap.add_argument("--context")
    ap.add_argument("--scenario", default="negative-quantity-exploit")
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    import strategy
    mem = strategy.ExperienceMemory()
    rows = [{"context": r["context"], "spec": frames.decompose(r["arm"]),
             "reward": r["reward"]} for r in mem.rows() if frames.decompose(r["arm"])]
    model = ComponentModel().fit(rows)
    print(json.dumps({"fitted_on": len(rows), "contexts": len(model.fitted_contexts),
                      "components": {f: len({v for ff, v in model.n if ff == f})
                                     for f in SPEC_FIELDS}}, ensure_ascii=False, indent=2))
    if a.context:
        got = propose(model, context=a.context, scenario=a.scenario, k=a.k)
        print(json.dumps(got, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
