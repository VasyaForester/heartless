#!/usr/bin/env python3
"""Shared board core (universalized 2026-11-13, RULES 65/67).

Single source for board facts used by BOTH the v2 driver and the retired v1
loop; everything comes from the board profile (boards/<name>.json via
boards.py) or from the modules the profile names:

  * scenarios, roster, solved seed, file prefixes/suffixes -> profile fields;
  * the delta catalog -> the module named by `deltas_module`;
  * the pre-submit check -> the module named by `checks_module` (used by lbp.py);
  * `SOLVED` is seed truth only - the driver re-confirms it from judge files.

Default board: lucky-break-payday ($HERMES_BOARD overrides).
"""
from __future__ import annotations

import glob
import importlib
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

from boards import load_board  # noqa: E402
import winquiet  # noqa: E402

LBP = HERE / "lbp.py"
BOARD = load_board()
BOARD_NAME = BOARD["name"]

# scenario id -> card title on the board
SCENARIOS = dict(BOARD.get("scenario_titles") or {})
MODELS = list(BOARD.get("models") or [])
MODELS_BY_SCENARIO = dict(BOARD.get("models_by_scenario") or {})


def models_for(sid: str) -> list:
    """Roster for a scenario: per-scenario override or the board default."""
    return list(MODELS_BY_SCENARIO.get(sid) or MODELS)


# Seed truth from the profile (`solved_seed`); solved cells are skipped by the
# driver and re-confirmed from judge files when present.
SOLVED = {sid: set(models or []) for sid, models in (BOARD.get("solved_seed") or {}).items()}
SCENARIO_PREFIX = dict(BOARD.get("scenario_prefixes") or {})
MODEL_SUFFIX = dict(BOARD.get("model_suffixes") or {})
FILE_PREFIX = str(BOARD.get("file_prefix") or "lbp")
DELTAS_MODULE = str(BOARD.get("deltas_module") or "deltas_payday")
CHECKS_MODULE = str(BOARD.get("checks_module") or "lbp_checks")
PAIRS_SEED = str(BOARD.get("pairs_seed") or "")
PAIR_STATUS = str(BOARD.get("pair_status") or "")

# Delta transforms = the mutation grammar (board-specific module).  Each takes
# the base text and returns a new text; the bandit learns which one pays off
# per pair.  A broken catalog must never crash the driver.
try:
    DELTAS = dict(importlib.import_module(DELTAS_MODULE).DELTAS)
except Exception as _exc:  # noqa: BLE001
    print(f"[lbcore] WARNING: cannot load deltas module {DELTAS_MODULE!r}: {_exc}",
          file=sys.stderr)
    DELTAS = {}


def sh(cmd, timeout=300, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace", cwd=cwd or str(WORK),
                       **winquiet.windowless_kwargs())
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def newest_input(sid, model):
    """Newest probe text for a scenario+model: suffix in the filename, prefix per scenario."""
    pre = SCENARIO_PREFIX.get(sid, sid)
    suf = MODEL_SUFFIX.get(model, "")
    pats = [f"{FILE_PREFIX}-{pre}-*{suf}.txt", f"{FILE_PREFIX}-{pre}-*.txt"]
    for pat in pats:
        cand = sorted(glob.glob(str(WORK / "inputs" / pat)), key=os.path.getmtime, reverse=True)
        # Exclude every generated variant ("loop" in the name) - a raw delta output
        # must never be promoted to a permanent base.
        cand = [c for c in cand if "loop" not in os.path.basename(c).lower()]
        if cand:
            return pathlib.Path(cand[0])
    return None


def judge_path(sid, model):
    """Judge receipt file for a pair (written by lbp.py, read by the driver)."""
    return WORK / "artifacts" / f"{FILE_PREFIX}-{sid}-{slug(model)}-judge.json"


def transcript_path(sid, model):
    """Submit-transcript file for a pair (written by lbp.py, read by the driver)."""
    return WORK / "artifacts" / f"{FILE_PREFIX}-{sid}-{slug(model)}-submit-transcript.json"


def loop_input_name(sid, delta, ts, rnd):
    """Generated variant filename (kept out of newest_input by the 'loop' marker)."""
    return f"{FILE_PREFIX}-{sid}-loop2-{delta}-{ts}-{rnd}.txt"
