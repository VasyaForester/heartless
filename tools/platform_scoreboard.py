#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Счётчик самой платформы: сколько клеток взято, и какие ещё открыты.

Зачем отдельный инструмент. Наша бухгалтерия и платформа расходятся: `pairs.solved` и
`pair-status.json` описывают, что видно в НАШЕЙ базе, а арена считает пройденные клетки
сама («N/4 breaks» по сценарию, «M/20 BREAKS» по борде). Разбор 2026-11-15 прямо указал на
эту разницу: три negative-quantity клетки и две giftcard у нас припаркованы как «нет
движения», тогда как платформа держит по ним часть клеток пройденными. Для протокола
остановки/открытия (рекомендация №4) решает счётчик платформы, а причины отказа берутся
из нашего реестра.

Читает ТОЛЬКО текущую вкладку полосы (никаких переходов и кликов), поэтому безопасен при
живом водителе: `node harness/engine/arena.mjs read --target <TAB> --selector body`.

    python3 tools/platform_scoreboard.py [--json] [--out artifacts/platform-scoreboard.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

W = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(W / "harness"))

import lbcore  # noqa: E402
import lbp  # noqa: E402

NODE = "node"
ENGINE = W / "harness" / "engine" / "arena.mjs"
A = W / "artifacts"


def sh(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def board_tab() -> str:
    rc, out, _ = sh([NODE, str(ENGINE), "tabs"])
    if rc != 0:
        return ""
    try:
        tabs = json.loads(out)
    except Exception:
        return ""
    for t in tabs:
        if "lucky-break-payday" in str(t.get("url") or ""):
            return str(t.get("id") or "")
    return ""


def body_text(tab: str) -> str:
    rc, out, _ = sh([NODE, str(ENGINE), "read", "--target", tab, "--selector", "body"])
    if rc != 0:
        return ""
    try:
        d = json.loads(out)
        return str((d.get("matches") or [{}])[0].get("text") or "")
    except Exception:
        return ""


def parse(text: str) -> dict:
    """Разобрать счётчики борды: по сценариям «N/4 breaks» и «M/20 BREAKS»."""
    out = {"scenarios": {}, "total": None}
    lines = [ln.strip() for ln in text.splitlines()]
    hints = {sid: str(h).lower() for sid, h in lbp.CARD_HINTS.items()}
    titles = {sid: str(t).lower() for sid, t in lbp.SCENARIO_TITLES.items()}
    current = None
    for ln in lines:
        low = ln.lower()
        for sid, hint in hints.items():
            if hint and hint in low:
                current = sid
                break
        else:
            for sid, title in titles.items():
                if title and title in low:
                    current = sid
                    break
        m = re.match(r"^(\d+)\s*/\s*(\d+)\s*breaks?$", low)
        if m and current:
            done, total = int(m.group(1)), int(m.group(2))
            if current not in out["scenarios"]:
                out["scenarios"][current] = {"broken": done, "cells": total}
            current = None
            continue
        m = re.match(r"^(\d+)\s*/\s*(\d+)\s*breaks?$", low)
        if m and out["total"] is None:
            out["total"] = {"broken": int(m.group(1)), "cells": int(m.group(2))}
    return out


def our_state(conn) -> dict:
    """Что видно в НАШЕЙ базе: solved-флаг и лучший проверенный результат по паре."""
    state = {}
    for r in conn.execute("SELECT id, solved FROM pairs"):
        state[r["id"]] = {"solved": int(r["solved"] or 0), "verified": 0, "best": None}
    for r in conn.execute(
            "SELECT pair_id, COUNT(*) AS n, MAX(COALESCE(score, -1)) AS best FROM attempts"
            " WHERE judge_status='verified' GROUP BY pair_id"):
        st = state.setdefault(r["pair_id"], {"solved": 0, "verified": 0, "best": None})
        st["verified"] = int(r["n"] or 0)
        st["best"] = None if (r["best"] is None or r["best"] < 0) else int(r["best"])
    return state


def status_reasons() -> dict:
    try:
        d = json.loads((W / "datasets" / "lbp" / "pair-status.json").read_text(encoding="utf-8"))
        return d.get("pairs") or {}
    except Exception:
        return {}


def closed_registry() -> dict:
    """Реестр закрытых/открытых клеток с основанием (протокол остановки/открытия)."""
    try:
        d = json.loads((W / "datasets" / "lbp" / "broken-cells.json").read_text(encoding="utf-8"))
        return {"closed": d.get("closed") or {}, "open": d.get("open") or {}}
    except Exception:
        return {"closed": {}, "open": {}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=str(A / "platform-scoreboard.json"))
    a = ap.parse_args()

    tab = board_tab()
    if not tab:
        print(json.dumps({"error": "no lucky-break-payday tab on CDP 9223"}, ensure_ascii=False))
        return 1
    text = body_text(tab)
    if not text:
        print(json.dumps({"error": "empty body: lane tab not readable"}, ensure_ascii=False))
        return 1
    seen = parse(text)

    import sqlite3
    conn = sqlite3.connect(f"file:{A / 'harness.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ours = our_state(conn)
    reasons = status_reasons()
    reg = closed_registry()

    targets = []
    for sid in lbcore.SCENARIOS:
        sc = seen["scenarios"].get(sid) or {}
        models = lbcore.MODELS if isinstance(lbcore.MODELS, (list, tuple)) else list(lbcore.MODELS)
        for model in models:
            key = f"{sid}|{model}"
            if key in reg["closed"]:
                continue
            st = ours.get(key) or {}
            targets.append({
                "pair": key,
                "scenario_broken": f"{sc.get('broken', '?')}/{sc.get('cells', '?')}",
                "our_status": str((reasons.get(key) or {}).get("status") or "ACTIVE"),
                "our_verified": st.get("verified", 0),
                "our_best": st.get("best"),
                "reopen_if": str((reg["open"].get(key) or {}).get("reopen_if") or ""),
                "reason": ((reasons.get(key) or {}).get("rationale") or "")[:120],
            })

    seen_total = seen.get("total") or {}
    closed_reg = len(reg["closed"])
    mismatch = (bool(seen_total) and closed_reg != seen_total.get("broken"))

    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": seen["total"],
           "scenarios": seen["scenarios"], "closed_in_registry": closed_reg,
           "registry_matches_platform": (None if not seen_total else not mismatch),
           "targets": targets}
    pathlib.Path(a.out).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.json:
        print(json.dumps(rec, ensure_ascii=False, indent=1))
        return 0

    tot = seen["total"] or {}
    try:
        shown = pathlib.Path(a.out).resolve().relative_to(W)
    except ValueError:
        shown = pathlib.Path(a.out)
    print(f"счётчик платформы: {tot.get('broken', '?')}/{tot.get('cells', '?')} BREAKS "
          f"(сохранено в {shown})")
    print(f"закрыто по нашему реестру: {closed_reg} "
          f"→ {'совпадает' if not mismatch else 'РАСХОЖДЕНИЕ: перечитать квитанции'}")
    print()
    print(f"{'сценарий':30s}{'взято':>8}  наших проверенных судей")
    for sid, sc in seen["scenarios"].items():
        ver = sum(t["our_verified"] for t in targets if t["pair"].startswith(sid + "|"))
        print(f"  {sid:28s}{sc['broken']}/{sc['cells']:>5}  {ver}")
    print()
    print(f"ЦЕЛЬ: {len(targets)} клеток без закрытия — работать по ним, а не по общему числу:")
    for t in sorted(targets, key=lambda x: x["pair"]):
        tag = f" [{t['our_status']}]" if t["our_status"] != "ACTIVE" else ""
        print(f"  {t['pair']:52s} verified={t['our_verified']:<3} best={t['our_best']}{tag}")
        if t["reopen_if"]:
            print(f"      открывать при: {t['reopen_if'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
