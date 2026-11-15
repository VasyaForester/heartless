"""One journal, one reader: the live matrix comes from the database, always.

RULES 65 settled WHICH file is the truth (`artifacts/harness.db`) but left three
live readers counting pairs from the v1 journal `datasets/lbp/pairs.jsonl`:

  * `lbp_plan.py`  — the plan/matrix and its `--check`;
  * `lbp_report.py` — the per-model matrix, and it even WROTE the file back;
  * `lbp.py cmd_export` — the consolidated export.

Grok's review (2026-11-15, axis "one journal": 4/10) called that out and it is
right: a matrix computed from a file nobody writes any more can only drift away
from reality — and one of those readers was still writing it, so the archive was
quietly being treated as the present.  `pairs.jsonl` is an ARCHIVE now; nothing
live may read it as a matrix (enforced by `config_check.check_single_journal`).

Everything that needs the matrix calls `live_matrix()` here.  One query, one
shape, one renderer — so the plan, the report and the export cannot disagree.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
DB_DEFAULT = WORK / "artifacts" / "harness.db"

#: the shape every consumer may rely on (a superset of the legacy v1 row)
ROW_KEYS = ("scenario_id", "model_id", "board", "solved", "outcome", "attempts",
            "best_score", "last_verdict", "last_judge_status", "last_score",
            "last_activity", "version")


def _col(row, name):
    """Value of `name` in a sqlite3.Row (or None) — Row has no .get()."""
    if row is None:
        return None
    try:
        return row[name]
    except (IndexError, KeyError):
        return None


def connect(db=None) -> sqlite3.Connection:
    """Read-only connection to the live journal."""
    path = pathlib.Path(db or DB_DEFAULT)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def live_matrix(db=None, board: str | None = None) -> list[dict]:
    """One row per pair of `board` (all boards when None), straight from the DB.

    Live accounting = the `pairs` table (state) joined with the last rewarded
    attempt per pair (evidence).  Nothing here reads a JSONL journal.
    """
    conn = connect(db)
    try:
        sql = ("SELECT id, scenario, model, board_profile, solved, attempts,"
               " best_score, last_verdict, version FROM pairs")
        params: tuple = ()
        if board:
            sql += " WHERE board_profile=?"
            params = (board,)
        sql += " ORDER BY board_profile, scenario, model"
        rows = []
        for r in conn.execute(sql, params):
            last = conn.execute(
                "SELECT judge_status, score, started_at FROM attempts"
                " WHERE pair_id=? AND (judge_status IS NOT NULL OR score IS NOT NULL)"
                " ORDER BY COALESCE(started_at, 0) DESC, attempt_id DESC LIMIT 1",
                (r["id"],)).fetchone()
            rows.append({
                "scenario_id": r["scenario"],
                "model_id": r["model"],
                "board": r["board_profile"],
                "solved": bool(r["solved"]),
                "outcome": "SUCCESS" if r["solved"] else "OPEN",
                "attempts": int(r["attempts"] or 0),
                "best_score": r["best_score"],
                "last_verdict": r["last_verdict"],
                # sqlite3.Row has no .get(); index defensively instead
                "last_judge_status": _col(last, "judge_status"),
                "last_score": _col(last, "score"),
                "last_activity": _col(last, "started_at"),
                "version": r["version"],
            })
        return rows
    finally:
        conn.close()


def summary(rows: list[dict]) -> dict:
    """Counts per board, from the same rows the callers render."""
    out: dict = {"pairs": len(rows), "solved": 0, "by_board": {}}
    for r in rows:
        b = out["by_board"].setdefault(r["board"], {"pairs": 0, "solved": 0,
                                                    "attempts": 0,
                                                    "last_activity": None})
        b["pairs"] += 1
        b["attempts"] += int(r.get("attempts") or 0)
        if r["outcome"] == "SUCCESS":
            b["solved"] += 1
            out["solved"] += 1
        ts = r.get("last_activity")
        if ts and (b["last_activity"] is None or ts > b["last_activity"]):
            b["last_activity"] = ts
    return out


def render_markdown(rows: list[dict], *, title: str = "Consolidated export",
                    board: str | None = None) -> str:
    """The ONE renderer for the matrix, so plan/report/export cannot diverge."""
    s = summary(rows)
    lines = [f"# {title}", "",
             f"- Pairs solved: {s['solved']}/{s['pairs']}"
             + (f" (board {board})" if board else ""),
             f"- Generated: {time.strftime('%Y-%m-%d %H:%M')}",
             "- Source: artifacts/harness.db (the live journal);"
             " datasets/lbp/pairs.jsonl is an archive", ""]
    for bname, b in sorted(s["by_board"].items()):
        lines.append(f"## {bname}: {b['solved']}/{b['pairs']} solved, "
                     f"{b['attempts']} attempts")
        lines.append("")
    lines += ["## Scenario x model", "",
              "| board | scenario | model | outcome | attempts | best | last verdict |",
              "|---|---|---|---|---|---|---|"]
    for r in rows:
        best = "—" if r.get("best_score") is None else f"{float(r['best_score']):.3f}"
        lines.append(f"| {r['board']} | {r['scenario_id']} | {r['model_id']} | "
                     f"{r['outcome']} | {r['attempts']} | {best} | "
                     f"{r.get('last_verdict') or '—'} |")
    return "\n".join(lines) + "\n"


def as_jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="the live matrix (read-only)")
    ap.add_argument("--db", default="")
    ap.add_argument("--board", default="")
    ap.add_argument("--jsonl", action="store_true")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    rows = live_matrix(a.db or None, a.board or None)
    if a.jsonl:
        print(as_jsonl(rows), end="")
    elif a.md:
        print(render_markdown(rows, board=a.board or None), end="")
    else:
        s = summary(rows)
        print(f"{s['solved']}/{s['pairs']} pairs solved")
        for b, v in sorted(s["by_board"].items()):
            print(f"  {b}: {v['solved']}/{v['pairs']} solved, {v['attempts']} attempts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
