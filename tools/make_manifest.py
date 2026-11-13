#!/usr/bin/env python3
"""Build the RunManifest for the current lane without restarting the supervisor.

The supervisor writes it automatically on its next start; this helper covers
the already-running supervisor (v3 rollout 2026-11-13).
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(WORK / "harness"))

import manifest  # noqa: E402

m = manifest.build(lane="main", cdp="127.0.0.1:9223",
                   browser_profile=WORK.parent / "browser-data")
print(json.dumps(m, ensure_ascii=False, indent=2))
print("validated:", manifest.validate(m, board_name="lucky-break-payday", lane="main",
                                     cdp="127.0.0.1:9223") or "OK")