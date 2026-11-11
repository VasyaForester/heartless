#!/usr/bin/env python3
"""tried.py — «что уже пробовали»: список прошлых прогонов по (scenario, model|ALL).

Использование (перед проектированием новой пробы — правило 53):
  python3 harness/tried.py --scenario double-refund --model "Diamond Whale Bold"
  python3 harness/tried.py --scenario banking-idor-exploit            # по всем моделям
  python3 harness/tried.py --scenario double-refund --model "Sand Ant Plus Ultra" --grep doublecharge
"""
import argparse, json, sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
LEDGER = WORK / "datasets/lbp/repeats.jsonl"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--model", default=None, help="фильтр по модели (по умолчанию — все)")
    ap.add_argument("--grep", default=None, help="фильтр по подстроке в input/reply")
    ap.add_argument("--limit", type=int, default=200)
    a = ap.parse_args()
    if not LEDGER.exists():
        print(json.dumps({"error": "no ledger", "path": str(LEDGER)}, ensure_ascii=False))
        sys.exit(1)
    rows = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            j = json.loads(ln)
        except Exception:
            continue
        if j.get("scenario") != a.scenario:
            continue
        if a.model and j.get("model") != a.model:
            continue
        blob = (j.get("input", "") + " " + (j.get("reply_tail") or ""))
        if a.grep and a.grep.lower() not in blob.lower():
            continue
        rows.append(j)
    rows = rows[-a.limit:]
    out = []
    for j in rows:
        out.append({
            "ts": j.get("ts"), "model": j.get("model"), "sha16": j.get("input_sha256"),
            "input": j.get("input"), "check_ready": j.get("check_ready"),
            "refusal_guard": j.get("refusal_guard"),
            "tail": (j.get("reply_tail") or "")[:140].replace("\n", " "),
        })
    # --- follow-up путь (chat_ops): тоже «пробы» — показываем, что и когда слали в чаты
    fups = []
    for fp in sorted((WORK / "artifacts").glob("chatops-*-send.json")):
        try:
            j = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        msgs = j.get("messages") or []
        last_user = ""
        for m in msgs:
            if (m or {}).get("role") == "user":
                last_user = m.get("text") or ""
        resp = ((j.get("response") or {}).get("text") or "")
        blob = last_user + " " + resp
        if a.grep and a.grep.lower() not in blob.lower():
            continue
        fups.append({
            "ts": j.get("sentAt"), "chat": fp.name.split("-")[1],
            "sent": last_user[:140].replace("\n", " "),
            "reply": resp[:100].replace("\n", " "),
        })
    print(json.dumps({"scenario": a.scenario, "model": a.model or "ALL", "n": len(out), "runs": out,
                      "followups_scope": "ВСЕ сценарии (в chatops-файлах нет поля scenario)",
                      "followups_n": len(fups), "followups": fups[-a.limit:]},
                     ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
