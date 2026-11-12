#!/usr/bin/env python3
"""campaign.py — последовательный прогон ПЛАНА проб (P1 харнесс-плана): rule53-гейт, валидность,
остановка на check_ready, сводка. Обёртка над tools/run1.sh.

usage:
  python3 harness/campaign.py --plan artifacts/plan-next.json [--tag wave1] [--force-dup] [--limit N]
plan.json: {"items": [{"scenario": "...", "model": "...", "input": "inputs/....txt", "note": "..."}]}

Что делает по каждому item:
  1) rule53-гейт: sha256(input) — если уже в datasets/lbp/repeats.jsonl → SKIP (или --force-dup);
  2) bash tools/run1.sh <scenario> <model> <input> <tag>  (полный вывод пишется в artifacts/run1/<tag>.log);
  3) парсит поля валидности из лога (fresh_chat, fill_ok, sent_ok, invalid, mock_ok, check_ready,
     refusal_guard, reply_tail) и добавляет строку в artifacts/campaign-<ts>.jsonl;
  4) останавливается (--stop-on-ready, default on) при check_ready=true — чтобы глазами оценить reply_tail.
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys, time
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
FIELDS = ["fresh_chat", "fill_ok", "probe_ok", "sent_ok", "invalid", "mock_guess", "mock_ok",
          "check_ready", "refusal_guard", "lost_send_suspect"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_log(text: str) -> dict:
    out = {}
    for f in FIELDS:
        m = list(re.finditer(rf'"{f}":\s*(true|false|null|"[^"]*")', text))
        if m:
            v = m[-1].group(1)
            out[f] = {"true": True, "false": False, "null": None}.get(v, v.strip('"'))
    m = list(re.finditer(r'"reply_tail":\s*"((?:[^"\\]|\\.)*)"', text))
    if m:
        try:
            out["reply_tail"] = json.loads('"' + m[-1].group(1) + '"')
        except Exception:
            out["reply_tail"] = m[-1].group(1)[:400]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--force-dup", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--stop-on-ready", dest="stop_on_ready", action="store_true", default=True)
    ap.add_argument("--no-stop", dest="stop_on_ready", action="store_false")
    ap.add_argument("--dry", action="store_true", help="только rule53-гейт и план, без прогонов")
    a = ap.parse_args()

    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    items = plan["items"]
    if a.limit:
        items = items[:a.limit]
    ts = time.strftime("%H%M%S")
    tag = a.tag or f"camp{ts}"
    camp_log = WS / "artifacts" / f"campaign-{ts}.jsonl"

    # rule53-гейт
    seen = set()
    led = WS / "datasets" / "lbp" / "repeats.jsonl"
    if led.exists():
        for line in led.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line).get("input_sha256"))
            except Exception:
                pass

    results = []
    for i, it in enumerate(items, 1):
        inp = WS / it["input"]
        h = sha(inp)[:16]
        dup = h in seen
        status = "DUP-SKIP" if (dup and not a.force_dup) else "RUN"
        print(f"[{i}/{len(items)}] {status} {it['scenario']} × {it['model']} · {it['input']}")
        if a.dry or status == "DUP-SKIP":
            results.append({**it, "sha": h, "status": status})
            continue
        t = f"{tag}-{i:02d}-{it['scenario'][:12]}-{it['model'].split()[0]}"
        p = subprocess.run(["bash", "tools/run1.sh", it["scenario"], it["model"], it["input"], t,
                            "--force-dup" if dup else ""],
                           cwd=str(WS), capture_output=True, text=True, timeout=420)
        logtext = (WS / "artifacts" / "run1" / f"{t}.log").read_text(encoding="utf-8", errors="replace") if (WS / "artifacts" / "run1" / f"{t}.log").exists() else (p.stdout + p.stderr)
        res = {**it, "sha": h, "status": "DONE", "tag": t, **parse_log(logtext)}
        results.append(res)
        print("   ", {k: res.get(k) for k in FIELDS if k in res}, "|", (res.get("reply_tail") or "")[:120].replace("\n", " "))
        if res.get("check_ready") and a.stop_on_ready:
            print("   !! check_ready=true — остановка для ручной проверки reply_tail")
            break
        time.sleep(2)

    with camp_log.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nsummary -> {camp_log}")
    run = [r for r in results if r.get("status") == "DONE"]
    print(f"runs: {len(run)} · valid: {sum(1 for r in run if not r.get('invalid') and r.get('mock_ok', True))} · "
          f"ready: {sum(1 for r in run if r.get('check_ready'))} · dup-skip: {sum(1 for r in results if r.get('status') == 'DUP-SKIP')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
