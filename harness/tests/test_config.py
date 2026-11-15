"""Configuration / documentation drift guard.

The registry (`RULES.md`), the instructions (`CLAUDE.md`), the board profiles
and the code must agree.  These tests are the mechanical part of that promise:
a stale claim breaks the suite instead of misleading the next session.
"""
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import config_check  # noqa: E402


class ConfigCheckTest(unittest.TestCase):
    def test_every_check_passes(self):
        report = config_check.run()
        failed = [r for r in report["results"] if not r["ok"]]
        self.assertTrue(report["ok"], f"drift detected: {failed}")

    def test_guard_notices_a_missing_infrastructure_file(self):
        """A guard that cannot fail is worthless: prove it detects absence."""
        old = config_check.LIVE_INFRA
        config_check.LIVE_INFRA = ("harness/definitely_absent.py",)
        try:
            r = config_check.check_infra_files()
        finally:
            config_check.LIVE_INFRA = old
        self.assertFalse(r["ok"])
        self.assertIn("definitely_absent", r["detail"])
        self.assertTrue(config_check.check_infra_files()["ok"])

    def test_guard_notices_a_docs_claim_about_a_missing_module(self):
        with tempfile.TemporaryDirectory() as td:
            fake = pathlib.Path(td) / "RULES.md"
            fake.write_text("см. harness/nonexistent_module.py — так нельзя",
                            encoding="utf-8")
            old = config_check.RULES
            config_check.RULES = fake
            try:
                r = config_check.check_docs_claims()
            finally:
                config_check.RULES = old
        self.assertFalse(r["ok"])
        self.assertIn("nonexistent_module.py", r["detail"])

    def test_registry_and_instructions_agree(self):
        r = config_check.check_docs_claims()
        self.assertTrue(r["ok"], r["detail"])

    def test_deprecated_entry_point_is_inert(self):
        r = config_check.check_deprecated_stub()
        self.assertTrue(r["ok"], r["detail"])

    def test_strategy_engine_is_wired(self):
        r = config_check.check_strategy_engine()
        self.assertTrue(r["ok"], r["detail"])


if __name__ == "__main__":
    unittest.main()

class SingleJournalTest(unittest.TestCase):
    """The axis-10 invariant of Grok's "one journal" axis: the check must go red when
    live code reads the v1 archive as data, and green when everything goes through
    harness/journal.py."""

    def test_the_check_is_green_now(self):
        res = config_check.check_single_journal()
        self.assertTrue(res["ok"], res.get("detail"))

    def test_the_check_names_every_consumer(self):
        for name in config_check.JOURNAL_CONSUMERS:
            path = config_check.WORK / "harness" / name
            self.assertTrue(path.is_file(), f"harness/{name} missing")
            self.assertIn("journal", path.read_text(encoding="utf-8", errors="replace"))

    def test_the_guard_fires_on_a_fake_read(self):
        victim = config_check.WORK / "harness" / "lbp_plan.py"
        original = victim.read_text(encoding="utf-8")
        fake = ("def _bad():\n"
                "    return (WORK / 'datasets/lbp/pairs.jsonl').read_text()\n"
                "\n\n")
        try:
            victim.write_text(original.replace("def load_pairs(", fake + "def load_pairs(", 1),
                              encoding="utf-8")
            res = config_check.check_single_journal()
            self.assertFalse(res["ok"])
            self.assertIn("reads the archive as data", res.get("detail") or "")
        finally:
            victim.write_text(original, encoding="utf-8")
        self.assertTrue(config_check.check_single_journal()["ok"])
