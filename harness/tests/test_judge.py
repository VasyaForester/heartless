import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import judge_correlation  # noqa: E402

START = 1_700_000_000.0


def iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class JudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.attempt = {
            "attempt_id": "a1", "chat_id": "abc123", "started_at": START,
            "transcript_hash": hashlib.sha256(b"hello").hexdigest(),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, operation_id="a1", chat="abc123", submitted=None,
              status="accepted", pcts=(90,), evidence=None):
        doc = {
            "operationId": operation_id,
            "url": f"https://app.grayswan.ai/arena/challenge/lucky-break-payday?chatId={chat}" if chat else "",
            "submittedAt": iso(submitted if submitted is not None else START + 30),
            "capturedAt": iso(START + 60),
            "status": status,
            "criteriaPercents": [{"text": f"Tool x {p}%"} for p in pcts],
            "evidence": evidence or [],
        }
        p = self.dir / "judge.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    def test_verified(self):
        r = judge_correlation.correlate(self.attempt, self.write(),
                                        transcript_text="hello")
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["score"], 90)
        self.assertEqual(r["verdict"], "accepted")

    def test_stale(self):
        r = judge_correlation.correlate(self.attempt, self.write(submitted=START - 3600))
        self.assertEqual(r["status"], "stale")

    def test_duplicate(self):
        r = judge_correlation.correlate(self.attempt, self.write(),
                                        known_operations={"a1": "other"})
        self.assertEqual(r["status"], "duplicate")

    def test_mismatched_operation(self):
        r = judge_correlation.correlate(self.attempt, self.write(operation_id="a2"))
        self.assertEqual(r["status"], "mismatched_operation")

    def test_mismatched_chat(self):
        r = judge_correlation.correlate(self.attempt, self.write(chat="def456"))
        self.assertEqual(r["status"], "mismatched_chat")

    def test_pending(self):
        r = judge_correlation.correlate(self.attempt, self.write(status="pending", pcts=()))
        self.assertEqual(r["status"], "pending")

    def test_missing(self):
        r = judge_correlation.correlate(self.attempt, self.dir / "absent.json")
        self.assertEqual(r["status"], "missing")

    def test_unverified_no_identity(self):
        p = self.write(operation_id=None, chat=None)
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc.pop("operationId", None)
        doc.pop("submittedAt", None)
        p.write_text(json.dumps(doc), encoding="utf-8")
        r = judge_correlation.correlate(self.attempt, p)
        self.assertEqual(r["status"], "unverified")

    def test_mismatched_transcript(self):
        r = judge_correlation.correlate(self.attempt, self.write(),
                                        transcript_text="other text")
        self.assertEqual(r["status"], "mismatched_transcript")


if __name__ == "__main__":
    unittest.main()