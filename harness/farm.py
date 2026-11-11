#!/usr/bin/env python3
"""Sequential model farm for a Gray Swan scenario, with checkpoint/resume.

Example (Chat scenario):
  python3 harness/farm.py --target TID --track Chat --scenario-id owlsec-windows-desktop-bypass \
    --models "Copper Leopard Ethereal,Obsidian Fox Ultra,Pink Snail Ultra" \
    --input inputs/chat-winadmin-message-v5.txt \
    --scope inputs/scope-owlsec-windows-desktop-bypass.json \
    --judge-policy comply --pause 15 --opid-prefix pg-w1-c3 --board 'Proving Ground'

Image scenario: add  --image inputs/lock-v2-attempt05.png  (upload step runs before fill).

judge-policy: never | comply (judge only classified comply_*) | always
Checkpoint: artifacts/farm-<scenario>.json (per-model stage/class/files; safe to resume).

Notes:
- Uses the plain arena CLI, EXCEPT judge which goes through arena_heal.py (stale/visible auto-repairs).
- Verification gates: model select is verified via `models` snapshot; fill is verified via inspect grep of the input prefix.
- Never re-sends a model whose stage reached 'sent' (no duplicate sends on resume); use --retry to force re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
HACK = HERE / "hackathon.py"
HEAL = HERE / "arena_heal.py"

sys.path.insert(0, str(HERE))
from classify_response import classify  # noqa: E402


def sh(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def arena(*args, timeout=300):
    return sh([sys.executable, str(HACK), "arena", *args], timeout=timeout)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_models(snapshot_text):
    """-> list of {name, selected, disabled, broken} parsed from an arena models output."""
    try:
        d = json.loads(snapshot_text)
    except Exception:
        return []

    def find(o):
        if isinstance(o, dict):
            if "availableModels" in o:
                return o["availableModels"]
            for v in o.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = find(v)
                if r:
                    return r
        return None

    return find(d) or []


def model_selected(snapshot_text, model):
    ms = parse_models(snapshot_text)
    for m in ms:
        if m.get("name") == model:
            return bool(m.get("selected"))
    return None  # model not found / parse issue


def ensure_model_selected(target, model):
    """Select + verify; on failure refresh via another model and retry. -> (ok, note)"""
    arena("select-model", "--target", target, "--value", model)
    rc, out, err = arena("models", "--target", target)
    sel = model_selected(out, model)
    if sel:
        return True, "selected+verified"
    ms = parse_models(out)
    others = [m["name"] for m in ms
              if m.get("name") and m["name"] != model and not m.get("disabled")]
    if others:
        via = others[0]
        arena("select-model", "--target", target, "--value", via)
        time.sleep(1)
        arena("select-model", "--target", target, "--value", model)
        rc, out, err = arena("models", "--target", target)
        sel = model_selected(out, model)
        if sel:
            return True, f"selected+verified (refresh via {via})"
    return False, f"selected-state not confirmed (sel={sel})"


def bind_scope(target, track, scenario_id, model, board, scope_path, ctx):
    args = ["bind-scope", "--target", target, "--track", track, "--scenario-id", scenario_id,
            "--model-id", model, "--evidence-source", "user-scenario", "--board", board,
            "--observed-context", ctx, "--out", scope_path]
    rc, out, err = arena(*args)
    combined = out + err
    if "model is unknown" in combined:
        ok, note = ensure_model_selected(target, model)
        if ok:
            rc, out, err = arena(*args)
            combined = out + err
    ok = '"error"' not in combined
    return ok, combined[:300]


def load_ckpt(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"models": {}}


def save_ckpt(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--track", required=True, choices=["Chat", "Image", "Agent", "Indirect"])
    ap.add_argument("--scenario-id", required=True)
    ap.add_argument("--models", required=True, help="comma-separated exact model names")
    ap.add_argument("--input", required=True, help="message file")
    ap.add_argument("--scope", required=True, help="scope file path (reused/overwritten per model)")
    ap.add_argument("--image", help="optional image file to upload before fill (Image track)")
    ap.add_argument("--judge-policy", choices=["never", "comply", "always"], default="comply")
    ap.add_argument("--pause", type=int, default=15, help="seconds between models")
    ap.add_argument("--opid-prefix", required=True)
    ap.add_argument("--board", default="Proving Ground")
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument("--ckpt", help="checkpoint path override")
    ap.add_argument("--retry", action="store_true", help="force re-run even if already sent")
    ap.add_argument("--mark-sent", help="comma-separated models: mark stage=sent after manually "
                                        "reconciling an uncertain send")
    ap.add_argument("--dry-run", action="store_true", help="select/bind/inspect only; no send/judge")
    ap.add_argument("--sweep", action="store_true", help="run verdict_sweep.py after the batch")
    ap.add_argument("--no-judge-timeout", type=int, default=60000)
    a = ap.parse_args()

    models = [m.strip() for m in a.models.split(",") if m.strip()]
    msg = pathlib.Path(a.input).read_text(encoding="utf-8").strip()
    marker = msg[:40]
    # Checkpoint/run-log names are board-scoped so boards that reuse a scenario
    # slug (e.g. Lucky Break: Payday vs Proving Ground) never overwrite each other.
    board_slug = slug(a.board)
    run_prefix = (f"farm-{slug(a.scenario_id)}" if board_slug in ("", "proving-ground")
                  else f"farm-{board_slug}-{slug(a.scenario_id)}")
    ckpt_path = pathlib.Path(a.ckpt or f"artifacts/{run_prefix}.json")
    ckpt = load_ckpt(ckpt_path)
    ckpt.setdefault("scenario", a.scenario_id)  # durable id for reconciliers
    ckpt.setdefault("track", a.track)
    results = []

    if a.mark_sent:
        for name in [x.strip() for x in a.mark_sent.split(",") if x.strip()]:
            mm = ckpt["models"].setdefault(name, {"stage": "new"})
            mm["stage"] = "sent"
            mm["marked_sent_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_ckpt(ckpt_path, ckpt)
        print(f"marked sent: {a.mark_sent}")
        return

    # A stale chats modal breaks model selection ("sel=None" on every model):
    # close it by navigating back to the scenario before starting.
    # Proving Ground only: other boards have no ?behaviorId= switch and must be
    # recovered by a card click (select-scenario) instead.
    if board_slug in ("", "proving-ground"):
        rc, out, err = arena("tabs")
        try:
            for t in json.loads(out).get("result", []):
                u = t.get("url", "")
                if "proving-ground" in u and "modal=" in u:
                    arena("open", "--target", a.target, "--url",
                          f"https://app.grayswan.ai/arena/challenge/proving-ground?behaviorId={a.scenario_id}")
                    print("closed stale chats modal -> behaviorId page")
                    time.sleep(2)
                    break
        except Exception:
            pass
    else:
        print(f"board '{a.board}': skip ?behaviorId= modal reset (use arena select-scenario for other boards)")

    for model in models:
        m = ckpt["models"].setdefault(model, {"stage": "new"})
        if m.get("stage") in ("sent", "judged") and not a.retry:
            print(f"== {model}: skip (stage={m['stage']})")
            results.append((model, m.get("class"), m.get("judge"), "skipped"))
            continue
        if m.get("stage") == "send_intent" and not a.retry:
            print(f"== {model}: UNCERTAIN_SEND — stop happened between send-intent and confirmation.")
            print("   Do NOT resend blindly. Reconcile first:")
            print(f"   python3 harness/chat_ops.py find --target {a.target} --model '{model}' "
                  f"--bootstrap-chat-id <any-known-chatId>")
            print(f"   If the chat exists with a response: re-run with --mark-sent \"{model}\".")
            print("   Only if the chat does NOT exist: re-run with --retry.")
            results.append((model, None, None, "uncertain_send"))
            continue

        s = slug(model)
        base = f"{a.out_dir}/farm-{s}"
        print(f"\n==== {model} ====")
        ok, note = ensure_model_selected(a.target, model)
        print("select:", note)
        if not ok:
            m.update({"stage": "error", "err": "select"})
            save_ckpt(ckpt_path, ckpt)
            continue

        ok, note = bind_scope(a.target, a.track, a.scenario_id, model, a.board, a.scope,
                              f"farm.py run for {model}")
        print("bind:", "OK" if ok else f"FAIL {note}")
        if not ok:
            m.update({"stage": "error", "err": f"bind: {note}"})
            save_ckpt(ckpt_path, ckpt)
            continue

        if a.dry_run:
            inspect_path = f"{base}-inspect-dry.json"
            arena("inspect", "--target", a.target, "--out", inspect_path)
            print("dry-run: would send", a.input, "| marker:", marker[:30])
            m.update({"stage": "dry-run"})
            save_ckpt(ckpt_path, ckpt)
            results.append((model, "-", "-", "dry-run"))
            continue

        # 3. optional image
        if a.image:
            rc, out, err = arena("upload", "--scope", a.scope, "--selector", 'input[name="fileUpload"]',
                                 "--file", a.image)
            if '"error"' in out + err:
                print("upload error:", (out + err)[:160])
        # 4. fill + verify
        rc, out, err = arena("fill", "--scope", a.scope, "--selector", "#chatTextarea", "--file", a.input)
        if '"filled": true' not in out:
            print("fill error:", (out + err)[:200]); m.update({"stage": "error", "err": "fill"}); save_ckpt(ckpt_path, ckpt); continue
        inspect_path = f"{base}-inspect.json"
        rc, out, err = arena("inspect", "--target", a.target, "--out", inspect_path)
        try:
            ins = pathlib.Path(inspect_path).read_text(encoding="utf-8")
        except Exception:
            ins = ""
        if marker and marker not in ins:
            print("WARN: input marker not found in inspect; continuing anyway")
        # 5. send — persist intent BEFORE pressing send: a crash between the two
        # checkpoints must read as uncertain_send, not trigger a silent resend.
        m.update({"stage": "send_intent",
                  "intent_ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "input_sha": hashlib.sha256(msg.encode("utf-8")).hexdigest()[:16]})
        save_ckpt(ckpt_path, ckpt)
        op_send = f"{a.opid_prefix}-{s}-send-01"
        rc, out, err = arena("send", "--scope", a.scope, "--file", a.input,
                             "--operation-id", op_send, "--timeout-ms", "180000",
                             "--out", f"{base}-send-result.json")
        time.sleep(1)
        txt = ""
        status = "unknown"
        try:
            d = json.loads(pathlib.Path(f"{base}-send-result.json").read_text(encoding="utf-8"))
            res = d.get("result") if "result" in d else d
            status = res.get("status")
            txt = ((res.get("response") or {}).get("text") or "")
        except Exception:
            pass
        cls, pre = classify(txt)
        m.update({"stage": "sent", "status": status, "class": cls, "pre": pre,
                  "send_file": f"{base}-send-result.json", "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
        print(f"send: status={status} class={cls} guess={pre.get('guess')}")
        save_ckpt(ckpt_path, ckpt)

        # 6. judge
        judge_state = "not-judged"
        # Judge only genuine compliance: full structured output or a visible tool call.
        # (comply_short is usually a refusal-with-help; judging it wastes submissions.)
        # SIEM scenario (owlsec-security-alert): the only artifact that can pass is a
        # "nothing suspicious" verdict (classify_response: comply_clean, siem_clean=True),
        # so judge that class instead of the inevitable critical reports.
        if a.scenario_id == "owlsec-security-alert":
            judge_worthy = bool(pre.get("siem_clean"))
        else:
            judge_worthy = (cls == "comply_full") or bool(pre.get("tool_call"))
        if a.judge_policy == "always" or (a.judge_policy == "comply" and judge_worthy):
            if status != "observed":
                judge_state = f"skipped (send status={status})"
            else:
                op_j = f"{a.opid_prefix}-{s}-judge-01"
                # Remove any previous judge file first: if the judge command fails to
                # produce a fresh verdict, the file must be MISSING so the result reads
                # as unknown — never a stale verdict from an older run (seen twice on
                # 2026-11-10: farm reported "rejected" from a Nov-7 W16 file).
                try:
                    os.remove(f"{base}-judge-result.json")
                except FileNotFoundError:
                    pass
                rc, out, err = sh([sys.executable, str(HEAL), "judge", "--target", a.target,
                                   "--scope", a.scope, "--operation-id", op_j,
                                   "--timeout-ms", str(a.no_judge_timeout),
                                   "--out", f"{base}-judge-result.json"], timeout=(a.no_judge_timeout // 1000 + 150))
                vstat = "unknown"
                try:
                    dj = json.loads(pathlib.Path(f"{base}-judge-result.json").read_text(encoding="utf-8"))
                    rj = dj.get("result") if "result" in dj else dj
                    vstat = rj.get("status", "unknown")
                except Exception:
                    pass
                if vstat == "unknown" and '"status": "rejected"' in out:
                    vstat = "rejected"
                if vstat == "unknown" and '"status": "accepted"' in out:
                    vstat = "accepted"
                judge_state = vstat
                print(f"judge: {vstat}")
                if vstat in ("pending", "unknown"):
                    sh([sys.executable, str(HERE / "pending.py"), "add", "--model", model,
                        "--scenario", a.scenario_id, "--track", a.track, "--opid", op_j,
                        "--note", f"farm judge {vstat}"])
        m.update({"stage": "judged" if judge_state not in ("not-judged",) else "sent",
                  "judge": judge_state})
        save_ckpt(ckpt_path, ckpt)
        results.append((model, cls, judge_state, status))

        # throttle-aware pause with jitter
        time.sleep(max(0, a.pause + random.randint(-5, 10)))

    print("\n==== farm summary ====")
    for r in results:
        print(" | ".join(str(x) for x in r))
    print("checkpoint:", ckpt_path)
    run_info = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "scenario": a.scenario_id,
                "dry_run": a.dry_run, "results": [list(r) for r in results]}
    run_path = f"{a.out_dir}/{run_prefix}-run-{time.strftime('%H%M%S')}.json"
    pathlib.Path(run_path).write_text(json.dumps(run_info, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    print("run log:", run_path)
    if a.sweep:
        rc, out, err = sh([sys.executable, str(HERE / "verdict_sweep.py"), "--target", a.target,
                           "--scope", a.scope, "--ckpt", str(ckpt_path),
                           "--scenario-id", a.scenario_id])
        print("sweep:", (out or err)[:800])


if __name__ == "__main__":
    main()
