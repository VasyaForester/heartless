import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import attempts  # noqa: E402
import generation  # noqa: E402
import replay  # noqa: E402
import store  # noqa: E402


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.conn = store.connect(self.dir / "h.db")
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES('s|m','lucky-break-payday','s','m')")
        self.conn.commit()
        self.lease = store.acquire_lease(self.conn, "test", "tab", pid=os.getpid())

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_generation_is_deterministic(self):
        a = generation.generate("base text", "append_nonce", "n1")
        b = generation.generate("base text", "append_nonce", "n1")
        c = generation.generate("base text", "append_nonce", "n2")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_offline_replay_matches_hash(self):
        base = self.dir / "base.txt"
        base.write_text("base text", encoding="utf-8")
        text = generation.generate("base text", "append_nonce", "n1")
        out = self.dir / "out.txt"
        out.write_text(text, encoding="utf-8")
        aid = attempts.allocate(self.conn, self.lease, pair_id="s|m",
                                board="lucky-break-payday", scenario="s", model="m",
                                lane="test")
        attempts.prepare(self.conn, self.lease, aid, input_text=text,
                         input_path=str(out), parent_input_path=str(base),
                         parent_input_hash=attempts.sha256_text("base text"),
                         delta="append_nonce", delta_version=1, nonce="n1")
        result = replay.replay(self.conn, aid)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["replayed_input_hash"], result["expected_input_hash"])

    def test_missing_metadata_reported(self):
        aid = attempts.allocate(self.conn, self.lease, pair_id="s|m",
                                board="lucky-break-payday", scenario="s", model="m",
                                lane="test")
        result = replay.replay(self.conn, aid)
        self.assertFalse(result["ok"])
        self.assertIn("missing", result.get("error", "") + str(result))


if __name__ == "__main__":
    unittest.main()