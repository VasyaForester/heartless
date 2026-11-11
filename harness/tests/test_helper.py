"""Offline integration tests: no browser, real profile, or Arena access."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HELPER_PATH = Path(__file__).resolve().parents[1] / "hackathon.py"
SPEC = importlib.util.spec_from_file_location("hackathon_helper_tested", HELPER_PATH)
h = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = h
SPEC.loader.exec_module(h)


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="helper-unit-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.layout = h.Layout(self.root / "participant")
        self.layout.harness.mkdir(parents=True)
        shutil.copyfile(HELPER_PATH, self.layout.harness / "hackathon.py")

    def event(self, attempt="a1", **updates):
        value = {"attemptId": attempt, "track": "Chat", "scenarioId": "s1", "modelId": "m1",
                 "status": "completed", "judgeStatus": "passed", "judgeEvidence": "judge: pass"}
        value.update(updates)
        return value

    def skill(self, name):
        directory = self.layout.profile / "skills" / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text("---\nname: " + name + "\n---\nLocal instructions.\n", encoding="utf-8")
        return directory

    def test_setup_is_idempotent_and_never_truncates(self):
        h.setup(self.layout, write_config=True)
        h.record(self.layout, self.event())
        before = self.layout.journal.read_bytes()
        h.setup(self.layout, write_config=True)
        self.assertEqual(before, self.layout.journal.read_bytes())
        self.assertTrue((self.layout.workspace / "artifacts").is_dir())
        self.assertTrue((self.layout.workspace / "inputs").is_dir())
        self.assertEqual(h.CDP_URL, json.loads((self.layout.harness / ".local.json").read_text())["cdpUrl"])

    def test_invalid_event_makes_no_writes(self):
        bad = self.event(track="Other")
        with self.assertRaises(h.HelperError):
            h.record(self.layout, bad)
        self.assertFalse(self.layout.journal.parent.exists())
        with self.assertRaises(h.HelperError):
            h.record(self.layout, self.event(status="pending"))
        with self.assertRaises(h.HelperError):
            h.record(self.layout, self.event(judgeEvidence={"result": "pass"}))
        with self.assertRaises(h.HelperError):
            h.record(self.layout, self.event(judgeStatus=[]))

    def test_append_retains_full_local_data_and_old_bytes(self):
        h.record(self.layout, self.event(input={"message": "local prompt"}, response="local answer"))
        before = self.layout.journal.read_bytes()
        h.record(self.layout, self.event(judgeStatus="failed", judgeEvidence="judge: fail"))
        after = self.layout.journal.read_bytes()
        self.assertTrue(after.startswith(before))
        events = h.read_events(self.layout)
        self.assertEqual(events[0]["response"], "local answer")
        self.assertNotEqual(events[0]["eventId"], events[1]["eventId"])

    def test_summary_latest_events_unique_pairs_and_coverage(self):
        h.record(self.layout, self.event("a1"))
        h.record(self.layout, self.event("a2"))  # Same pair, different attempt.
        h.record(self.layout, self.event("a3", modelId="m2", judgeEvidence=" "))
        h.record(self.layout, self.event("a4", scenarioId="s2", status="error", judgeStatus="unknown", judgeEvidence=""))
        h.record(self.layout, self.event("a1", status="pending", judgeStatus="pending", judgeEvidence=""))
        result = h.summary(self.layout)
        self.assertEqual((result["totalEvents"], result["totalAttempts"]), (5, 4))
        self.assertEqual(result["confirmedPassedPairs"], 1)
        self.assertEqual(result["confirmedPassedScenarios"], 1)
        self.assertEqual(result["coveredScenarios"], 2)
        self.assertEqual(result["statusCounts"], {"completed": 2, "error": 1, "pending": 1})
        self.assertNotIn("judgeEvidence", result["attempts"][0])
        h.record(self.layout, self.event("a2", judgeStatus="failed"))
        self.assertEqual(h.summary(self.layout)["confirmedPassedPairs"], 0)
        self.assertEqual(h.summary(self.layout)["confirmedPassedScenarios"], 0)

    def test_reference_counts_five_pairs_four_passed_eight_covered(self):
        for number in range(1, 9):
            h.record(self.layout, self.event(f"a{number}", scenarioId=f"s{number}",
                                           judgeStatus="passed" if number <= 4 else "failed"))
        h.record(self.layout, self.event("another-model", scenarioId="s1", modelId="m2"))
        result = h.summary(self.layout)
        self.assertEqual(result["confirmedPassedPairs"], 5)
        self.assertEqual(result["confirmedPassedScenarios"], 4)
        self.assertEqual(result["coveredScenarios"], 8)

    def test_damaged_journal_is_preserved(self):
        h.setup(self.layout)
        self.layout.journal.write_text('{"partial":', encoding="utf-8")
        before = self.layout.journal.read_bytes()
        with self.assertRaises(h.HelperError):
            h.record(self.layout, self.event())
        self.assertEqual(before, self.layout.journal.read_bytes())
        self.assertFalse(self.layout.journal.with_suffix(".lock").exists())

    def test_export_only_sources_all_skills_and_redacted_summary(self):
        h.setup(self.layout, write_config=True)
        self.skill("participant-arbitrary-new-skill")
        self.skill("gray-swan-cdp-automation")
        (self.layout.harness / "config.json").write_text('{"budget":3}', encoding="utf-8")
        (self.layout.harness / ".env").write_text("private file", encoding="utf-8")
        (self.layout.profile / "SOUL.md").write_text("do not export blanket profile", encoding="utf-8")
        browser = self.layout.profile / "browser-data"
        browser.mkdir()
        (browser / "Cookies").write_text("private browser", encoding="utf-8")
        h.record(self.layout, self.event(input="private prompt", response="private answer", judgeEvidence="private judge reply"))
        destination = self.root / "submission.zip"
        h.export_submission(self.layout, destination)
        with zipfile.ZipFile(destination) as archive:
            names = set(archive.namelist())
            self.assertIn("skills/participant-arbitrary-new-skill/SKILL.md", names)
            self.assertIn("harness/config.json", names)
            self.assertNotIn("harness/.local.json", names)
            self.assertNotIn("harness/.env", names)
            self.assertEqual(names & {"summary.json", "summary.csv"}, {"summary.json", "summary.csv"})
            payload = b"\n".join(archive.read(name) for name in names)
            for private in (b"private prompt", b"private answer", b"private judge reply", b"private browser", b"do not export blanket"):
                self.assertNotIn(private, payload)
        before = destination.read_bytes()
        with self.assertRaises(h.HelperError):
            h.export_submission(self.layout, destination)
        self.assertEqual(before, destination.read_bytes())

    def test_export_refuses_suspicious_source_without_printing_value(self):
        secret = "sk-" + "x" * 30
        (self.layout.harness / "config.json").write_text(json.dumps({"apiKey": secret}), encoding="utf-8")
        destination = self.root / "submission.zip"
        with self.assertRaises(h.HelperError) as raised:
            h.export_submission(self.layout, destination)
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("harness/config.json", str(raised.exception))
        self.assertFalse(destination.exists())

    def test_personal_paths_and_transcripts_are_rejected(self):
        config = self.layout.harness / "config.json"
        config.write_text(json.dumps({"cwd": "/Users/" + "participant/private"}), encoding="utf-8")
        with self.assertRaises(h.HelperError):
            h.export_submission(self.layout, self.root / "one.zip")
        config.write_text(json.dumps({"input": "private", "response": "private"}), encoding="utf-8")
        with self.assertRaises(h.HelperError):
            h.export_submission(self.layout, self.root / "two.zip")

    def test_generic_unquoted_secret_assignment_is_rejected(self):
        value = "api_key: " + "generic" * 5
        self.assertTrue(h.scan_text(value, "config.yaml"))

    def test_symlink_source_or_journal_is_not_followed(self):
        external = self.root / "outside.txt"
        external.write_text("outside", encoding="utf-8")
        try:
            (self.layout.harness / "linked.md").symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(h.HelperError):
            h.export_submission(self.layout, self.root / "link.zip")
        self.layout.journal.parent.mkdir()
        self.layout.journal.symlink_to(external)
        with self.assertRaises(h.HelperError):
            h.record(self.layout, self.event())
        self.assertEqual(external.read_text(), "outside")

    def test_source_scanner_accepts_itself_and_placeholders(self):
        self.assertEqual(h.scan_text(HELPER_PATH.read_text(), "helper"), [])
        self.assertEqual(h.scan_text('api_key="YOUR_API_KEY"', "example"), [])
        self.assertEqual(h.scan_text(Path(__file__).read_text(), "tests"), [])

    def test_csv_formula_is_escaped(self):
        h.record(self.layout, self.event(attempt="=2+3"))
        self.assertIn("'=2+3", h.summary_csv(h.summary(self.layout)))

    def test_node_runtime_check_rejects_missing_websocket(self):
        result = subprocess.CompletedProcess([], 0, '{"version":"22.0.0","webSocket":false}', "")
        with patch.object(h.shutil, "which", return_value="node"), patch.object(h.subprocess, "run", return_value=result):
            with self.assertRaises(h.HelperError):
                h.discover_node()

    def test_doctor_separates_transport_tabs_and_unverified_arena_readiness(self):
        engine_dir = self.layout.harness / "engine"
        engine_dir.mkdir()
        (engine_dir / "arena.mjs").write_text("// test fixture", encoding="utf-8")
        with patch.object(h, "discover_node", return_value=("node", {"version": "22.0.0", "webSocket": True})), \
             patch.object(h, "chrome_candidates", return_value=[Path("chrome")]), \
             patch.object(h, "installed_skills", return_value=list(h.REQUIRED_SKILLS)):
            for tabs in ([], [{"id": "tab1", "url": "https://app.grayswan.ai/", "title": "Arena"}]):
                with self.subTest(tabs=tabs), patch.object(h, "engine", return_value={"ok": True, "command": "tabs", "result": tabs}):
                    result = h.doctor(self.layout, browser=True)
                    self.assertTrue(result["browserTransportAvailable"])
                    self.assertEqual(result["arenaTabAvailable"], bool(tabs))
                    self.assertEqual(result["matchingArenaTabs"], len(tabs))
                    self.assertEqual(result["ok"], bool(tabs))
                    for check in ("login", "training", "judge"):
                        self.assertEqual(result["arenaReadiness"][check], "not_verified")
            with patch.object(h, "engine", side_effect=h.HelperError("CDP unavailable")):
                result = h.doctor(self.layout, browser=True)
                self.assertFalse(result["browserTransportAvailable"])
                self.assertFalse(result["arenaTabAvailable"])
                self.assertFalse(result["ok"])

    def test_browser_launch_uses_only_dedicated_profile_and_loopback(self):
        chrome = self.root / "chrome"
        chrome.write_text("fake executable", encoding="utf-8")
        with patch.object(h.socket, "socket") as socket_mock, patch.object(h.subprocess, "Popen") as popen:
            popen.return_value.pid = 123
            result = h.launch_browser(self.layout, str(chrome))
            command = popen.call_args.args[0]
            self.assertIn("--remote-debugging-address=127.0.0.1", command)
            self.assertIn("--remote-debugging-port=9223", command)
            self.assertIn(f"--user-data-dir={self.layout.profile / 'browser-data'}", command)
            self.assertEqual(command[-1], h.TRAINING_URL)
            socket_mock.return_value.__enter__.return_value.bind.assert_called_once_with(("127.0.0.1", 9223))
            self.assertEqual(result["pid"], 123)

    def test_occupied_cdp_browser_is_reused_without_killing_or_restarting(self):
        with patch.object(h.socket, "socket") as sock, patch.object(h, "engine") as engine, \
                patch.object(h.subprocess, "Popen") as popen:
            sock.return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
            engine.return_value = {"ok": True, "result": {"targetId": "fixture-tab"}}
            result = h.launch_browser(self.layout)
            self.assertTrue(result["reusedBrowser"])
            engine.assert_called_once_with(self.layout, "open", ["--url", h.TRAINING_URL, "--cdp", h.CDP_URL])
            popen.assert_not_called()

    def test_launch_rejects_non_arena_destination_before_touching_browser(self):
        with patch.object(h.socket, "socket") as sock:
            with self.assertRaises(h.HelperError):
                h.launch_browser(self.layout, url="https://example.com/")
            sock.assert_not_called()

    def test_arena_wrapper_preserves_arguments_including_spaces(self):
        with patch.object(h, "engine", return_value={"ok": True}) as engine:
            self.assertEqual(h.main(["arena", "context", "--target", "target id"], self.layout), 0)
            engine.assert_called_once_with(self.layout, "context", ["--target", "target id"])


if __name__ == "__main__":
    unittest.main()
