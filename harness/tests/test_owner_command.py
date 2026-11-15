#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RULES 0 — the owner's standing order — is enforced, not just written.

Owner's order (verbatim, 2026-11-15): "если я дал команду решать, то не надо
останавливаться, пока я не скажу иного. не надо давать отчетов по сделанному,
жаловаться на стены, ротации и т. д. надо просто решать".

Written words rot; these tests make the order mechanical:
  1. the order is present in RULES.md (and in the check that fails the build without it);
  2. NOTHING in harness/ or tools/ can pause the lane by itself — the pause flag is the
     owner's hand, never a code path;
  3. the keeper starts the lane with no time limit and its ONLY stop condition is the
     owner's flag;
  4. `max_hours = 0` keeps meaning "unlimited".
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
W = HERE.parent.parent
sys.path.insert(0, str(W / "harness"))

import config_check  # noqa: E402

PAUSE_FLAGS = ("supervisor.paused", "loop.paused")
WRITE_RE = re.compile(r"write_text|open\([^)]*['\"][wa]|\.touch\(|\bunlink\(")


class OwnerOrderTest(unittest.TestCase):
    def test_the_order_is_in_the_rules(self):
        text = (W / "RULES.md").read_text(encoding="utf-8", errors="replace")
        self.assertIn("ПРИКАЗ ВЛАДЕЛЬЦА", text,
                      "RULES 0 — the owner's standing order — must sit above every other rule")
        self.assertIn("СТОЯЧИЙ РЕЖИМ", text,
                      "the section must say what it is: a standing mode, not a task")

    def test_the_build_fails_without_the_order(self):
        result = config_check.check_owner_order()
        self.assertTrue(result["ok"], f"config_check refuses the tree: {result['detail']}")

    def test_no_source_can_pause_the_lane_by_itself(self):
        offenders = []
        for base in ("harness", "tools"):
            for path in sorted((W / base).glob("*.py")):
                if path.name.startswith("_") or "tests" in path.parts:
                    continue
                for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    for flag in PAUSE_FLAGS:
                        if flag in line and WRITE_RE.search(line):
                            offenders.append(f"{base}/{path.name}:{n} {flag}")
        self.assertEqual(offenders, [],
                         "only the OWNER pauses the lane: a code path that writes the pause "
                         "flag would stop the work without an order")

    def test_the_keeper_restarts_without_a_time_limit(self):
        keeper = pathlib.Path.home() / "AppData" / "Local" / "hermes" / "scripts" / "v3_keeper.sh"
        if not keeper.is_file():
            self.skipTest("keeper script is not on this machine")
        text = keeper.read_text(encoding="utf-8", errors="replace")
        self.assertIn("--max-hours 0", text, "the keeper must not pass a time limit")
        self.assertIn("supervisor.paused", text,
                      "the keeper's only stop condition is the owner's flag")
        self.assertEqual(len(re.findall(r"\[\s*-f\s+\"[^\"]*\.paused\"\s*\]", text)), 1,
                         "exactly one pause flag guards the keeper; a second one could stop "
                         "the lane without the owner")

    def test_zero_max_hours_means_unlimited(self):
        driver = (W / "harness" / "driver.py").read_text(encoding="utf-8", errors="replace")
        self.assertIn("if a.max_hours and time.time() - started >= a.max_hours * 3600:", driver,
                      "0/None must keep meaning 'no time limit' — if the semantics changed on "
                      "purpose, update RULES 0 and this guard in the same commit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
