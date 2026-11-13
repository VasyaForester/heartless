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
