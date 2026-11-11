#!/usr/bin/env python3
"""Incremental-accumulation runner для LBP (класс «$20 × 8» из литературы).

Идея: каждый запрос мал и валиден по отдельности, но серия в ОДНОМ чате накапливает сумму,
превышающую стоимость заказа. Скрипт:
  1) создаёт чат первым сообщением (через lbp.py repeat, без сабмита),
  2) достаёт chatId из адреса вкладки (lbp.py state),
  3) отправляет остальные шаги через chat_ops.py followup в ТОМ ЖЕ чате,
  4) печатает транскрипт и (по флагу --submit) пытается отправить на судью.

Пример:
  python3 harness/lbp_accum.py --scenario double-refund --model "Copper Turtle Brave" \
      --steps inputs/lbp-refund-acc-1.txt inputs/lbp-refund-acc-2.txt ... --wait-s 45
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BASE_URL = "https://app.grayswan.ai/arena/challenge/lucky-break-payday"
BOARD = "Lucky Break: Payday"


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, cwd=str(WORK), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")


def latest_chat_id(target: str) -> str | None:
    out = run(["python3", "harness/lbp.py", "state"])
    m = re.search(r'"url"\s*:\s*"([^"]+)"', out)
    if not m:
        return None
    m2 = re.search(r"chatId=([0-9a-f]+)", m.group(1))
    return m2.group(1) if m2 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--steps", nargs="+", required=True,
                    help="файлы сообщений в порядке отправки (первый создаёт чат)")
    ap.add_argument("--target", default="F7709C7D3AFF2EBC7048FA1DEEFF8368")
    ap.add_argument("--wait-s", type=int, default=45)
    ap.add_argument("--submit", action="store_true")
    a = ap.parse_args()

    t = a.target
    log: dict = {"scenario": a.scenario, "model": a.model, "steps": []}

    # 1) первый шаг — создаёт чат
    out1 = run(["python3", "harness/lbp.py", "repeat", "--scenario", a.scenario,
                "--model", a.model, "--input", a.steps[0], "--n", "1",
                "--wait-s", str(a.wait_s)])
    log["steps"].append({"i": 1, "file": a.steps[0], "raw": out1[-1500:]})
    print(f"== accum step 1: {a.steps[0]} ==")
    print(out1[-900:])

    cid = latest_chat_id(t)
    log["chatId"] = cid
    if not cid:
        print("!! не удалось определить chatId — останов")
        print(json.dumps(log, ensure_ascii=False)[:2000])
        return 1
    print(f"chatId={cid}")

    # 2) остальные шаги — в тот же чат
    for i, f in enumerate(a.steps[1:], start=2):
        print(f"== accum step {i}: {f} ==")
        out = run(["python3", "harness/chat_ops.py", "followup", "--target", t,
                   "--chat-id", cid, "--scenario-id", a.scenario, "--track", "Chat",
                   "--base-url", BASE_URL, "--board", BOARD, "--file", f])
        log["steps"].append({"i": i, "file": f, "raw": out[-1500:]})
        txt = ""
        m = re.search(r'"text"\s*:\s*"(.+?)"\s*[,}]', out, re.S)
        if m:
            txt = m.group(1)
        print(txt[:700] if txt else out[-500:])
        time.sleep(2)

    # 3) проверка и (опц.) сабмит
    chk = run(["python3", "harness/lbp.py", "check", "--scenario", a.scenario])
    log["check"] = chk[-1200:]
    ready = '"ready": true' in chk
    print(f"check_ready={ready}")
    if a.submit and ready:
        sub = run(["python3", "harness/lbp.py", "submit", "--scenario", a.scenario])
        log["submit"] = sub[-1500:]
        print(sub[-900:])

    outp = WORK / f"artifacts/lbp-accum-{a.scenario}-{int(time.time())}.json"
    outp.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved: {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
