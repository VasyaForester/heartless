#!/usr/bin/env python3
"""Online candidate learning (2026-11-15, P0 из разбора ChatGPT).

Проблема: ComponentModel пересобирается на каждый вызов генерации, но набор
наблюдений (`gen_rows`) считался ОДИН раз при старте драйвера — попытки,
сделанные в течение смены, не влияли на последующие предложения.

`LiveObservations` держит watermark по rowid в `artifacts/candidate-live.json`
и подмешивает только НОВЫЕ rewarded-попытки (и разобранные generated-кадры).
Список наблюдений мутируется на месте — его же использует driver.

Usage:
    python3 harness/online_learning.py --selftest
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import frames  # noqa: E402

STATE_PATH = WORK / "artifacts" / "candidate-live.json"


class LiveObservations:
    """Append-only view of rewarded attempts, with a persisted rowid watermark."""

    def __init__(self, conn: sqlite3.Connection, rows: list, *, min_new: int = 1,
                 state_path: pathlib.Path | None = None, board: str | None = None):
        self.conn = conn
        self.rows = rows
        self.min_new = max(1, int(min_new))
        self.state_path = pathlib.Path(state_path or STATE_PATH)
        self.board = board
        self._board_col = self._has_column("attempts", "board_profile")
        self.watermark = self._load_watermark()
        self.pulled_total = 0

    def _has_column(self, table: str, col: str) -> bool:
        try:
            return any(r[1] == col for r in self.conn.execute(f"PRAGMA table_info({table})"))
        except Exception:
            return False

    def _max_rowid(self) -> int:
        try:
            r = self.conn.execute("SELECT MAX(rowid) FROM attempts").fetchone()
            return int((r[0] if r is not None else 0) or 0)
        except Exception:
            return 0

    def _load_watermark(self) -> int:
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
            w = int(d.get("watermark") or 0)
        except Exception:
            w = 0
        # первый запуск: не пересчитывать уже вошедшие в стартовый fit строки
        return w or self._max_rowid()

    def _save(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(
                {"watermark": self.watermark, "pulled_total": self.pulled_total,
                 "updated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                 "rows": len(self.rows)}, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def pull(self) -> int:
        """Append new rewarded observations; return how many were added."""
        q = ("SELECT rowid AS rid, pair_id, delta, reward FROM attempts "
             "WHERE rowid > ? AND reward IS NOT NULL")
        params: list = [self.watermark]
        if self.board and self._board_col:
            q += " AND board_profile=?"
            params.append(self.board)
        q += " ORDER BY rowid"
        new_rows = []
        try:
            cur = self.conn.execute(q, tuple(params))
        except Exception:
            return 0
        for r in cur:
            rid, pid, delta, reward = r[0], r[1], r[2], r[3]
            spec = frames.decompose(delta)
            if not spec:
                continue
            ctx = f"{self.board}|{pid}" if self.board else str(pid)
            new_rows.append({"context": ctx, "spec": spec, "reward": float(reward)})
            self.watermark = max(self.watermark, int(rid))
        if len(new_rows) < self.min_new:
            # watermark не двигаем, если набрали меньше порога — накопим
            if not new_rows:
                return 0
        # даже меньше порога двигаем: строки уже прочитаны и добавлены
        self.rows.extend(new_rows)
        self.pulled_total += len(new_rows)
        self._save()
        return len(new_rows)


def _selftest() -> int:
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp())
    db = tmp / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE attempts (pair_id TEXT, delta TEXT, reward REAL)")
    conn.execute("INSERT INTO attempts VALUES ('negq|SA', 'append_policy', 0.2)")
    conn.commit()
    rows: list = []
    live = LiveObservations(conn, rows, state_path=tmp / "state.json", board="lbp")
    assert live.pull() == 0, "стартовый watermark должен исключать старые строки"
    conn.execute("INSERT INTO attempts VALUES ('negq|SA', 'gen.audit.prose_pre.keep_verbatim', 0.6)")
    conn.commit()
    n = live.pull()
    assert n == 1 and len(rows) == 1, (n, rows)
    assert rows[0]["spec"] == ("audit", "prose_pre", "keep_verbatim"), rows[0]
    # второй pull не дублирует
    assert live.pull() == 0 and len(rows) == 1
    # состояние переживает перезапуск
    live2 = LiveObservations(conn, [], state_path=tmp / "state.json", board="lbp")
    assert live2.pull() == 0
    conn.close()
    print("online_learning selftest OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print(__doc__)