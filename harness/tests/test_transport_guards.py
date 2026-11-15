"""Transport guards: one target per attempt, and no send into a chat we did not verify.

Grok's review (2026-11-15, axis "transport": 8/10) asked for three things beyond what
existed, and each has a test here:

  * after the card click, READ THE SCENARIO MARKER and drop the attempt if it did not
    change — the known failure mode is `?behaviorId=` silently no-oping while a
    URL-contains check still "passes";
  * a chats modal / dead tab that swallows the send must FAIL THE ATTEMPT instead of
    resending into the old chat;
  * the attempt is bound to ONE target for its whole life, and a tab-id change appears
    in the journal as a NEW binding.

The marker decision is a pure function (`lbp.marker_matches`) so it is tested without a
browser.  The two ordering rules (persist before `continue`; verify the marker before
re-sending) are source-level guards, tested the way config_check tests its own guards:
read the file, strip comments, match the pattern next to the action it protects.
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

import attempts as attempts_mod  # noqa: E402
import driver  # noqa: E402
import lbp  # noqa: E402
import store  # noqa: E402


def code_lines(path: pathlib.Path) -> str:
    """The file with comment-only lines removed (a guard must live in live code)."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


class MarkerTest(unittest.TestCase):
    """`marker_matches` — did the scenario really change?"""

    TITLES = {"sid-a": "Scenario Alpha", "sid-b": "Scenario Beta"}

    def test_the_right_marker_matches(self):
        self.assertTrue(lbp.marker_matches("Scenario Alpha — attack panel", "sid-a",
                                           self.TITLES))

    def test_an_empty_marker_is_not_a_success(self):
        """«Не знаю» must not look like «ок» — that is how sends leaked into other chats."""
        self.assertFalse(lbp.marker_matches("", "sid-a", self.TITLES))
        self.assertFalse(lbp.marker_matches("   ", "sid-a", self.TITLES))

    def test_the_wrong_marker_fails(self):
        self.assertFalse(lbp.marker_matches("Scenario Beta", "sid-a", self.TITLES))

    def test_an_unknown_scenario_fails_closed(self):
        self.assertFalse(lbp.marker_matches("Scenario Alpha", "who-knows", self.TITLES))

    def test_a_partial_title_does_not_match(self):
        self.assertFalse(lbp.marker_matches("Scenario", "sid-a", self.TITLES))

    def test_the_real_titles_work(self):
        sid = next(iter(lbp.SCENARIO_TITLES))
        self.assertTrue(lbp.marker_matches(lbp.SCENARIO_TITLES[sid], sid))


class GuardPlacementTest(unittest.TestCase):
    """The two ordering rules, checked in the live source (comments stripped)."""

    def setUp(self):
        self.src = code_lines(HERE.parent / "lbp.py")

    def test_the_attempt_is_dropped_before_the_send_when_the_marker_did_not_change(self):
        idx = self.src.find('send_skipped"] = "scenario_switch_failed')
        self.assertGreater(idx, 0, "the scenario-marker guard is gone")
        window = self.src[idx:idx + 400]
        self.assertIn("_persist(run)", window, "a dropped attempt must still be recorded")
        self.assertIn("continue", window, "a dropped attempt must not reach the send")

    def test_the_marker_is_read_before_the_attempt_is_dropped(self):
        idx = self.src.find("switch_ok = bool(ok_ctx) or marker_matches(")
        self.assertGreater(idx, 0, "the marker read is gone")
        self.assertLess(idx, self.src.find('send_skipped"] = "scenario_switch_failed'))

    def test_the_heal_verifies_the_marker_before_resending(self):
        idx = self.src.find('run["heal"] = "board-reopen+resend"')
        self.assertGreater(idx, 0)
        window = self.src[idx:idx + 1600]
        verify = window.find("marker_matches(heal_marker, sid)")
        resend = window.find('_send_once(run, tag_2 := "_retry")')
        self.assertGreater(verify, 0, "the heal resends without reading the marker")
        self.assertLess(verify, resend, "the marker must be verified BEFORE the resend")
        self.assertIn("heal_refused", window, "a refused heal must say why")

    def test_every_ledger_row_names_its_target(self):
        self.assertIn('"target": tid', self.src, "the attempt must record its target")

    def test_a_fresh_run_writes_its_binding(self):
        """The driver, not the probe CLI, owns the binding record."""
        driver_src = code_lines(HERE.parent / "driver.py")
        self.assertIn("_bind_target(store.connect(a.db), a.lane, target)", driver_src)


class TargetBindingTest(unittest.TestCase):
    """One target per attempt; a change is a NEW binding, visible in the journal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name) / "t.db"
        store.connect(self.db).close()          # schema
        self.conn = store.connect(self.db)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def events(self, kind):
        import json
        return [json.loads(r["payload"]) for r in self.conn.execute(
            "SELECT payload FROM events WHERE kind=? ORDER BY id", (kind,))]

    def test_the_first_start_records_a_binding_and_no_rebound(self):
        rec = driver._bind_target(self.conn, "lane-a", "TAB1")
        self.assertEqual(rec["target"], "TAB1")
        self.assertEqual(len(self.events("target_binding")), 1)
        self.assertEqual(self.events("target_rebound"), [])

    def test_the_same_target_again_is_not_a_rebinding(self):
        driver._bind_target(self.conn, "lane-a", "TAB1")
        driver._bind_target(self.conn, "lane-a", "TAB1")
        self.assertEqual(self.events("target_rebound"), [],
                         "repeating the same id must not look like a change")

    def test_a_new_tab_id_is_visible_as_a_new_binding(self):
        driver._bind_target(self.conn, "lane-a", "TAB1")
        driver._bind_target(self.conn, "lane-a", "TAB2")
        rebounds = self.events("target_rebound")
        self.assertEqual(len(rebounds), 1)
        self.assertEqual(rebounds[0]["previous"], "TAB1")
        self.assertEqual(rebounds[0]["target"], "TAB2")
        self.assertEqual(len(self.events("target_binding")), 2,
                         "one binding per start: the first, then the rebinding")

    def test_the_attempt_row_carries_the_target(self):
        self.conn.execute(
            "INSERT INTO pairs(id,board_profile,scenario,model) VALUES('s|m','board','s','m')")
        lease = store.acquire_lease(self.conn, "lane-a", "TAB1")
        aid = attempts_mod.allocate(self.conn, lease, pair_id="s|m", board="board",
                                    scenario="s", model="m", lane="lane-a",
                                    target_id="TAB1")
        row = self.conn.execute("SELECT target_id FROM attempts WHERE attempt_id=?",
                                (aid,)).fetchone()
        self.assertEqual(row["target_id"], "TAB1")

    def test_the_live_schema_knows_the_column(self):
        version = self.conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'").fetchone()["value"]
        self.assertGreaterEqual(int(version), 6)
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(attempts)")]
        self.assertIn("target_id", cols)

    def test_a_stale_target_is_still_refused(self):
        self.assertTrue(lbp.refuse_stale_target(sorted(lbp.STALE_TARGETS)[0], "repeat"))
        self.assertFalse(lbp.refuse_stale_target("TAB-FRESH", "repeat"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
