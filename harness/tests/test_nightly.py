"""The night must be able to finish what it started, unattended.

Tested here: the pre-registered A/B action (the only thing that mutates live
configuration without a human in the loop), its once-only guard, and the lane
health reading that decides whether to touch the lane at all.
"""

import json
import os
import pathlib
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import nightly  # noqa: E402


class DecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.art = pathlib.Path(self.tmp.name) / "artifacts"
        self.art.mkdir(parents=True)
        self._saved = (nightly.ARTIFACTS, nightly.AB_DECISION, nightly.FLAGS)
        nightly.ARTIFACTS = self.art
        nightly.AB_DECISION = self.art / "ab-decision.json"
        nightly.FLAGS = self.art / "lane-flags.json"
        self.FLAGS = nightly.FLAGS
        self.AB_DECISION = nightly.AB_DECISION

    def tearDown(self):
        nightly.ARTIFACTS, nightly.AB_DECISION, nightly.FLAGS = self._saved
        self.tmp.cleanup()

    def write_flags(self, data):
        self.FLAGS.write_text(json.dumps(data), encoding="utf-8")

    def test_losing_generator_is_turned_off(self):
        self.write_flags({"strategy": "contextual_ts", "ab_generate": 0.5})
        out = nightly.apply_decision("control_repeat", dry_run=False)
        self.assertIn("applied", out["action"])
        flags = json.loads(self.FLAGS.read_text(encoding="utf-8"))
        self.assertEqual(flags["generate"], "off")
        self.assertEqual(flags["strategy"], "contextual_ts", "other flags untouched")
        self.assertTrue((self.art / "restart.requested").is_file())

    def test_winning_generator_changes_nothing(self):
        self.write_flags({"strategy": "contextual_ts", "ab_generate": 0.5})
        out = nightly.apply_decision("generated", dry_run=False)
        self.assertEqual(out["action"], "recorded")
        flags = json.loads(self.FLAGS.read_text(encoding="utf-8"))
        self.assertNotIn("generate", flags)

    def test_a_decision_is_applied_at_most_once(self):
        self.write_flags({})
        nightly.apply_decision("control_repeat", dry_run=False)
        again = nightly.apply_decision("control_repeat", dry_run=False)
        self.assertIn("already decided", again["action"])

    def test_dry_run_never_writes(self):
        self.write_flags({"ab_generate": 0.5})
        out = nightly.apply_decision("control_repeat", dry_run=True)
        self.assertIn("dry-run", out["action"])
        flags = json.loads(self.FLAGS.read_text(encoding="utf-8"))
        self.assertNotIn("generate", flags)
        self.assertFalse((self.art / "restart.requested").is_file())
        self.assertFalse(self.AB_DECISION.is_file())


class LaneHealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.art = pathlib.Path(self.tmp.name) / "artifacts"
        self.art.mkdir(parents=True)
        self._saved = (nightly.ARTIFACTS, nightly.LOCK, nightly.DRIVER_LOG)
        nightly.ARTIFACTS = self.art
        nightly.LOCK = self.art / "supervisor.lock"
        nightly.DRIVER_LOG = self.art / "driver.log"
        self.LOCK = nightly.LOCK
        self.DRIVER_LOG = nightly.DRIVER_LOG

    def tearDown(self):
        nightly.ARTIFACTS, nightly.LOCK, nightly.DRIVER_LOG = self._saved
        self.tmp.cleanup()

    def test_missing_lock_reads_as_not_alive(self):
        h = nightly.lane_health()
        self.assertFalse(h["alive"])
        self.assertIn("not alive", h["note"])

    def test_a_pause_flag_stops_any_restart(self):
        (self.art / "supervisor.paused").touch()
        h = nightly.lane_health()
        self.assertTrue(h["paused"])
        self.assertIn("paused", h["note"])
        self.assertFalse(nightly.maybe_restart(h, dry_run=True)["restarted"])

    def test_fresh_log_is_healthy(self):
        self.LOCK.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        self.DRIVER_LOG.write_text("x", encoding="utf-8")
        h = nightly.lane_health()
        self.assertTrue(h["alive"])
        self.assertLess(h["log_age_s"], 60)
        self.assertFalse(nightly.maybe_restart(h, dry_run=True)["restarted"])

    def test_a_stale_log_with_a_live_supervisor_is_left_to_the_watchdog(self):
        self.LOCK.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        self.DRIVER_LOG.write_text("x", encoding="utf-8")
        old = time.time() - 3 * nightly.STALE_LANE_S
        os.utime(self.DRIVER_LOG, (old, old))
        h = nightly.lane_health()
        self.assertTrue(h["alive"])
        out = nightly.maybe_restart(h, dry_run=True)
        self.assertFalse(out["restarted"])
        self.assertIn("watchdog", out["why"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
