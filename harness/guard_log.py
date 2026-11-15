"""Lifting a guard is an event, not a side effect of a flag.

Grok's review (2026-11-15, axis "refusal honesty": 7/10): `--force-submit` could
bypass the refusal guard with nothing written down — no who, no why, no which guard
was lifted.  A run whose exceptions are invisible is a run whose statistics lie.

The rule implemented here is fail-closed: `lift()` records WHO lifted WHICH guard and
WHY into the harness journal BEFORE the action it authorises, and if the record
cannot be written the caller must NOT perform the action (the returned dict says
`recorded: False`, and `allows_action()` is then False).

The axis-10 test of that requirement lives in harness/tests/test_guard_log.py: an
unrecordable lift must not let the attempt reach the submit.
"""

from __future__ import annotations

import json
import os
import pathlib
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
DB_DEFAULT = WORK / "artifacts" / "harness.db"

KIND = "guard_lifted"


def who() -> str:
    """Best-effort identity of the operator: flag, env, then the OS user."""
    return (os.environ.get("HERMES_FORCE_WHO")
            or os.environ.get("USERNAME") or os.environ.get("USER") or "unknown")


def lift(guard: str, *, reason: str, actor: str | None = None,
         attempt_id: str | None = None, opid: str | None = None,
         db: pathlib.Path | None = None, extra: dict | None = None) -> dict:
    """Write the lift into the journal.  Never raises; the record IS the permission.

    Returns {"recorded": bool, "guard", "reason", "who", "at", "attempt_id", "opid",
    "detail"}.  Callers must check `allows_action(rec)` before doing what the lifted
    guard was protecting.
    """
    rec = {"recorded": False, "guard": str(guard), "reason": str(reason or "unspecified"),
           "who": str(actor or who()), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "attempt_id": attempt_id, "opid": opid}
    if extra:
        rec["extra"] = extra
    path = pathlib.Path(db or DB_DEFAULT)
    try:
        import sys
        sys.path.insert(0, str(HERE))
        import store  # noqa: PLC0415 — local import keeps this module usable standalone
        conn = store.connect(path)
        try:
            store.event(conn, KIND, rec)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        rec["recorded"] = True
        rec["journal"] = str(path)
    except Exception as exc:  # noqa: BLE001 — fail-closed, but never crash the probe
        rec["detail"] = f"{type(exc).__name__}: {exc}"
    return rec


def allows_action(rec: dict | None) -> bool:
    """A lifted guard authorises its action ONLY if it was written down."""
    return bool(rec) and bool(rec.get("recorded"))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="record a lifted guard (or inspect them)")
    ap.add_argument("--guard", default="refusal_guard")
    ap.add_argument("--reason", default="")
    ap.add_argument("--attempt-id", default="")
    ap.add_argument("--opid", default="")
    ap.add_argument("--list", action="store_true", help="show recent lifts")
    a = ap.parse_args()
    if a.list:
        conn_path = DB_DEFAULT
        import sqlite3
        conn = sqlite3.connect(f"file:{conn_path}?mode=ro", uri=True)
        rows = conn.execute("SELECT ts, payload FROM events WHERE kind=? ORDER BY ts DESC LIMIT 20",
                            (KIND,)).fetchall()
        for ts, payload in rows:
            try:
                d = json.loads(payload or "{}")
            except Exception:  # noqa: BLE001
                d = {"raw": payload}
            print(f"  {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))} "
                  f"{d.get('guard')} by {d.get('who')}: {d.get('reason')} "
                  f"(attempt {d.get('attempt_id') or '—'})")
        if not rows:
            print("  no lifted guards recorded")
        return 0
    rec = lift(a.guard, reason=a.reason or "operator override", attempt_id=a.attempt_id,
               opid=a.opid)
    print(json.dumps(rec, ensure_ascii=False))
    return 0 if rec["recorded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
