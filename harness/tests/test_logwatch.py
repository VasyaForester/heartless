"""The lane watchdog must count ITS OWN lane, not raw bytes.

`artifacts/driver.log` is written by every lane (main writes `:main:`, pg writes
`:pg:`), so a size/mtime watchdog sees the other lane's chatter as progress and
can leave a wedged driver running (measured 2026-11-14).
"""

import os
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

import logwatch  # noqa: E402


class LaneProgressTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = pathlib.Path(self.tmp.name) / "driver.log"

    def write(self, text):
        with self.log.open("a", encoding="utf-8") as f:
            f.write(text)

    def test_counts_only_this_lane(self):
        self.write("[t] ATTEMPT lucky-break-payday:x:Model:main:abc delta=d energy=1000\n")
        self.write("[t] ATTEMPT proving-ground:y:Model:pg:def delta=d energy=1000\n")
        self.write("[t] ATTEMPT lucky-break-payday:z:Model:main:ghi delta=d energy=1000\n")
        self.assertEqual(logwatch.lane_progress(self.log, "main"), 2)
        self.assertEqual(logwatch.lane_progress(self.log, "pg"), 1)

    def test_another_lane_writing_does_not_count_as_progress(self):
        """The exact masking failure: pg keeps logging, main is wedged."""
        self.write("[t] ATTEMPT a:b:Model:main:1 delta=d\n")
        baseline = logwatch.lane_progress(self.log, "main")
        for i in range(5):
            self.write(f"[t] ATTEMPT p:q:Model:pg:{i} delta=d\n")
        self.assertEqual(logwatch.lane_progress(self.log, "main"), baseline,
                         "foreign-lane lines must not look like main-lane progress")

    def test_counts_the_lane_field_too(self):
        self.write("[t] DRIVER START lane=main target=ABC pid=1\n")
        self.assertGreaterEqual(logwatch.lane_progress(self.log, "main"), 1)

    def test_missing_file_is_not_progress(self):
        self.assertEqual(logwatch.lane_progress(pathlib.Path(self.tmp.name) / "nope.log", "main"), -1)

    def test_tail_window_does_not_crash_on_a_big_file(self):
        self.write("\n".join(f"[t] ATTEMPT a:b:Model:main:{i} delta=d" for i in range(5000)))
        self.assertGreater(logwatch.lane_progress(self.log, "main", tail_bytes=4096), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
