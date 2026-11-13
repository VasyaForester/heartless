#!/usr/bin/env python3
"""Immutable evidence store v3 (Phase 3).

One directory per attempt, written once, never silently rewritten:

  artifacts/attempts/<attempt_id>/
      manifest.json      — run id, board/lane/cdp, scenario/model/delta, timestamps
      input.txt          — exact probe text
      environment.json   — caption of the captured environment facts
      transcript.json    — submit transcript copy (if present)
      judge_raw.json     — judge artifact copy captured AT THIS ATTEMPT
      judge_result.json  — correlation record (added by finish)
      evaluation.json    — local evaluation / multi-criterion placeholder
      checksums.json     — sha256 of every raw artifact

The judge copy is taken immediately after the transport returns, BEFORE any
later attempt can overwrite the per-pair judge file.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
ATTEMPTS_DIR = WORK / "artifacts" / "attempts"


def _sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return "missing"


def attempt_dir(attempt_id: str) -> pathlib.Path:
    d = ATTEMPTS_DIR / attempt_id.replace("|", "_").replace(":", "_")
    d.mkdir(parents=True, exist_ok=True)
    return d


def capture(attempt_id: str, *, key: str, input_path: str, delta: str, lane: str,
            transcript_path: pathlib.Path | None = None,
            judge_path: pathlib.Path | None = None) -> dict:
    d = attempt_dir(attempt_id)
    sid, model = key.split("|", 1)
    man = {}
    try:
        man = json.loads((WORK / "artifacts" / "run-manifest.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    info = {
        "attempt_id": attempt_id, "scenario": sid, "model": model, "delta": delta,
        "lane": lane, "input_path": str(input_path), "delta_version": 1,
        "run_id": man.get("run_id"), "board_id": man.get("board_id"),
        "cdp_endpoint": man.get("cdp_endpoint"), "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (d / "manifest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    src = pathlib.Path(input_path)
    if not src.is_absolute():
        src = WORK / src
    if src.exists():
        shutil.copyfile(src, d / "input.txt")

    env = {k: info[k] for k in ("run_id", "board_id", "lane", "cdp_endpoint") if k in info}
    env["note"] = "ui/model/tool-schema versions not exposed by the arena transport"
    (d / "environment.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")

    judge_copy = None
    if transcript_path and pathlib.Path(transcript_path).exists():
        shutil.copyfile(transcript_path, d / "transcript.json")
    if judge_path and pathlib.Path(judge_path).exists():
        judge_copy = d / "judge_raw.json"
        shutil.copyfile(judge_path, judge_copy)
    checks = {p.name: _sha_file(p) for p in sorted(d.glob("*.json")) + sorted(d.glob("*.txt"))}
    (d / "checksums.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    return {"dir": str(d), "judge_copy": judge_copy, "transcript_copy": d / "transcript.json"}


def finish(attempt_id: str, *, judge_result: dict | None = None,
           evaluation: dict | None = None) -> None:
    d = attempt_dir(attempt_id)
    if judge_result is not None:
        (d / "judge_result.json").write_text(
            json.dumps(judge_result, ensure_ascii=False, indent=2), encoding="utf-8")
    if evaluation is not None:
        (d / "evaluation.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    checks = {p.name: _sha_file(p) for p in sorted(d.glob("*.json")) + sorted(d.glob("*.txt"))}
    (d / "checksums.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")