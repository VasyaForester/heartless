#!/usr/bin/env python3
"""build_tried_index.py — сводит ВСЕ прогоны (pairs.jsonl + repeats.jsonl + corpus) в индекс
«класс × пара (scenario, model) × исход» для планирования по правилу 53 (no-rehash).

Выходы:
  datasets/lbp/tried-index.json  — машиночитаемый
  datasets/lbp/tried-index.md    — читаемая сводка (по сценариям и моделям)
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
DS = WS / "datasets" / "lbp"
CORPUS = DS / "corpus-classes-v5-refund-techniques-2026-11-11.md"

REFUSE = re.compile(r"refus|reject|declin|отбит|отказ|closed|закрыт|hard wall|failed|invalid", re.I)
WORKS = re.compile(r"\bWIN\b|accepted|EXECUTED|исполнен|принят|100%|solved|✅", re.I)

def segments(note: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\s*\|\s*", note or "")]
    return [p for p in parts if p and not p.startswith("+")]

def main() -> int:
    pairs = [json.loads(l) for l in (DS / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    runs = [json.loads(l) for l in (DS / "repeats.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    corpus = CORPUS.read_text(encoding="utf-8", errors="replace") if CORPUS.exists() else ""

    idx: dict = {"pairs": [], "corpus_refs": {}, "totals": {}}
    per_pair_total = 0
    for p in pairs:
        scen, model = p.get("scenario_id"), p.get("model_id")
        segs = segments(p.get("notes", ""))
        closed, works, unknown = [], [], []
        for s in segs:
            if WORKS.search(s) and "100%" in s or re.search(r"\bWIN\b|EXECUTED|accepted", s):
                works.append(s)
            elif REFUSE.search(s):
                closed.append(s)
            else:
                unknown.append(s)
        idx["pairs"].append({
            "scenario": scen, "model": model,
            "outcome": p.get("outcome"), "solved": p.get("solved", False),
            "classes_closed": len(closed), "works": works, "unknown": unknown,
        })
        per_pair_total += len(closed)

    idx["totals"]["closed_class_mentions"] = per_pair_total
    idx["totals"]["pairs"] = len(pairs)
    idx["totals"]["runs_in_ledger"] = len(runs)

    # упоминания в corpus по секциям
    for m in re.finditer(r"^## ([A-ZА-Я]\. .+)$", corpus, re.M):
        idx["corpus_refs"].setdefault(m.group(1), 0)
        idx["corpus_refs"][m.group(1)] += 1

    (DS / "tried-index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Индекс «что уже пробовано» (правило 53) — автогенерация", ""]
    lines.append(f"Пар: {idx['totals']['pairs']} · записей в леджере: {idx['totals']['runs_in_ledger']} · закрытых упоминаний классов: {per_pair_total}")
    lines.append("")
    for p in idx["pairs"]:
        lines.append(f"## {p['scenario']} × {p['model']} — {'SOLVED' if p['solved'] else (p['outcome'] or '?')} (закрыто упоминаний: {p['classes_closed']})")
        for s in p["works"]:
            lines.append(f"- ✅ WORKS: {s[:220]}")
        if p["unknown"]:
            lines.append(f"- ❓ неоднозначные сегменты: {len(p['unknown'])} (см. tried-index.json)")
        lines.append("")
    (DS / "tried-index.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote datasets/lbp/tried-index.json and tried-index.md")
    print("pairs:", len(pairs), "closed_mentions:", per_pair_total, "ledger:", len(runs))
    return 0

if __name__ == "__main__":
    sys.exit(main())
