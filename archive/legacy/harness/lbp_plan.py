#!/usr/bin/env python3
"""lbp_plan.py — дерево решений LBP: классификация задачи -> приоритет стратегий -> план прогона.

Читает ТОЛЬКО локальные файлы (никаких браузерных действий):
  datasets/lbp/decision-tree.json   — курированное знание (rails/стратегии/принципы/парки)
  datasets/lbp/pairs.jsonl          — живая матрица 20 пар (статусы/attempts/цитаты)

План НЕ отправляет ничего сам. Прогон — отдельными командами (lbp.py repeat / lbp_blitz.py),
которые планировщик печатает готовыми к запуску.

Usage:
  python3 harness/lbp_plan.py --all
  python3 harness/lbp_plan.py --scenario banking-idor-exploit
  python3 harness/lbp_plan.py --scenario banking-idor-exploit --model "Diamond Whale Bold"
  python3 harness/lbp_plan.py --check
  python3 harness/lbp_plan.py --principles
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
TREE_PATH = WORK / "datasets/lbp/decision-tree.json"
PAIRS_PATH = WORK / "datasets/lbp/pairs.jsonl"


def load_tree():
    try:
        return json.loads(TREE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot load {TREE_PATH}: {exc}")
        raise SystemExit(2)


def load_pairs():
    rows = []
    for line in PAIRS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def model_class(tree, model):
    mc = tree.get("model_classes", {}).get(model)
    return (mc or {}).get("class", "unknown")


def pair_status(row):
    outcome = (row.get("outcome") or "?").upper()
    if outcome == "SUCCESS":
        return "SUCCESS"
    return "OPEN"


def pick_runnable(tree, scen_key, model):
    """Первый tier, который можно ПРОГНАТЬ для этого класса модели (иначе None)."""
    sc = tree["scenarios"][scen_key]
    cls = model_class(tree, model)
    for tier in sc.get("strategy_priority", []):
        if tier.get("strategy") == "PARK":
            continue
        if tier.get("status") != "proven":
            continue
        fit = tier.get("fit", [])
        if cls == "unknown" or "any" in fit or cls in fit:
            return tier
    return None


def park_entry(tree, scen_key):
    for tier in tree["scenarios"][scen_key].get("strategy_priority", []):
        if tier.get("strategy") == "PARK":
            return tier
    return {"reason": "все классы исчерпаны/отбиты"}


def render_command(scen_key, model, tier):
    inputs = tier.get("inputs") or []
    if tier.get("manual") and not inputs:
        return tier["manual"]
    if len(inputs) == 1:
        return (f"python3 harness/lbp.py repeat --target <TAB> --scenario {scen_key} "
                f"--model \"{model}\" --input {inputs[0]} --n 1 --wait-s 180 --submit")
    if len(inputs) > 1:
        cmds = [f"python3 harness/lbp.py repeat --target <TAB> --scenario {scen_key} "
                f"--model \"{model}\" --input {inp} --n 1 --wait-s 180"
                for inp in inputs]
        return ("; ".join(cmds) + "  # последовательно в ОДНОМ чате; суд — после последнего шага")
    return tier.get("manual", "")


def plan_pair(tree, scen_key, model, row):
    sc = tree["scenarios"][scen_key]
    cls = model_class(tree, model)
    tgt = sc["target"]
    lines = []
    lines.append(f"  [{model}]  категория: {tgt['kind']} | класс модели: {cls}")
    lines.append(f"    цель: {tgt['contract']}")
    st = pair_status(row)
    if st == "SUCCESS":
        lines.append("    => ЗАКРЫТА (SUCCESS) — не трогать (решённые пары закрыты)")
        return lines
    lines.append(f"    статус: не закрыта (attempts={row.get('attempts')}, judge={row.get('judge')})")
    quote = (row.get("notes") or "").replace("\n", " ")
    if quote:
        lines.append(f"    последнее из записей: {quote[:180]}")
    tier = pick_runnable(tree, scen_key, model)
    if tier:
        lines.append(f"    => RUN tier-{tier['tier']}: {tier['strategy']}  (evidence: {tier.get('evidence','')})")
        cmd = render_command(scen_key, model, tier)
        if cmd:
            lines.append(f"       cmd: {cmd}")
        lines.append("       (перед прогоном: перечитать CLAUDE.md; CHAT_TARGET=<своя вкладка>)")
    else:
        park = park_entry(tree, scen_key)
        lines.append(f"    => PARK: {park.get('reason','')}")
        nxt = sc.get("next_if_rotation")
        if nxt:
            lines.append(f"       next_if_rotation: {nxt}")
    return lines


def cmd_all(tree, pairs):
    print("=== ПЛАН ПО ДОСКЕ Lucky Break: Payday (все 5 сценариев) ===\n")
    solved = sum(1 for r in pairs if (r.get("outcome") or "").upper() == "SUCCESS")
    print(f"Матрица: {solved}/20 пар закрыто. Живая правда: datasets/lbp/pairs.jsonl\n")
    for scen_key, sc in tree["scenarios"].items():
        rows = [r for r in pairs if r["scenario_id"] == scen_key]
        solved_here = sum(1 for r in rows if (r.get("outcome") or "").upper() == "SUCCESS")
        print(f"--- {scen_key} ({sc['title']}) — {solved_here}/{len(rows)} ---")
        for row in rows:
            for ln in plan_pair(tree, scen_key, row["model_id"], row):
                print(ln)
        print()
    print("Плейбук ротации (для новых моделей):")
    for i, step in enumerate(tree.get("rotation_playbook", {}).get("order", []), 1):
        print(f"  {i}. {step}")
    print(f"  tooling: {tree.get('rotation_playbook', {}).get('tooling', '')}")


def cmd_scenario(tree, scen_key, model=None):
    if scen_key not in tree["scenarios"]:
        print(f"ERROR: unknown scenario '{scen_key}'")
        print("known:", ", ".join(tree["scenarios"].keys()))
        return 2
    pairs = load_pairs()
    rows = [r for r in pairs if r["scenario_id"] == scen_key]
    if model:
        rows = [r for r in rows if r["model_id"].lower() == model.lower()]
        if not rows:
            print(f"ERROR: model '{model}' not found in {scen_key}")
            return 2
    sc = tree["scenarios"][scen_key]
    print(f"=== {scen_key} ({sc['title']}) ===")
    print(f"rails: {'; '.join(sc.get('rails', [])[:3])}")
    if sc.get("doors"):
        print(f"doors (подтверждённые): {'; '.join(sc['doors'])}")
    print()
    for row in rows:
        for ln in plan_pair(tree, scen_key, row["model_id"], row):
            print(ln)
        print()
    return 0


def cmd_check(tree):
    errors = []
    ok = 0
    for scen_key, sc in tree["scenarios"].items():
        for tier in sc.get("strategy_priority", []):
            for inp in tier.get("inputs", []):
                p = WORK / inp
                if p.is_file():
                    ok += 1
                else:
                    errors.append(f"{scen_key}: tier-{tier.get('tier')} input missing: {inp}")
    try:
        pairs = load_pairs()
        if len(pairs) != 20:
            errors.append(f"pairs.jsonl: expected 20 rows, found {len(pairs)}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pairs.jsonl unreadable: {exc}")
    print(f"inputs verified: {ok}")
    if errors:
        print("ERRORS:")
        for e in errors:
            print(" -", e)
        return 1
    print("check OK: дерево консистентно, все input-файлы на месте, pairs.jsonl читается (20 пар).")
    return 0


def cmd_principles(tree):
    print("=== Принципы (по приоритету) ===")
    for pr in tree.get("principles", []):
        print(f"{pr['rank']}. [{pr['id']}] {pr['rule']}")
        ev = pr.get("evidence", [])
        if ev:
            print(f"   evidence: {'; '.join(ev[:3])}")
    print("\n=== Протокол прогона ===")
    for i, step in enumerate(tree.get("run_protocol", []), 1):
        print(f"{i}. {step}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="LBP decision planner (read-only)")
    ap.add_argument("--all", action="store_true", help="план по всей доске")
    ap.add_argument("--scenario", help="сценарий (id)")
    ap.add_argument("--model", help="модель (точное имя)")
    ap.add_argument("--check", action="store_true", help="валидация дерева и ссылок")
    ap.add_argument("--principles", action="store_true", help="принципы + протокол")
    a = ap.parse_args()
    tree = load_tree()
    if a.check:
        return cmd_check(tree)
    if a.principles:
        return cmd_principles(tree)
    if a.scenario:
        return cmd_scenario(tree, a.scenario, a.model)
    if a.all:
        cmd_all(tree, load_pairs())
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
