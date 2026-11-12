import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import supervisor  # noqa: E402


class SupervisorTest(unittest.TestCase):
    def test_single_instance_lock(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "supervisor.lock"
            self.assertIsNotNone(supervisor.acquire_lock(p))
            self.assertIsNone(supervisor.acquire_lock(p))
            supervisor.release_lock(p)
            self.assertFalse(p.exists())
            self.assertIsNotNone(supervisor.acquire_lock(p))
            supervisor.release_lock(p)

    def test_stale_lock_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "supervisor.lock"
            p.write_text('{"pid": 99999999}', encoding="utf-8")
            self.assertIsNotNone(supervisor.acquire_lock(p))
            supervisor.release_lock(p)


if __name__ == "__main__":
    unittest.main()