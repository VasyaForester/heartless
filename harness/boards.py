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

import functools
import json
import os
import pathlib
import hashlib

BOARD_DIR = pathlib.Path(__file__).resolve().parent.parent / "boards"
DEFAULT_BOARD = "lucky-break-payday"
REQUIRED = ("name", "board", "match", "url", "scenario_selector",
            "model_confirm", "win_string", "cost")
DICT_FIELDS = ("scenario_titles", "card_hints", "mock_signs")
SCHEMA_NAME = "schema"
SCHEMA_PATH = BOARD_DIR / f"{SCHEMA_NAME}.json"
_TYPE_OF = {"str": str, "int": int, "float": (int, float), "bool": bool,
            "list": list, "dict": dict}


@functools.lru_cache(maxsize=1)
def profile_schema() -> dict:
    """The machine-readable contract in boards/schema.json (empty if unreadable)."""
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _check_types(profile: dict, where: str) -> None:
    """Type-level validation driven by the schema, so the contract lives in ONE place.

    Unknown extra keys are allowed on purpose (a profile may carry notes), but a
    known key with the wrong type is a loud error: a typo like `"cost": 2` or a
    stringified list used to slip through and fail deep inside the driver.
    """
    props = (profile_schema().get("properties") or {})
    for key, spec in props.items():
        if key not in profile or not isinstance(spec, dict):
            continue
        want = _TYPE_OF.get(str(spec.get("type")))
        value = profile[key]
        if want is None or value is None:
            continue
        if isinstance(value, bool) and want is int:  # bool is an int subclass
            raise ValueError(f"board profile{where}: {key!r} must be int, got bool")
        if not isinstance(value, want):
            raise ValueError(f"board profile{where}: {key!r} must be "
                             f"{spec.get('type')}, got {type(value).__name__}")
        sub = spec.get("keys")
        if isinstance(sub, dict) and isinstance(value, dict):
            for sk, skind in sub.items():
                if sk in value and value[sk] is not None and \
                        not isinstance(value[sk], _TYPE_OF.get(str(skind), object)):
                    raise ValueError(f"board profile{where}: {key}.{sk} must be {skind}")


def list_boards() -> list[str]:
    """.json files in boards/, minus the profile SCHEMA itself (boards/schema.json)."""
    skip = {SCHEMA_NAME}
    return sorted(p.stem for p in BOARD_DIR.glob("*.json") if p.stem not in skip)


def validate(profile: dict, path: pathlib.Path | None = None) -> dict:
    where = f" ({path})" if path else ""
    schema_required = tuple(profile_schema().get("required") or REQUIRED)
    missing = [k for k in schema_required if k not in profile]
    if missing:
        raise ValueError(f"board profile{where} missing fields: {missing}")
    _check_types(profile, where)
    if profile.get("sandbox"):
        # An offline sandbox arena (e.g. fake-arena) is not a live target: it must
        # say so, and it is exempt from the live-URL rule.  Everything else about
        # the profile is validated exactly like a real board.
        if not str(profile.get("_note") or "").strip():
            raise ValueError(f"board profile{where}: sandbox boards need a _note")
        return profile
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