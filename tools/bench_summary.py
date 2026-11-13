#!/usr/bin/env python3
"""Compact strategy_bench summary -> stdout (for reports)."""
import json
import pathlib

p = pathlib.Path(__file__).resolve().parent.parent / "artifacts" / "strategy-bench.json"
d = json.loads(p.read_text(encoding="utf-8"))


def num(x):
    if isinstance(x, dict):
        return x.get("mean")
    return x


print("== data ==")
print(" ", d.get("data"))
print("== protocol ==")
pr = d.get("protocol") or {}
for k in ("budget", "seeds", "train_split", "reward", "budget_sweep"):
    print(f"  {k}: {pr.get(k)}")
print(f"  arms pinned: {len(pr.get('arms') or [])}")

print("\n== aggregate per policy (budget %s) ==" % pr.get("budget"))
for name, v in (d.get("policies") or {}).items():
    if not isinstance(v, dict):
        continue
    print(f"  {name:14s} mean={num(v.get('mean_reward'))} succ={num(v.get('success_rate'))} "
          f"good_arm={num(v.get('good_arm_rate'))} cov_arms={v.get('coverage_arms')} "
          f"cov_fam={v.get('coverage_families')} ci_w={num(v.get('ci_width'))} "
          f"regret={num(v.get('regret'))}")

print("\n== sweep (mean_reward per policy) ==")
for b, entry in (d.get("sweep") or {}).items():
    if isinstance(entry, dict):
        line = "  ".join(f"{k}:{num(val)}" for k, val in entry.items())
    else:
        line = str(entry)[:200]
    print(f"  budget={b}: {line}")

print("\n== prior tune ==")
tune = d.get("tune") or {}
print("  policy:", tune.get("policy") or tune.get("policies"))
for k, v in (tune.get("by_prior_k") or {}).items():
    print(f"  prior_k={k}: {v}")
print("  best:", tune.get("best"))