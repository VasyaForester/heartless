#!/usr/bin/env python3
"""Board profiles: one data object per arena board, no board logic in transport.

A profile tells the runner:
  - which board URL to use
  - how a scenario is selected (card click vs ?behaviorId=)
  - how to confirm the model (Attacking: line)
  - which page string means a win
  - what a message and a judge cost

The profiles are intentionally data-only.  `hackathon.py` stays a transport
(CDP/tab/fill/send/judge); `lbp.py`, `farm.py`, `chat_ops.py` and the v2
driver read board facts from here instead of carrying their own constants.
"""
from __future__ import annotations

import json
import os
import pathlib
import hashlib

BOARD_DIR = pathlib.Path(__file__).resolve().parent.parent / "boards"
DEFAULT_BOARD = "lucky-break-payday"
REQUIRED = ("name", "board", "match", "url", "scenario_selector",
            "model_confirm", "win_string", "cost")
DICT_FIELDS = ("scenario_titles", "card_hints", "mock_signs")


def list_boards() -> list[str]:
    return sorted(p.stem for p in BOARD_DIR.glob("*.json"))


def validate(profile: dict, path: pathlib.Path | None = None) -> dict:
    where = f" ({path})" if path else ""
    missing = [k for k in REQUIRED if k not in profile]
    if missing:
        raise ValueError(f"board profile{where} missing fields: {missing}")
    if not str(profile["url"]).startswith("https://app.grayswan.ai/arena/challenge/"):
        raise ValueError(f"board profile{where}: url must be an arena challenge URL")
    cost = profile["cost"]
    if not isinstance(cost, dict) or not {"message", "judge"} <= set(cost):
        raise ValueError(f"board profile{where}: cost must have message and judge")
    for field in DICT_FIELDS:
        if not isinstance(profile.get(field, {}), dict):
            raise ValueError(f"board profile{where}: {field} must be an object")
    return profile


def load_board(name: str | None = None) -> dict:
    """Load a board profile.  Name defaults to $HERMES_BOARD or Payday."""
    name = name or os.environ.get("HERMES_BOARD") or DEFAULT_BOARD
    path = BOARD_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"unknown board {name!r}; known: {list_boards()}")
    profile = validate(json.loads(path.read_text(encoding="utf-8")), path)
    profile["_profile_version"] = int(profile.get("schema", 1))
    profile["_profile_hash"] = hashlib.sha256(
        json.dumps(profile, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return profile


def active_board() -> dict:
    return load_board(os.environ.get("HERMES_BOARD") or DEFAULT_BOARD)


if __name__ == "__main__":
    for name in list_boards():
        p = load_board(name)
        print(f"{name}: {p['board']} {p['url']} win={p['win_string']!r} "
              f"scenarios={len(p.get('scenario_titles', {}))}")