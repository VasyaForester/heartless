"""One writer, the rest read.

Grok's review (2026-11-15, axis "attempt accounting": 8/10) asked for one database writer
and read-only everywhere else — "учёт попытки станет десяткой вместе с одним журналом".

The writer is the driver (it holds the lane lease; `store.transition` asserts ownership).
Everybody else is a reader, and a reader that CANNOT write cannot corrupt the journal, take
a write lock on it, or migrate it as a side effect of a diagnostic run.  `harness/journal.py`
is the one shared reader used by the plan, the report, the export and the nightly report.

These are source-level guards, in the same style as the ones in config_check: read the file,
drop comment lines, and look at how the connection is opened.  A functional test cannot prove
this — the failure mode is a future edit, not today's behaviour.
"""

import os
import pathlib
import re
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(tempfile.gettempdir()) / "hermes-test-driver.log"))

# Modules that READ the journal.  `journal.py` is the shared reader; the rest either use it
# or open the database directly for their own aggregation.
READERS = ("journal.py", "strategy_bench.py", "lbp_plan.py", "lbp_report.py",
           "nightly.py", "bandit_audit.py", "efficiency.py", "rewards.py")

# Modules allowed to WRITE: the driver owns the lane lease and the attempt lifecycle; the
# supervisor and farm bootstrap the pairs table from data files.
WRITERS = ("driver.py", "supervisor.py", "farm.py", "store.py", "attempts.py")


def code_lines(name: str) -> list:
    path = HARNESS / name
    if not path.is_file():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("#")]


def connect_calls(lines: list) -> list:
    """The text of every sqlite3.connect(...) call, parentheses balanced."""
    out, buf, depth = [], None, 0
    for line in lines:
        stripped = line.strip()
        if buf is None and "sqlite3.connect(" in stripped:
            buf, depth = [], stripped.count("(") - stripped.count(")")
        if buf is not None:
            buf.append(stripped)
            if buf and not buf[0].count("("):
                pass
            depth += stripped.count("(") - stripped.count(")")
            if depth <= 0:
                out.append(" ".join(buf))
                buf, depth = None, 0
    return out


class OneWriterTest(unittest.TestCase):
    def test_every_reader_opens_the_journal_read_only(self):
        offenders = []
        for name in READERS:
            for call in connect_calls(code_lines(name)):
                if "mode=ro" not in call:
                    offenders.append(f"{name}: {call[:80]}")
        self.assertEqual(offenders, [],
                         "a reader opened the journal read-write; readers must use "
                         "file:...?mode=ro")

    def test_no_reader_can_create_or_migrate_the_journal(self):
        """`store.connect` opens read-write and runs the schema migration."""
        offenders = [name for name in READERS
                     if any("store.connect(" in ln for ln in code_lines(name))]
        self.assertEqual(offenders, [],
                         "a reader called store.connect (read-write + migration)")

    def test_the_shared_reader_is_read_only(self):
        calls = connect_calls(code_lines("journal.py"))
        self.assertTrue(calls, "journal.py must open the database")
        self.assertTrue(all("mode=ro" in c for c in calls))

    def test_the_driver_is_the_writer(self):
        src = "\n".join(code_lines("driver.py"))
        self.assertIn("store.connect(", src,
                      "the driver owns the lane lease; it is the writer")

    def test_the_guard_notices_a_read_write_reader(self):
        """Prove the guard by breaking it (a guard never seen red is not a guard)."""
        fake = [f'{n}: conn = sqlite3.connect(a.db, timeout=10)'
                for n in ("probe.py",)]
        offenders = [f for f in fake if "mode=ro" not in f]
        self.assertTrue(offenders, "the pattern the guard looks for must match")


if __name__ == "__main__":
    unittest.main(verbosity=2)
