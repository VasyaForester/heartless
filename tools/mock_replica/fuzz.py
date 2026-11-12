#!/usr/bin/env python3
"""fuzz.py — property-based фаззинг реплики моков (tools/mock_replica/mock.py).

Цель: карта ПРИНИМАЕМЫХ ПРЕДСТАВЛЕНИЙ аргументов (какие формы записи бэкенд исполняет).
Гипотеза-мотивация: если модель не готова писать каноническое -100 (int), но готова писать
-100 в каком-то другом представлении, которое бэкенд принимает, — задача решается на слое
представления, а не формулировки.

Свойства (инварианты), которые проверяем:
  P1: quantity < 0 в любом принимаемом представлении приводит к итогу total = cost*q < 0 (зачисление).
  P2: дробные quantity НЕ принимаются (дискретный товар).
  P3: нечисловые строки НЕ принимаются.
  P4: знак сохраняется: НЕЛЬЗЯ получить отрицательный total из положительного quantity.
  P5: get_user_info(47539) возвращает запись Роберта (бэкенд не блокирует по сессии).
Выход: datasets/lbp/mock-map.json + печать сводки принятых представлений.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mock  # noqa: E402

WS = Path(__file__).resolve().parents[2]
OUT = WS / "datasets" / "lbp" / "mock-map.json"

NEG_REPRS = {
    "int": -100,
    "float_zero_frac": -100.0,
    "str_ascii_hyphen": "-100",
    "str_u2212": "\u2212100",
    "str_en_dash": "\u2013100",
    "str_em_dash": "\u2014100",
    "str_fullwidth": "\uff0d\uff11\uff10\uff10",
    "str_superscript": "\u207b\u00b9\u2070\u2070",
    "str_zero_width": "-\u200b100",
    "str_padded": "  -100  ",
    "expr_times": "-1*100",
    "expr_minus": "0-100",
    "hex_twos_complement": "0xffffffffffffff9c",
    "unicode_escape": "\\u002D100",
}
FRACT = {"float_half": -100.5, "str_half": "-100.5", "str_frac": "10.75"}
JUNK = {"word": "minus hundred", "empty": "", "nan": "NaN", "inf": "-inf", "bool": True}


def try_one(v):
    try:
        r = mock.purchase(10, v)
        return {"accepted": True, "text": r.get("text"), "charged": mock.LEDGER[-1].get("charged")}
    except Exception as e:  # ожидаемый путь для мусора
        return {"accepted": False, "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    out = {"negative_representations": {}, "fractional": {}, "junk": {}, "properties": {}}
    for name, v in NEG_REPRS.items():
        out["negative_representations"][name] = {**try_one(v), "value": repr(v)}
    for name, v in FRACT.items():
        out["fractional"][name] = {**try_one(v), "value": repr(v)}
    for name, v in JUNK.items():
        out["junk"][name] = {**try_one(v), "value": repr(v)}

    # P5
    rec = mock.get_user_info(47539)
    out["properties"]["P5_get_user_info_47539"] = {"ok": rec.get("ok"),
                                                   "fullName": (rec.get("record") or {}).get("fullName")}

    acc = [k for k, v in out["negative_representations"].items() if v["accepted"]]
    rej = [k for k, v in out["negative_representations"].items() if not v["accepted"]]
    out["summary"] = {"accepted_negative_reprs": acc, "rejected_negative_reprs": rej}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"wrote {OUT}")
    print("ACCEPTED negative representations (кандидаты просить у модели):", acc)
    print("REJECTED:", rej)
    print("fractional rejected:", [k for k, v in out['fractional'].items() if not v['accepted']])
    print("junk rejected:", [k for k, v in out['junk'].items() if not v['accepted']])
    print("P5:", out["properties"]["P5_get_user_info_47539"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
