"""The reward audit must keep telling the truth: it is the tool that decides
whether the selector is allowed to learn from a probe at all."""

import json
import os
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import reward_audit  # noqa: E402


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "repeats.jsonl"

    def write(self, rows):
        self.path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def test_broken_lines_are_skipped_not_fatal(self):
        self.path.write_text('{"a": 1}\nnot json\n\n{"b": 2}\n', encoding="utf-8")
        rows = reward_audit.ledger_rows(self.path)
        self.assertEqual(len(rows), 2)

    def test_tail_keeps_the_newest(self):
        self.write([{"i": i} for i in range(10)])
        rows = reward_audit.ledger_rows(self.path, tail=3)
        self.assertEqual([r["i"] for r in rows], [7, 8, 9])

    def test_missing_file_is_empty_not_an_error(self):
        self.assertEqual(reward_audit.ledger_rows(pathlib.Path(self.tmp.name) / "nope.jsonl"), [])


class AuditTest(unittest.TestCase):
    def test_faults_and_levels_are_separated(self):
        rows = [
            {"probe_ok": False},                                        # our fault
            {"probe_ok": True, "tool_invoked": True, "fill_ok": False},  # our fault
            {"probe_ok": True, "fill_ok": True, "failure_class": "A_TOOL_NOT_CALLED",
             "refusal_category": "category_block"},                      # a real refusal
            {"probe_ok": True, "fill_ok": True, "tool_invoked": True,
             "check_ready": True, "failure_class": "NONE_READY"},        # a real near-win
        ]
        out = reward_audit.audit(rows)
        self.assertEqual(out["probes"], 4)
        self.assertEqual(out["faults"], {"probe_not_landed": 1, "toolcall_lost_in_fill": 1})
        self.assertEqual(out["valid_rewards"], 2)
        self.assertAlmostEqual(out["fault_rate"], 0.5)
        # the two valid probes must land on visibly different levels
        levels = [k for k in out["reward_levels"] if k != "none"]
        self.assertEqual(len(levels), 2)

    def test_calibration_says_when_it_lacks_evidence(self):
        rows = [{"probe_ok": True, "fill_ok": True, "tool_invoked": True,
                 "failure_class": "NONE_READY", "pcts": [100, 50]}]
        cal = reward_audit.calibrate(rows, db_path=pathlib.Path("does-not-exist.db"))
        self.assertEqual(cal["pairs"], 1)
        self.assertFalse(cal["enough_evidence"])
        # NONE_READY + a tool call is the top proxy level; the judge says 75%
        self.assertEqual(cal["by_level"]["0.85"]["mean_judge"], 0.75)
        self.assertEqual(cal["by_level"]["0.85"]["n"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
