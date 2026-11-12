#!/usr/bin/env python3
"""Offline deterministic replay of a generated attempt.  Never submits."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import generation  # noqa: E402
import store  # noqa: E402

REQUIRED = ("parent_input_path", "delta", "nonce", "delta_version", "input_hash")


def replay(conn, attempt_id: str) -> dict:
    row = store.get_attempt(conn, attempt_id)
    if not row:
        return {"ok": False, "error": f"attempt {attempt_id} not found"}
    missing = [k for k in REQUIRED if row[k] in (None, "")]
    base_path = row["parent_input_path"]
    if base_path and not pathlib.Path(base_path).is_absolute():
        base_path = str(WORK / base_path)
    if missing:
        return {"ok": False, "error": "missing replay metadata", "missing": missing,
                "attempt_id": attempt_id}
    base = pathlib.Path(base_path)
    if not base.is_file():
        return {"ok": False, "error": f"parent input not found: {base}",
                "attempt_id": attempt_id}
    text = generation.generate(base.read_text(encoding="utf-8", errors="replace"),
                              row["delta"], row["nonce"],
                              int(row["delta_version"]))
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "ok": actual == row["input_hash"],
        "attempt_id": attempt_id,
        "delta": row["delta"],
        "delta_version": row["delta_version"],
        "nonce": row["nonce"],
        "parent_input_path": base_path,
        "parent_input_hash": row["parent_input_hash"],
        "expected_input_hash": row["input_hash"],
        "replayed_input_hash": actual,
        "bytes": len(text.encode("utf-8")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--attempt-id", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    conn = store.connect(a.db)
    try:
        result = replay(conn, a.attempt_id)
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())