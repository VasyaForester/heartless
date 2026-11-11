#!/usr/bin/env python3
"""Auto-healing wrappers for arena operations.

Repairs the recurring state desyncs observed in practice:
- "Scope is stale: ..."            -> auto rebind from the scope file, retry
- "A judge verdict is already visible" -> click CONTINUE (short-text button), retry
- "Selected control is hidden or disabled" -> report with a concrete hint (manual step needed)

Usage (from the workspace dir):
  python3 harness/arena_heal.py judge --target T --scope inputs/scope-x.json --operation-id op-1 --timeout-ms 60000 --out artifacts/j.json
  python3 harness/arena_heal.py click --target T --scope S --selector 'CSS' --operation-id op-2
  python3 harness/arena_heal.py clear-verdict --target T --scope S
  python3 harness/arena_heal.py select-fresh --target T --value 'Model' [--via 'OtherModel']

Every repair is appended to attempts/heal-log.jsonl (technical log; result recording stays in attempts.jsonl).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
HACK = HERE / "hackathon.py"


def run_arena(args, timeout_s=240):
    cmd = [sys.executable, str(HACK), "arena"] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or ""), (e.stderr or "") + "\n[arena_heal] subprocess timeout"


def blob(rc, out, err):
    return (out + "\n" + err).strip()


def log_heal(kind, ok, msg):
    p = pathlib.Path("attempts/heal-log.jsonl")
    p.parent.mkdir(exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind,
                            "ok": ok, "msg": msg[:300]}, ensure_ascii=False) + "\n")
    mark = "OK" if ok else "FAILED"
    print(f"[heal] {kind}: {mark} | {msg[:180]}")


def load_scope_fields(path):
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    s = d.get("result") if isinstance(d, dict) and "result" in d else d
    out = {}
    for k in ("board", "track", "scenarioId", "modelId"):
        v = (s or {}).get(k)
        if v:
            out[k] = v
    return out


def rebind(target, scope_path):
    f = load_scope_fields(scope_path)
    missing = [k for k in ("track", "scenarioId", "modelId") if not f.get(k)]
    if missing:
        return False, f"cannot auto-rebind; scope file missing: {missing}"
    args = ["bind-scope", "--target", target,
            "--track", f["track"], "--scenario-id", f["scenarioId"], "--model-id", f["modelId"],
            "--evidence-source", "user-scenario",
            "--observed-context", "auto-heal rebind (arena_heal)", "--out", scope_path]
    if f.get("board"):
        args += ["--board", f["board"]]
    rc, out, err = run_arena(args, timeout_s=120)
    ok = '"error"' not in (out + err) and ("bind-scope" in out or rc == 0)
    return ok, blob(rc, out, err)[:400]


def find_short_button(target, label, out_path):
    rc, out, err = run_arena(["inspect", "--target", target, "--out", out_path], timeout_s=120)
    try:
        d = json.loads(pathlib.Path(out_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    found = []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("text")
            if isinstance(t, str) and t.strip() == label and o.get("selector"):
                found.append(o["selector"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return found[0] if found else None


def try_clear_verdict(target, scope):
    path = str(pathlib.Path("artifacts") / f"heal-inspect-{int(time.time())}.json")
    sel = find_short_button(target, "CONTINUE", path)
    if not sel:
        log_heal("clear-verdict", False, "CONTINUE button not found on page")
        return False
    op = f"heal-continue-{int(time.time())}"
    rc, out, err = run_arena(["click", "--scope", scope, "--selector", sel, "--operation-id", op], timeout_s=120)
    ok = '"clicked": true' in out
    log_heal("clear-verdict", ok, f"selector={sel[:70]}")
    if ok:
        time.sleep(2)
    return ok


def cmd_send(a):
    """send with auto-rebind on stale scope (URL changes after every send)."""
    last = ""
    for attempt in range(1, 4):
        args = ["send", "--scope", a.scope, "--file", a.file, "--operation-id", a.operation_id]
        if a.timeout_ms:
            args += ["--timeout-ms", str(a.timeout_ms)]
        if a.out:
            args += ["--out", a.out]
        tmo = (int(a.timeout_ms / 1000) + 120) if a.timeout_ms else 300
        rc, out, err = run_arena(args, timeout_s=tmo)
        text = blob(rc, out, err)
        last = text
        if "scope is stale" in text.lower():
            ok, msg = rebind(a.target, a.scope)
            log_heal("stale->rebind", ok, msg)
            if ok:
                time.sleep(1)
            continue
        print(out)
        return rc
    print(last)
    return 1


def cmd_judge(a):
    last = ""
    for attempt in range(1, 4):
        tmo = (int(a.timeout_ms / 1000) + 90) if a.timeout_ms else 240
        args = ["judge", "--scope", a.scope, "--operation-id", a.operation_id]
        if a.timeout_ms:
            args += ["--timeout-ms", str(a.timeout_ms)]
        if a.out:
            args += ["--out", a.out]
        rc, out, err = run_arena(args, timeout_s=tmo)
        text = blob(rc, out, err)
        last = text
        low = text.lower()
        if "scope is stale" in low:
            ok, msg = rebind(a.target, a.scope)
            log_heal("stale->rebind", ok, msg)
            continue
        if "verdict is already visible" in low:
            if try_clear_verdict(a.target, a.scope):
                continue
            break
        if "hidden or disabled" in low:
            log_heal("hidden-control", False, "judge button hidden/disabled — inspect page manually (blocked/empty chats can disable Submit)")
            print(text)
            return rc
        print(out)
        return rc
    print(last)
    return 1


def cmd_click(a):
    last = ""
    for attempt in range(1, 4):
        rc, out, err = run_arena(["click", "--scope", a.scope, "--selector", a.selector,
                                  "--operation-id", a.operation_id], timeout_s=180)
        text = blob(rc, out, err)
        last = text
        low = text.lower()
        if "scope is stale" in low:
            ok, msg = rebind(a.target, a.scope)
            log_heal("stale->rebind", ok, msg)
            continue
        if "hidden or disabled" in low:
            log_heal("hidden-control", False, f"click target hidden: {a.selector[:70]}")
            print(text)
            return rc
        print(out)
        return rc
    print(last)
    return 1


def cmd_clear_verdict(a):
    ok = try_clear_verdict(a.target, a.scope)
    return 0 if ok else 1


def cmd_select_fresh(a):
    """Force a fresh chat for the target model: if the same model is already selected,
    selecting is a no-op, so we switch via another model first when --via is given."""
    if a.via:
        rc, out, err = run_arena(["select-model", "--target", a.target, "--value", a.via], timeout_s=120)
        if '"error"' in out + err:
            log_heal("select-fresh", False, f"via-select failed: {blob(rc,out,err)[:200]}")
            print(blob(rc, out, err))
            return 1
        time.sleep(1)
    rc, out, err = run_arena(["select-model", "--target", a.target, "--value", a.value], timeout_s=120)
    print(out)
    ok = f'"{a.value}"' in out and '"error"' not in out + err
    log_heal("select-fresh", ok, f"target={a.value} via={a.via}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Auto-healing arena wrappers")
    sub = ap.add_subparsers(dest="cmd", required=True)

    snd = sub.add_parser("send")
    snd.add_argument("--target", required=True)
    snd.add_argument("--scope", required=True)
    snd.add_argument("--file", required=True)
    snd.add_argument("--operation-id", required=True)
    snd.add_argument("--timeout-ms", type=int, default=120000)
    snd.add_argument("--out")
    snd.set_defaults(fn=cmd_send)

    j = sub.add_parser("judge")
    j.add_argument("--target", required=True)
    j.add_argument("--scope", required=True)
    j.add_argument("--operation-id", required=True)
    j.add_argument("--timeout-ms", type=int, default=60000)
    j.add_argument("--out")
    j.set_defaults(fn=cmd_judge)

    c = sub.add_parser("click")
    c.add_argument("--target", required=True)
    c.add_argument("--scope", required=True)
    c.add_argument("--selector", required=True)
    c.add_argument("--operation-id", required=True)
    c.set_defaults(fn=cmd_click)

    v = sub.add_parser("clear-verdict")
    v.add_argument("--target", required=True)
    v.add_argument("--scope", required=True)
    v.set_defaults(fn=cmd_clear_verdict)

    s = sub.add_parser("select-fresh")
    s.add_argument("--target", required=True)
    s.add_argument("--value", required=True)
    s.add_argument("--via")
    s.set_defaults(fn=cmd_select_fresh)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
