#!/usr/bin/env python3
"""Explicit attempt lifecycle on top of `store.py`.

States: allocated -> prepared -> submitted -> awaiting_judge -> judged -> finalized.
Terminal failures: execution_failed, submission_uncertain, judge_failed, cancelled.
Every transition goes through `store.transition` (fenced + append-only event).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid

import store


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def new_attempt_id(board: str, scenario: str, model: str, lane: str) -> str:
    return f"{board}:{scenario}:{model}:{lane}:{uuid.uuid4().hex[:12]}"


def allocate(conn, lease, *, pair_id: str, board: str, scenario: str,
             model: str, model_version: str | None = None,
             lane: str, chat_id: str | None = None) -> str:
    attempt_id = new_attempt_id(board, scenario, model, lane)
    store.insert_attempt(conn, lease, {
        "attempt_id": attempt_id, "pair_id": pair_id, "board_profile": board,
        "scenario": scenario, "model": model, "model_version": model_version,
        "lane": lane, "chat_id": chat_id, "started_at": time.time(),
        "state": "allocated", "input_path": None,
    })
    return attempt_id


def prepare(conn, lease, attempt_id: str, *, input_text: str, input_path: str,
            parent_input_hash: str | None = None,
            parent_input_path: str | None = None,
            delta: str | None = None, delta_version: int | None = None,
            seed: int | None = None, nonce: str | None = None,
            strategy_version: int = 1) -> str:
    input_hash = sha256_text(input_text)
    store.transition(
        conn, lease, attempt_id, "prepared",
        input_path=input_path, input_hash=input_hash,
        parent_input_hash=parent_input_hash, parent_input_path=parent_input_path,
        delta=delta, delta_version=delta_version, seed=seed, nonce=nonce,
        strategy_version=strategy_version,
    )
    return input_hash


def mark_submitted(conn, lease, attempt_id: str, *, submitted_at: float | None = None,
                   chat_id: str | None = None, transcript_text: str | None = None,
                   execution_status: str = "ok") -> None:
    store.transition(
        conn, lease, attempt_id, "submitted",
        submitted_at=submitted_at if submitted_at is not None else time.time(),
        chat_id=chat_id,
        transcript_hash=sha256_text(transcript_text) if transcript_text is not None else None,
        execution_status=execution_status,
    )


def mark_uncertain(conn, lease, attempt_id: str, reason: str = "timeout/no judge") -> None:
    store.transition(conn, lease, attempt_id, "submission_uncertain",
                     execution_status="uncertain", payload={"reason": reason})


def mark_failed(conn, lease, attempt_id: str, reason: str) -> None:
    store.transition(conn, lease, attempt_id, "execution_failed",
                     execution_status="failed", payload={"reason": reason})


def mark_awaiting(conn, lease, attempt_id: str, *, judge_ref: str | None = None) -> None:
    store.transition(conn, lease, attempt_id, "awaiting_judge",
                     judge_ref=judge_ref, judge_status="pending")


def mark_unjudged(conn, lease, attempt_id: str,
                  reason: str = "no judge attributed to this operation") -> None:
    """The probe ran but produced no verdict of its own.

    Not terminal: `judge_ledger.reconcile_unjudged` will pick up a late verdict
    if one ever binds to this operation id.  Replaces the old behaviour of
    pushing the attempt into the terminal `judge_failed` (which destroyed the
    reward channel — 104/114 live attempts on 2026-11-13).
    """
    store.transition(conn, lease, attempt_id, "unjudged", judge_status="unjudged",
                     payload={"reason": reason})


def mark_judge(conn, lease, attempt_id: str, result: dict) -> None:
    """Persist a correlated judge.  Only a verified judge can reach `judged`."""
    store.record_judge(
        conn, lease, attempt_id, result["judge_ref"],
        chat_id=result.get("chat_id"), operation_id=result.get("operation_id"),
        submitted_at=result.get("submitted_at"), captured_at=result.get("captured_at"),
        status=result.get("status"), score=result.get("score"),
        pcts=result.get("pcts"), raw_path=result.get("judge_ref"),
        raw_hash=result.get("raw_hash"),
        verified=result.get("status") == "verified",
    )
    status = result.get("status")
    if status == "pending":
        return  # stay awaiting_judge; a missing judge must remain pending
    if status == "verified":
        store.transition(
            conn, lease, attempt_id, "judged", judge_status="verified",
            score=result.get("score"), pcts=json.dumps(result.get("pcts")),
            verdict=result.get("verdict"), judge_ref=result.get("judge_ref"),
            judge_hash=result.get("raw_hash"),
        )
        return
    store.transition(conn, lease, attempt_id, "judge_failed",
                     judge_status=status, payload={"reason": result.get("reason")})


def finalize(conn, lease, attempt_id: str, *, solved: bool) -> None:
    store.finalize_attempt(conn, lease, attempt_id, solved=solved)


def recover(conn, lease) -> list[dict]:
    """Crash recovery: never silently reset an in-progress attempt."""
    out = []
    rows = conn.execute(
        "SELECT attempt_id,state FROM attempts"
        " WHERE state IN ('prepared','submitted','awaiting_judge')").fetchall()
    for row in rows:
        state = row["state"]
        if state == "prepared":
            store.transition(conn, lease, row["attempt_id"], "execution_failed",
                             execution_status="failed",
                             payload={"reason": "worker restart before submit"})
            out.append({"attempt_id": row["attempt_id"], "from": state,
                        "to": "execution_failed"})
        elif state == "submitted":
            store.transition(conn, lease, row["attempt_id"], "submission_uncertain",
                             execution_status="uncertain",
                             payload={"reason": "worker restart after send; do not resubmit"})
            out.append({"attempt_id": row["attempt_id"], "from": state,
                        "to": "submission_uncertain"})
        else:
            out.append({"attempt_id": row["attempt_id"], "from": state,
                        "to": "awaiting_judge (kept)"})
    return out