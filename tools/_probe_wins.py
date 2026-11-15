#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Какие входы давали высокий счёт: топ строк леджера проб по сумме критериев.

Читает datasets/lbp/repeats.jsonl (большой файл — потому и скриптом, а не однострочником)
и печатает строки giftcard/negq/refund со счётом >= 90 вместе с путём к входному файлу,
чтобы можно было переиграть именно тот вход.
"""
import json
import pathlib

W = pathlib.Path(__file__).resolve().parent.parent
LEDGER = W / "datasets" / "lbp" / "repeats.jsonl"


def score_of(d):
    pcts = d.get("pcts") or d.get("judge_pcts") or []
    if isinstance(pcts, list) and pcts and all(isinstance(x, (int, float)) for x in pcts):
        return sum(pcts), pcts
    s = d.get("score")
    return (s, pcts) if isinstance(s, (int, float)) else (None, pcts)


def main():
    hits = []
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
        sc, pcts = score_of(d)
        if sc is None or sc < 90:
            continue
        hits.append((sc, pcts, str(d.get("scenario") or "")[:28],
                     str(d.get("attacking") or d.get("model") or "")[:22],
                     str(d.get("input") or "")[:64], str(d.get("ts") or "")))
    hits.sort(key=lambda t: -t[0])
    print(f"строк в леджере: {total}; счётов >= 90: {len(hits)}")
    for sc, pcts, sid, model, inp, ts in hits[:14]:
        exists = (W / inp).is_file() if inp else False
        print(f"  sc={sc:>4} pcts={str(pcts)[:26]:26s} {sid:28s} {model:22s} файл_есть={exists} {inp}")
    print()
    print("полные 100/100/100:", sum(1 for sc, pcts, *_ in hits
                                    if isinstance(pcts, list) and pcts and all(p == 100 for p in pcts)))


if __name__ == "__main__":
    main()
