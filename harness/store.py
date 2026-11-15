#!/usr/bin/env python3
"""Reliability store for the LBP v2 driver.

This is the v2.1 replacement for the ad-hoc SQLite block in `driver.py`:
schema versioning, foreign keys, explicit transactions, fenced leases,
an append-only event log and an explicit attempt state machine.

Design rules:
  * SQLite is the single v2 truth; JSONL exports are derived.
  * A lease is a generation + random owner token, not just a pid.
  * Every state-changing write proves lease ownership inside the same
    `BEGIN IMMEDIATE` transaction that performs the write.
  * An expired worker cannot update pairs, attempts, events or solved state.
  * Judge correlation is stored as evidence, never as a guessed verdict.
"""
from __future__ import annotations

import ctypes
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass

SCHEMA_VERSION = 6
LEASE_TTL = 1800

# Explicit lifecycle.  `judged` is not final: only a verified judge may
# finalize a pair.  `submission_uncertain` is terminal and must never trigger
# a blind duplicate submission.
#
# v4 adds `unjudged`: the probe RAN but no judge was produced for it (the
# submit gate skipped the submission, or the pair judge file belongs to an
# earlier attempt).  It is NOT terminal — a late verdict may still arrive and
# bind to it through the judge ledger (judge_ledger.py).  Before v4 every such
# attempt fell into the terminal `judge_failed`, which destroyed the reward
# channel: 104/114 live attempts ended there and the bandit learned nothing.
TRANSITIONS = {
    "allocated": {"prepared", "execution_failed", "cancelled"},
    "prepared": {"submitted", "execution_failed", "cancelled"},
    "submitted": {"awaiting_judge", "judged", "unjudged", "submission_uncertain",
                  "execution_failed", "judge_failed"},
    "awaiting_judge": {"judged", "unjudged", "judge_failed", "cancelled"},
    "unjudged": {"judged", "judge_failed"},
    "judged": {"finalized", "judge_failed"},
    "finalized": set(),
    "execution_failed": set(),
    "submission_uncertain": set(),
    "judge_failed": set(),
    "cancelled": set(),
}
TERMINAL = {"finalized", "execution_failed", "submission_uncertain",
            "judge_failed", "cancelled"}
# Attempts that still may acquire a verdict later (never treated as settled).
OPEN_STATES = {"prepared", "submitted", "awaiting_judge", "unjudged"}

ALLOWED_FIELDS = {
    "execution_status", "judge_status", "chat_id", "submitted_at",
    "finished_at", "transcript_hash", "judge_ref", "judge_hash",
    "score", "pcts", "verdict", "input_path", "input_hash",
    "parent_input_hash", "delta", "delta_version", "seed", "nonce",
    "strategy_version", "parent_input_path", "reward", "reward_source",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS board_profiles (
  profile_id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL,
  url TEXT NOT NULL, win_string TEXT NOT NULL, profile_hash TEXT,
  loaded_at REAL
);
CREATE TABLE IF NOT EXISTS pairs (
  id TEXT PRIMARY KEY, board_profile TEXT NOT NULL DEFAULT 'default',
  scenario TEXT NOT NULL, model TEXT NOT NULL, model_version TEXT,
  solved INTEGER NOT NULL DEFAULT 0, solved_attempt TEXT,
  best_score INTEGER NOT NULL DEFAULT -1, best_input TEXT,
  latest_input TEXT, latest_attempt TEXT, best_attempt TEXT,
  attempts INTEGER NOT NULL DEFAULT 0, last_verdict TEXT,
  version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attempts (
  attempt_id TEXT PRIMARY KEY,
  pair_id TEXT NOT NULL REFERENCES pairs(id),
  board_profile TEXT NOT NULL,
  scenario TEXT NOT NULL, model TEXT NOT NULL, model_version TEXT,
  lane TEXT NOT NULL, chat_id TEXT,
  started_at REAL NOT NULL, submitted_at REAL, finished_at REAL,
  input_hash TEXT, transcript_hash TEXT,
  judge_ref TEXT, judge_hash TEXT,
  execution_status TEXT NOT NULL DEFAULT 'allocated',
  judge_status TEXT NOT NULL DEFAULT 'pending',
  state TEXT NOT NULL DEFAULT 'allocated',
  score INTEGER, pcts TEXT, verdict TEXT,
  parent_input_hash TEXT, delta TEXT, delta_version INTEGER,
  seed INTEGER, nonce TEXT, strategy_version INTEGER,
  input_path TEXT, parent_input_path TEXT,
  reward REAL, reward_source TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_pair ON attempts(pair_id);
CREATE INDEX IF NOT EXISTS idx_attempts_state ON attempts(state);
CREATE TABLE IF NOT EXISTS attempt_events (
  attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  seq INTEGER NOT NULL, ts REAL NOT NULL,
  from_state TEXT, to_state TEXT NOT NULL,
  kind TEXT NOT NULL, payload TEXT,
  PRIMARY KEY (attempt_id, seq)
);
CREATE TABLE IF NOT EXISTS judges (
  judge_ref TEXT PRIMARY KEY,
  attempt_id TEXT REFERENCES attempts(attempt_id),
  chat_id TEXT, operation_id TEXT,
  submitted_at TEXT, captured_at TEXT,
  status TEXT, score INTEGER, pcts TEXT,
  raw_path TEXT, raw_hash TEXT,
  verified INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_judges_operation ON judges(operation_id);
CREATE TABLE IF NOT EXISTS deltas (
  pair_id TEXT NOT NULL REFERENCES pairs(id),
  delta TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0,
  sum_score INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (pair_id, delta)
);
CREATE TABLE IF NOT EXISTS leases (
  lane TEXT PRIMARY KEY, pid INTEGER, target TEXT,
  generation INTEGER NOT NULL DEFAULT 0, owner_token TEXT,
  heartbeat REAL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL,
  kind TEXT NOT NULL, payload TEXT
);
"""


class LeaseLost(RuntimeError):
    """The worker no longer owns the lane lease."""


class InvalidTransition(RuntimeError):
    """Attempt state transition is not allowed."""


@dataclass(frozen=True)
class Lease:
    lane: str
    generation: int
    owner_token: str

    def as_dict(self) -> dict:
        return {"lane": self.lane, "generation": self.generation,
                "owner_token": self.owner_token}


def pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok and code.value == 259)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _create_v3(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migrate the driver's v2 schema in place; preserve old attempts."""
    pairs_cols = _columns(conn, "pairs")
    for col, ddl in (
        ("board_profile", "TEXT NOT NULL DEFAULT 'default'"),
        ("model_version", "TEXT"),
        ("solved_attempt", "TEXT"),
        ("version", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if col not in pairs_cols:
            conn.execute(f"ALTER TABLE pairs ADD COLUMN {col} {ddl}")

    lease_cols = _columns(conn, "leases")
    if "generation" not in lease_cols:
        conn.execute("ALTER TABLE leases ADD COLUMN generation INTEGER NOT NULL DEFAULT 0")
    if "owner_token" not in lease_cols:
        conn.execute("ALTER TABLE leases ADD COLUMN owner_token TEXT")

    if _table_exists(conn, "attempts"):
        conn.execute("ALTER TABLE attempts RENAME TO attempts_v2")
    _create_v3(conn)
    if _table_exists(conn, "attempts_v2"):
        conn.execute("""
            INSERT OR IGNORE INTO attempts(
              attempt_id,pair_id,board_profile,scenario,model,lane,started_at,
              finished_at,execution_status,judge_status,state,score,verdict,
              pcts,input_path)
            SELECT 'legacy-'||a.id, a.pair_id, 'lucky-break-payday',
                   p.scenario, p.model, 'legacy', a.started, a.finished,
                   CASE WHEN a.rc=0 THEN 'ok' ELSE 'failed' END,
                   'unverified',
                   CASE WHEN a.rc=0 THEN 'judged' ELSE 'execution_failed' END,
                   a.score, a.verdict, a.pcts, a.input
            FROM attempts_v2 a JOIN pairs p ON p.id=a.pair_id
        """)
    conn.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('version',?)",
                 (str(SCHEMA_VERSION),))


def _add_missing_columns(conn: sqlite3.Connection) -> list[str]:
    """Additive, idempotent migration: never drops or rewrites a column.

    v3 -> v4 adds the best/latest separation (advice 2026-11-13, critical #1:
    `best_input` used to be overwritten by every attempt, so the search base
    could degrade below the best confirmed probe) and the reward columns.
    """
    added = []
    plans = {
        "pairs": (
            ("latest_input", "TEXT"),
            ("latest_attempt", "TEXT"),
            ("best_attempt", "TEXT"),
        ),
        "attempts": (
            ("reward", "REAL"),
            ("reward_source", "TEXT"),
            # which arm the attempt came from: 'catalog' (a fixed delta),
            # 'generated' (a frame composed on the fly) or 'control_repeat'
            # (the randomized control of the generator experiment: re-probe the
            # best catalog delta instead of composing a new frame).
            ("arm_source", "TEXT"),
            # v4 -> v5 (Grok review 2026-11-15, axis "reproducibility": 8/10): a replay
            # needs to know WHICH board profile and WHICH model roster produced the
            # probe.  Without them the same nonce can be replayed against a different
            # profile and silently produce a different input.
            ("profile_hash", "TEXT"),
            ("models_hash", "TEXT"),
            # v5 -> v6 (Grok review 2026-11-15, axis "transport"): the attempt is bound
            # to ONE browser target for its whole life.  Recording it is what makes a
            # tab-id change visible as a NEW binding instead of a silent reuse.
            ("target_id", "TEXT"),
        ),
    }
    for table, cols in plans.items():
        if not _table_exists(conn, table):
            continue
        have = _columns(conn, table)
        for col, ddl in cols:
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
                added.append(f"{table}.{col}")
    if "latest_input" in {a.split(".")[1] for a in added}:
        # backfill: the last known input of a pair was whatever we used as base
        conn.execute("UPDATE pairs SET latest_input=best_input WHERE latest_input IS NULL")
    return added


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    version = int(row["value"]) if row else 0
    if version >= SCHEMA_VERSION:
        # still repair a partially created schema (cheap, idempotent)
        _add_missing_columns(conn)
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        if version == 0 and not _table_exists(conn, "pairs"):
            _create_v3(conn)
        elif version == 0:
            _migrate_v2_to_v3(conn)
        else:
            _create_v3(conn)  # idempotent: CREATE TABLE IF NOT EXISTS
        _add_missing_columns(conn)
        conn.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('version',?)",
                     (str(SCHEMA_VERSION),))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def connect(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    migrate(conn)
    return conn


def acquire_lease(conn: sqlite3.Connection, lane: str, target: str,
                  pid: int | None = None, ttl: int = LEASE_TTL) -> Lease | None:
    """Atomically acquire or renew a lane.  Returns None if another live worker owns it."""
    pid = int(pid if pid is not None else os.getpid())
    now = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT * FROM leases WHERE lane=?", (lane,)).fetchone()
        if row and now - float(row["heartbeat"] or 0) < ttl and pid_alive(int(row["pid"] or 0)) \
                and int(row["pid"] or 0) != pid:
            conn.rollback()
            return None
        generation = int(row["generation"] or 0) + 1 if row else 1
        token = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO leases(lane,pid,target,generation,owner_token,heartbeat)"
            " VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(lane) DO UPDATE SET pid=excluded.pid,target=excluded.target,"
            " generation=excluded.generation,owner_token=excluded.owner_token,"
            " heartbeat=excluded.heartbeat",
            (lane, pid, target, generation, token, now))
        conn.commit()
        return Lease(lane, generation, token)
    except Exception:
        conn.rollback()
        raise


def assert_owner(conn: sqlite3.Connection, lease: Lease, ttl: int = LEASE_TTL) -> None:
    row = conn.execute("SELECT generation,owner_token,heartbeat FROM leases WHERE lane=?",
                       (lease.lane,)).fetchone()
    if not row:
        raise LeaseLost(f"no lease for lane {lease.lane}")
    if int(row["generation"]) != lease.generation or row["owner_token"] != lease.owner_token:
        raise LeaseLost("lease generation/token changed")
    if time.time() - float(row["heartbeat"] or 0) > ttl:
        raise LeaseLost("lease expired")


def heartbeat(conn: sqlite3.Connection, lease: Lease) -> None:
    cur = conn.execute(
        "UPDATE leases SET heartbeat=? WHERE lane=? AND generation=? AND owner_token=?",
        (time.time(), lease.lane, lease.generation, lease.owner_token))
    if cur.rowcount != 1:
        raise LeaseLost("heartbeat: lease is no longer ours")


def release(conn: sqlite3.Connection, lease: Lease) -> None:
    try:
        conn.execute("DELETE FROM leases WHERE lane=? AND generation=? AND owner_token=?",
                     (lease.lane, lease.generation, lease.owner_token))
    except sqlite3.Error:
        pass


def last_event(conn: sqlite3.Connection, kind: str) -> dict | None:
    """The newest payload of a kind (used for bindings that must not be reused silently)."""
    import json
    row = conn.execute("SELECT payload FROM events WHERE kind=? ORDER BY id DESC LIMIT 1",
                       (kind,)).fetchone()
    if not row or row["payload"] is None:
        return None
    try:
        return json.loads(row["payload"])
    except Exception:  # noqa: BLE001 — a corrupt row is not a reason to stop a lane
        return None


def event(conn: sqlite3.Connection, kind: str, payload=None) -> None:
    import json
    conn.execute("INSERT INTO events(ts,kind,payload) VALUES(?,?,?)",
                 (time.time(), kind, json.dumps(payload, ensure_ascii=False) if payload is not None else None))


def transition(conn: sqlite3.Connection, lease: Lease, attempt_id: str,
               to_state: str, *, kind: str = "transition", payload=None,
               **fields) -> None:
    """Transactional, fenced state transition + append-only event."""
    import json
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        row = conn.execute("SELECT state FROM attempts WHERE attempt_id=?",
                           (attempt_id,)).fetchone()
        if not row:
            raise InvalidTransition(f"attempt {attempt_id} not found")
        cur = row["state"]
        if to_state not in TRANSITIONS.get(cur, set()):
            raise InvalidTransition(f"{cur} -> {to_state} is not allowed")
        sets = ["state=?"]
        params: list = [to_state]
        for key, value in fields.items():
            if key in ALLOWED_FIELDS:
                sets.append(f"{key}=?")
                params.append(value)
        if "finished_at" not in fields and to_state in TERMINAL:
            sets.append("finished_at=?")
            params.append(time.time())
        params.append(attempt_id)
        cur2 = conn.execute(f"UPDATE attempts SET {','.join(sets)} WHERE attempt_id=?",
                            params)
        if cur2.rowcount != 1:
            raise LeaseLost("attempt update affected no rows")
        seq = conn.execute(
            "SELECT COALESCE(MAX(seq),0)+1 AS s FROM attempt_events WHERE attempt_id=?",
            (attempt_id,)).fetchone()["s"]
        conn.execute(
            "INSERT INTO attempt_events(attempt_id,seq,ts,from_state,to_state,kind,payload)"
            " VALUES(?,?,?,?,?,?,?)",
            (attempt_id, seq, time.time(), cur, to_state, kind,
             json.dumps(payload, ensure_ascii=False) if payload is not None else None))
        event(conn, "attempt_transition",
              {"attempt_id": attempt_id, "from": cur, "to": to_state, "kind": kind})
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def insert_attempt(conn: sqlite3.Connection, lease: Lease, attempt: dict) -> None:
    import json
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        cols = ["attempt_id", "pair_id", "board_profile", "scenario", "model",
                "model_version", "lane", "chat_id", "started_at", "state",
                "input_path", "profile_hash", "models_hash", "target_id"]
        vals = [(attempt.get("state") or "allocated") if c == "state" else attempt.get(c)
                for c in cols]
        conn.execute(f"INSERT INTO attempts({','.join(cols)}) VALUES({','.join('?'*len(cols))})",
                     vals)
        conn.execute(
            "INSERT INTO attempt_events(attempt_id,seq,ts,from_state,to_state,kind,payload)"
            " VALUES(?,?,?,?,?,?,?)",
            (attempt["attempt_id"], 1, time.time(), None, "allocated", "allocated",
             json.dumps(attempt, ensure_ascii=False, default=str)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def record_judge(conn: sqlite3.Connection, lease: Lease, attempt_id: str,
                 judge_ref: str, *, chat_id=None, operation_id=None,
                 submitted_at=None, captured_at=None, status=None, score=None,
                 pcts=None, raw_path=None, raw_hash=None, verified=False) -> None:
    import json
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        conn.execute(
            "INSERT OR REPLACE INTO judges(judge_ref,attempt_id,chat_id,operation_id,"
            "submitted_at,captured_at,status,score,pcts,raw_path,raw_hash,verified,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (judge_ref, attempt_id, chat_id, operation_id, submitted_at, captured_at,
             status, score, json.dumps(pcts) if pcts is not None else None,
             raw_path, raw_hash, 1 if verified else 0, time.time()))
        conn.execute(
            "UPDATE attempts SET judge_ref=?,judge_hash=?,judge_status=?,score=?,pcts=?"
            " WHERE attempt_id=?",
            (judge_ref, raw_hash, "verified" if verified else (status or "pending"),
             score, json.dumps(pcts) if pcts is not None else None, attempt_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def finalize_attempt(conn: sqlite3.Connection, lease: Lease, attempt_id: str,
                     *, solved: bool) -> None:
    """Finalize a judged attempt and update the pair in one transaction.

    An unverified judge can never reach this function: the state machine
    requires `judge_status == 'verified'`.
    """
    import json
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        row = conn.execute(
            "SELECT a.*, p.best_score AS p_best, p.solved AS p_solved,"
            " p.attempts AS p_attempts, p.solved_attempt AS p_solved_attempt"
            " FROM attempts a JOIN pairs p ON p.id=a.pair_id"
            " WHERE a.attempt_id=?", (attempt_id,)).fetchone()
        if not row:
            raise InvalidTransition(f"attempt {attempt_id} not found")
        if row["state"] != "judged":
            raise InvalidTransition(f"cannot finalize from {row['state']}")
        if row["judge_status"] != "verified":
            raise InvalidTransition("unverified judge cannot finalize")
        conn.execute("UPDATE attempts SET state='finalized',finished_at=? WHERE attempt_id=?",
                     (time.time(), attempt_id))
        seq = conn.execute(
            "SELECT COALESCE(MAX(seq),0)+1 AS s FROM attempt_events WHERE attempt_id=?",
            (attempt_id,)).fetchone()["s"]
        conn.execute(
            "INSERT INTO attempt_events(attempt_id,seq,ts,from_state,to_state,kind,payload)"
            " VALUES(?,?,?,?,?,?,?)",
            (attempt_id, seq, time.time(), "judged", "finalized", "finalize",
             json.dumps({"solved": solved, "score": row["score"]}, ensure_ascii=False)))
        best = int(row["score"]) if row["score"] is not None else -1
        new_best = max(int(row["p_best"] or -1), best)
        # Critical fix (advice 2026-11-13 #1): `best_input` is the search base of
        # the next variant.  Before v4 it was overwritten by EVERY attempt, so a
        # weak probe could replace the best confirmed one and the search regressed.
        # Now: latest_* always tracks the newest probe, best_* only advances on a
        # real improvement of the objective metric.
        improved = best > int(row["p_best"] or -1)
        prev_best_input = conn.execute(
            "SELECT best_input FROM pairs WHERE id=?", (row["pair_id"],)).fetchone()
        best_input = row["input_path"] if improved else (prev_best_input["best_input"]
                                                         if prev_best_input else None)
        best_attempt = attempt_id if improved else None
        conn.execute(
            "UPDATE pairs SET attempts=attempts+1,last_verdict=?,solved=?,"
            "solved_attempt=?,best_score=?,best_input=?,"
            "latest_input=?,latest_attempt=?,"
            "best_attempt=COALESCE(?,best_attempt),version=version+1 WHERE id=?",
            (row["verdict"], 1 if solved else int(row["p_solved"] or 0),
             attempt_id if solved else row["p_solved_attempt"],
             new_best, best_input,
             row["input_path"], attempt_id,
             best_attempt, row["pair_id"]))
        if row["delta"]:
            conn.execute(
                "INSERT INTO deltas(pair_id,delta,n,sum_score) VALUES(?,?,1,?)"
                " ON CONFLICT(pair_id,delta) DO UPDATE SET"
                " n=n+1,sum_score=sum_score+excluded.sum_score",
                (row["pair_id"], row["delta"], best))
        event(conn, "attempt_finalized", {"attempt_id": attempt_id, "solved": solved,
                                          "score": row["score"]})
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def known_judge_operations(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["operation_id"]: r["attempt_id"] for r in conn.execute(
        "SELECT operation_id,attempt_id FROM judges WHERE operation_id IS NOT NULL")}


def judge_for_operation(conn: sqlite3.Connection, operation_id: str):
    """The judge row bound to an operation id, if any (v4 attribution)."""
    return conn.execute(
        "SELECT * FROM judges WHERE operation_id=? ORDER BY created_at DESC LIMIT 1",
        (operation_id,)).fetchone()


def set_reward(conn: sqlite3.Connection, lease: Lease, attempt_id: str,
               reward: float | None, source: str) -> None:
    """Persist the bandit reward of an attempt (judge score or local proxy).

    The reward is the ONLY channel the selector learns from, so it is stored
    explicitly instead of being recomputed from a possibly-rotated judge file.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        conn.execute("UPDATE attempts SET reward=?,reward_source=? WHERE attempt_id=?",
                     (None if reward is None else float(reward), source, attempt_id))
        event(conn, "attempt_reward", {"attempt_id": attempt_id, "reward": reward,
                                       "source": source})
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def bump_delta(conn: sqlite3.Connection, lease: Lease, pair_id: str, delta: str,
               reward: float | None) -> None:
    """Update per-(pair, delta) statistics from any rewarded attempt.

    `finalize_attempt` only runs for verified judges; on this arena almost no
    probe reaches one, so the statistics would stay frozen at the seed.  The
    selector needs the counts from every rewarded probe (v4).
    """
    if not delta:
        return
    value = int(round(float(reward) * 100)) if reward is not None else 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        conn.execute(
            "INSERT INTO deltas(pair_id,delta,n,sum_score) VALUES(?,?,1,?)"
            " ON CONFLICT(pair_id,delta) DO UPDATE SET n=n+1,sum_score=sum_score+excluded.sum_score",
            (pair_id, delta, value))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def set_arm_source(conn: sqlite3.Connection, lease: Lease, attempt_id: str,
                   source: str) -> None:
    """Tag where the arm came from (catalog | generated | control_repeat).

    Needed by the generator experiment: without the tag a re-probe of a known
    delta and a freshly composed frame are indistinguishable in the ledger, so
    "does generation pay off?" could never be answered from live data (the
    offline bench cannot answer it either — a brand-new frame has no reward by
    construction).
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        assert_owner(conn, lease)
        conn.execute("UPDATE attempts SET arm_source=? WHERE attempt_id=?",
                     (source, attempt_id))
        event(conn, "arm_source", {"attempt_id": attempt_id, "source": source})
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_attempt(conn: sqlite3.Connection, attempt_id: str):
    return conn.execute("SELECT * FROM attempts WHERE attempt_id=?", (attempt_id,)).fetchone()


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    return int(row["value"]) if row else 0


def insert_board_profile(conn: sqlite3.Connection, profile: dict, profile_hash: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO board_profiles(profile_id,name,version,url,win_string,"
        "profile_hash,loaded_at) VALUES(?,?,?,?,?,?,?)",
        (f"{profile['name']}@{profile.get('schema',1)}", profile["name"],
         int(profile.get("schema", 1)), profile["url"], profile["win_string"],
         profile_hash, time.time()))