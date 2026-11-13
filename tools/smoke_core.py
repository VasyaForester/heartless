#!/usr/bin/env python3
"""Smoke: lbcore loads scenarios from the board profile (accounting fix 2026-11-13)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "harness"))
import lbcore  # noqa: E402

print("board:", lbcore.BOARD_NAME)
print("url:", lbcore.BOARD["url"])
print("scenarios:", list(lbcore.SCENARIOS))
print("models:", len(lbcore.MODELS))
print("prefixes ok:", all(k in lbcore.SCENARIO_PREFIX for k in lbcore.SCENARIOS))
print("solved cells:", sum(len(v) for v in lbcore.SOLVED.values()))