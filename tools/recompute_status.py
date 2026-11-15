#!/usr/bin/env python3
"""Пересчитать статусы пар по таксономии отказов (ChatGPT review 2026-11-15).

Сканирует последние evidence-каталоги каждой незакрытой пары, классифицирует
каждую попытку (harness/failure_taxonomy.classify) и выносит решение:
CONTINUE / CHANGE_HYPOTHESIS / DIAGNOSE_LIMITED / PARK / REVALIDATE.

По умолчанию — только отчёт. С --write обновляет datasets/lbp/pair-status.json:
PARK -> status="PARKED" (+failure_class/reason), DIAGNOSE_LIMITED -> пометка
diagnostic с бюджетом, остальные — поле decision для сведения.

Usage:
  python3 tools/recompute_status.py [--n 30] [--write]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import time

W = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(W / "harness"))

import failure_taxonomy as ft  # noqa: E402

A = W / "artifacts"
STATUS_FILE = W / "datasets" / "lbp" / "pair-status.json"


def attempts_map(conn) -> dict:
    out = {}
    for r in conn.execute("SELECT attempt_id, execution_status, judge_status, score "
                          "FROM attempts"):
        out[r["attempt_id"]] = dict(r)
    return out


def evidence_rows(conn) -> dict:
    amap = attempts_map(conn)
    pairs: dict[str, list] = {}
    dirs = [d for d in (A / "attempts").iterdir() if d.is_dir()]
    dirs.sort(key=lambda p: (p / "manifest.json").stat().st_mtime
              if (p / "manifest.json").is_file() else 0)
    for d in dirs:
        man = d / "manifest.json"
        if not man.is_file():
            continue
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
        except Exception:
            continue
        pair = f"{m.get('scenario')}|{m.get('model')}"
        aid = m.get("attempt_id") or ""
        row = amap.get(aid) or {}
        execution_ok = (row.get("execution_status") in (None, "ok"))
        rendered = (d / "judge_raw.json").is_file()
        text = ""
        tp = d / "transcript.json"
        if tp.is_file():
            try:
                tr = json.loads(tp.read_text(encoding="utf-8", errors="replace"))
                text = "\n".join(m2.get("text") or "" for m2 in tr.get("messages", [])
                                 if m2.get("role") == "assistant")
            except Exception:
                pass
        cls = ft.classify(execution_ok=execution_ok, rendered=rendered, text=text,
                          judge_status=row.get("judge_status"), judge_score=row.get("score"),
                          judge_has_call=rendered)
        pairs.setdefault(pair, []).append(cls)
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    conn = sqlite3.connect(f"file:{A / 'harness.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    unsolved = [r["id"] for r in conn.execute("SELECT id FROM pairs WHERE solved=0")]
    pairs = evidence_rows(conn)
    conn.close()

    report = {}
    print(f"{'pair':52s} {'n':>3s} {'dominant':18s} {'share':>5s}  decision")
    for pair in sorted(unsolved):
        classes = pairs.get(pair, [])[-a.n:]
        d = ft.decide(classes)
        report[pair] = d
        print(f"{pair[:52]:52s} {d['n']:>3d} {d['failure_class']:18s} "
              f"{d['share']:>5.2f}  {d['decision']:16s} {d['reason'][:60]}")

    if a.write:
        doc = {"schema": 1, "updated": time.strftime("%Y-%m-%dT%H:%M"),
               "note": "Статусы пар. PARKED — не сэмплируется драйвером.",
               "pairs": {}}
        if STATUS_FILE.is_file():
            try:
                doc = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        doc.setdefault("pairs", {})
        for pair, d in report.items():
            cur = doc["pairs"].get(pair) or {}
            cur["decision"] = d["decision"]
            cur["failure_class"] = d["failure_class"]
            cur["share"] = round(d["share"], 3)
            cur["n_window"] = d["n"]
            cur["reason"] = d["reason"]
            cur["checked_at"] = time.strftime("%Y-%m-%dT%H:%M")
            if d["decision"] == ft.PARK and cur.get("status") not in (
                    "POLICY_BLOCKED", "UNSAFE_OBJECTIVE", "PARKED", "PARK"):
                cur["status"] = "PARKED"
                cur["parked_reason"] = d["failure_class"]
            if d["decision"] == ft.DIAGNOSE_LIMITED:
                cur["diagnostic"] = {"class": d["failure_class"], "budget_probes": 8,
                                     "status": "open"}
            doc["pairs"][pair] = cur
        STATUS_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwritten: {STATUS_FILE.relative_to(W)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())