#!/usr/bin/env python3
"""Judge/<->attempt correlation.

Freshness is a hint, never proof.  A judge is accepted only when its
operation id, chat id, timestamps, transcript hash and uniqueness agree with
the attempt that produced it.  Unverified judges never update solved state.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone

STATUSES = {"verified", "pending", "stale", "duplicate", "mismatched_chat",
            "mismatched_operation", "mismatched_transcript", "ambiguous",
            "unverified", "missing"}


def _parse_ts(value):
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _chat_id(raw: dict):
    m = re.search(r"chatId=([0-9a-fA-F]+)", str(raw.get("url") or ""))
    return m.group(1) if m else None


def _pcts(raw: dict):
    texts = []
    for item in (raw.get("criteriaPercents") or []):
        if isinstance(item, dict):
            texts.append(str(item.get("text") or ""))
        else:
            texts.append(str(item))
    for item in (raw.get("evidence") or []):
        if isinstance(item, dict):
            texts.append(str(item.get("text") or ""))
    pcts = []
    for text in texts:
        for n in re.findall(r"(\d+)%", text):
            pcts.append(int(n))
    return pcts


def correlate(attempt, judge_path, *, transcript_text=None,
              known_operations=None, now=None) -> dict:
    """Return a correlation record.  Never invents a verdict."""
    known_operations = known_operations or {}
    path = pathlib.Path(judge_path) if judge_path else None
    base = {
        "status": "missing", "reason": "no judge artifact", "judge_ref": str(path) if path else None,
        "raw_hash": None, "chat_id": None, "operation_id": None,
        "submitted_at": None, "captured_at": None, "verdict": None,
        "score": None, "pcts": [], "raw": None,
    }
    if not path or not path.is_file():
        return base
    try:
        raw_bytes = path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        base.update(status="unverified", reason=f"unreadable judge: {exc}")
        return base
    raw = raw.get("result", raw) if isinstance(raw, dict) else {}
    base["raw"] = raw
    base["raw_hash"] = hashlib.sha256(raw_bytes).hexdigest()[:16]
    base["chat_id"] = _chat_id(raw)
    base["operation_id"] = raw.get("operationId")
    base["submitted_at"] = raw.get("submittedAt")
    base["captured_at"] = raw.get("capturedAt")
    pcts = _pcts(raw)
    base["pcts"] = pcts
    base["score"] = sum(pcts) if pcts else None
    status = str(raw.get("status") or "unknown").lower()
    base["verdict"] = status

    attempt_id = attempt["attempt_id"]
    attempt_chat = attempt["chat_id"] if "chat_id" in attempt.keys() else None
    attempt_started = float(attempt["started_at"] or 0)

    if base["operation_id"] and base["operation_id"] != attempt_id:
        base.update(status="mismatched_operation",
                    reason=f"judge op {base['operation_id']} != attempt {attempt_id}")
        return base
    if base["chat_id"] and attempt_chat and base["chat_id"] != attempt_chat:
        base.update(status="mismatched_chat",
                    reason=f"judge chat {base['chat_id']} != attempt chat {attempt_chat}")
        return base
    submitted_ts = _parse_ts(base["submitted_at"])
    if submitted_ts and submitted_ts.timestamp() < attempt_started - 60:
        base.update(status="stale",
                    reason="judge submittedAt predates this attempt")
        return base
    if base["operation_id"] in known_operations and known_operations[base["operation_id"]] != attempt_id:
        base.update(status="duplicate",
                    reason=f"judge op already belongs to {known_operations[base['operation_id']]}")
        return base
    if transcript_text is not None:
        transcript_hash = attempt["transcript_hash"] if "transcript_hash" in attempt.keys() else None
        actual = hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()
        if transcript_hash and actual != transcript_hash:
            base.update(status="mismatched_transcript",
                        reason="judge transcript hash does not match the attempt")
            return base
    if status in {"pending", "unknown", ""}:
        base.update(status="pending", reason=f"judge status is {status or 'unknown'}")
        return base
    if status in {"ambiguous", "multiple"}:
        base.update(status="ambiguous", reason="judge says ambiguous")
        return base
    if not base["operation_id"] and not base["chat_id"] and not base["submitted_at"]:
        base.update(status="unverified", reason="no operation id, chat id or timestamp")
        return base
    if status in {"accepted", "rejected", "solved", "failed", "denied"}:
        base.update(status="verified", reason=f"judge status {status}")
        return base
    base.update(status="unverified", reason=f"unknown judge status {status}")
    return base