#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Что арена Gray Swan когда-либо ПРИНЯЛА: все accepted/solved из леджера проб.

Отвечает на вопрос «как принимает ответы gray swan» фактами из наших записей:
какие входы, на каких клетках и с какими процентами получили вердикт accepted/solved.
Печатает путь к входному файлу и проверяет, что файл ещё на диске (можно переиграть).
"""
import json
import pathlib

W = pathlib.Path(__file__).resolve().parent.parent
LEDGER = W / "datasets" / "lbp" / "repeats.jsonl"


def main():
    accepted = []
    verdicts = {}
    total = 0
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        total += 1
        v = str(d.get("verdict") or d.get("judge") or "").strip().lower()
        verdicts[v[:20]] = verdicts.get(v[:20], 0) + 1
        if v in ("accepted", "solved", "win"):
            accepted.append(d)
    print(f"строк в леджере: {total}")
    print("вердикты:", sorted(verdicts.items(), key=lambda kv: -kv[1])[:8])
    print()
    print(f"=== ПРИНЯТО ареной: {len(accepted)} ===")
    for d in accepted:
        inp = str(d.get("input") or "")
        ex = (W / inp).is_file() if inp else False
        print(f"  ts={d.get('ts')}  {str(d.get('scenario'))[:26]:26s} {str(d.get('attacking'))[:20]:20s} "
              f"pcts={d.get('pcts')} verdict={d.get('verdict')} файл={'ЕСТЬ' if ex else 'нет'}")
        if inp:
            print(f"      вход: {inp}")


if __name__ == "__main__":
    main()
