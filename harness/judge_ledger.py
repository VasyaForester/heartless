#!/usr/bin/env python3
"""Judge ledger: bind every judge artifact to the OPERATION that produced it.

Why this module exists (defect found 2026-11-13, before Strategy Engine 2.0)
---------------------------------------------------------------------------
`lbp.py` writes the judge of a submission to a PER-PAIR file
(`artifacts/lbp-<sid>-<model>-judge.json`).  The v2/v3 driver then read that
file after every attempt and asked `judge_correlation` whether it belonged to
the attempt.  It usually did not:

  * submissions are gated (smart policy: cooldown + meaning), so most attempts
    never submit at all and the pair file still holds the PREVIOUS attempt's
    judge;
  * therefore `correlate()` returned `mismatched_operation` and the attempt was
    pushed into the terminal `judge_failed` state;
  * measured on the live DB: 104 of 114 attempts ended that way, 56 of 59
    archived judge copies were foreign, and the bandit's only reward channel
    was dead — the selector was learning from the seed file alone.

The ledger removes the ambiguity instead of guessing: a judge artifact is
stored under the operation id it carries (`artifacts/judges/<opid>.json`), so
"the judge of attempt X" is a lookup, not an inference.  An attempt without a
ledger entry is `unjudged` — a state that a LATE verdict can still bind to.

Files:
  artifacts/judges/<safe-opid>.json   — immutable copy of the judge artifact
  artifacts/judges/index.jsonl        — append-only index (opid, sha, status…)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
LEDGER_DIR = WORK / "artifacts" / "judges"
INDEX_PATH = LEDGER_DIR / "index.jsonl"

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(opid: str) -> str:
    """Filesystem-safe, collision-resistant name for an operation id."""
    opid = str(opid or "")
    slug = _SAFE.sub("-", opid).strip("-")[:80] or "noop"
    return f"{slug}-{hashlib.sha256(opid.encode('utf-8')).hexdigest()[:8]}"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_judge(path) -> dict | None:
    """Load a judge artifact, unwrapping the transport envelope if present."""
    p = pathlib.Path(path) if path else None
    if not p or not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    # `arena judge` may nest the payload under "result" or as a JSON string in
    # "observation" (the chat_ops path).  Normalise to the flat shape.
    for key in ("result", "observation"):
        inner = raw.get(key)
        if isinstance(inner, str):
            try:
                inner = json.loads(inner.replace("'", '"'))
            except Exception:
                inner = None
        if isinstance(inner, dict) and (inner.get("operationId") or inner.get("status")):
            merged = dict(raw)
            merged.pop(key, None)
            merged.update(inner)
            raw = merged
            break
    return raw


def operation_id_of(path) -> str | None:
    raw = read_judge(path)
    if not raw:
        return None
    op = raw.get("operationId")
    return str(op) if op else None


def status_of(path) -> str:
    raw = read_judge(path) or {}
    return str(raw.get("status") or "unknown").lower()


def path_for(opid: str) -> pathlib.Path | None:
    """Ledger copy bound to this operation id, if it exists."""
    if not opid:
        return None
    p = LEDGER_DIR / f"{safe_name(opid)}.json"
    return p if p.is_file() else None


def load(opid: str) -> dict | None:
    p = path_for(opid)
    return read_judge(p) if p else None


def is_foreign(judge_path, opid: str) -> bool:
    """True when the artifact exists but carries a DIFFERENT operation id.

    This is the exact condition the old driver mislabelled: the file belongs to
    an earlier submission of the same pair, not to the attempt under test.
    """
    got = operation_id_of(judge_path)
    return bool(got) and bool(opid) and got != opid


def bind(judge_path, opid: str, *, pair_key: str | None = None,
         source: str | None = None) -> dict:
    """Copy a judge artifact under its operation id (idempotent, atomic).

    Refuses to bind an artifact whose operation id contradicts `opid` — that is
    the mis-attribution this module exists to prevent.
    """
    p = pathlib.Path(judge_path) if judge_path else None
    if not p or not p.is_file():
        return {"bound": False, "reason": "no judge artifact", "opid": opid}
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {"bound": False, "reason": f"unreadable: {exc}", "opid": opid}
    raw = read_judge(p) or {}
    got = raw.get("operationId")
    if got and opid and str(got) != str(opid):
        return {"bound": False, "opid": opid, "judge_operation_id": str(got),
                "reason": "judge belongs to another operation"}
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    dest = LEDGER_DIR / f"{safe_name(str(opid or got or 'noop'))}.json"
    if not dest.exists():
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)  # atomic; an existing binding is never overwritten
    # The binding's identity is the STORED artifact, not the file we were handed:
    # a later submission rewrites the per-pair file, and the ledger must keep
    # reporting the verdict that belongs to this operation.
    stored = dest.read_bytes()
    sha = _sha_bytes(stored)
    raw = read_judge(dest) or raw
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "opid": str(opid or got or ""),
        "judge_operation_id": str(got) if got else None,
        "pair": pair_key,
        "source": source or str(p),
        "path": str(dest),
        "sha256": sha,
        "status": str(raw.get("status") or "unknown").lower(),
        "submitted_at": raw.get("submittedAt"),
        "chat_id": _chat_id(raw),
        "criteria_pcts": [c.get("text") for c in (raw.get("criteriaPercents") or [])
                          if isinstance(c, dict)][:6],
    }
    try:
        with open(INDEX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return {"bound": True, "path": str(dest), "sha256": sha, "opid": row["opid"]}


def _chat_id(raw: dict) -> str | None:
    m = re.search(r"chatId=([0-9a-fA-F]+)", str(raw.get("url") or ""))
    return m.group(1) if m else None


def index() -> list[dict]:
    out = []
    if INDEX_PATH.is_file():
        for line in INDEX_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def reconcile_unjudged(conn, lease, *, limit: int = 50) -> list[dict]:
    """Late-verdict pass: an `unjudged` attempt may still get its judge.

    Runs before selection so a pending verdict is not lost (RULES 11) and is
    never re-submitted (RULES 53).
    """
    import attempts as attempts_mod  # local import: avoid an import cycle
    import judge_correlation
    import store

    out = []
    rows = conn.execute(
        "SELECT * FROM attempts WHERE state='unjudged' ORDER BY started_at LIMIT ?",
        (int(limit),)).fetchall()
    for row in rows:
        opid = row["attempt_id"]
        jp = path_for(opid)
        if not jp:
            continue
        result = judge_correlation.correlate(row, jp, transcript_text=None,
                                             known_operations=store.known_judge_operations(conn))
        if result["status"] == "pending":
            attempts_mod.mark_awaiting(conn, lease, opid, judge_ref=str(jp))
            out.append({"attempt_id": opid, "status": "pending"})
            continue
        attempts_mod.mark_judge(conn, lease, opid, result)
        if result["status"] == "verified":
            solved = result["verdict"] in ("accepted", "solved")
            attempts_mod.finalize(conn, lease, opid, solved=solved)
            store.set_reward(conn, lease, opid, _reward_from_judge(result), "judge")
            out.append({"attempt_id": opid, "status": "verified",
                        "verdict": result["verdict"], "score": result["score"],
                        "solved": solved})
        else:
            out.append({"attempt_id": opid, "status": result["status"],
                        "reason": result.get("reason")})
    return out


def _reward_from_judge(result: dict) -> float | None:
    """Normalised judge reward: mean criterion percent in [0, 1]."""
    pcts = [p for p in (result.get("pcts") or []) if isinstance(p, (int, float))]
    if not pcts:
        score = result.get("score")
        return (float(score) / 100.0) if isinstance(score, (int, float)) else None
    return round(sum(pcts) / (100.0 * len(pcts)), 4)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bind", help="judge artifact to bind")
    ap.add_argument("--opid", help="operation id the artifact belongs to")
    ap.add_argument("--pair", help="scenario|model tag (optional)")
    ap.add_argument("--lookup", help="show the ledger entry for an operation id")
    ap.add_argument("--list", action="store_true", help="print the ledger index")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.bind:
        print(json.dumps(bind(a.bind, a.opid, pair_key=a.pair), ensure_ascii=False, indent=2))
        return 0
    if a.lookup:
        print(json.dumps(load(a.lookup) or {"bound": False}, ensure_ascii=False, indent=2))
        return 0
    rows = index()
    print(json.dumps({"entries": len(rows), "rows": rows[-20:]}, ensure_ascii=False, indent=2))
    return 0


def _selftest() -> int:
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        src = td / "pair-judge.json"
        src.write_text(json.dumps({
            "clicked": True, "status": "rejected", "operationId": "op-1",
            "submittedAt": "2026-11-13T10:00:00.000Z",
            "url": "https://app.grayswan.ai/arena/challenge/lucky-break-payday?chatId=abc123",
            "criteriaPercents": [{"selector": "#bits-c1", "text": "Tool `create` … 0%"}],
        }), encoding="utf-8")
        # 1) foreign artifact must NOT bind to another operation
        r = bind(src, "op-2")
        if r.get("bound") or r.get("reason") != "judge belongs to another operation":
            ok = False
            print("FAIL foreign artifact was bound", r)
        # 2) matching operation binds
        globals()["LEDGER_DIR"] = td / "judges"
        globals()["INDEX_PATH"] = globals()["LEDGER_DIR"] / "index.jsonl"
        r = bind(src, "op-1", pair_key="s|m")
        if not r.get("bound"):
            ok = False
            print("FAIL matching artifact did not bind", r)
        if not path_for("op-1"):
            ok = False
            print("FAIL path_for after bind")
        if operation_id_of(src) != "op-1" or not is_foreign(src, "op-9"):
            ok = False
            print("FAIL operation_id_of/is_foreign")
        if _reward_from_judge({"pcts": [0, 100]}) != 0.5:
            ok = False
            print("FAIL reward normalisation")
        print("bind:", json.dumps(r, ensure_ascii=False))
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
