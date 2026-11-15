"""Target selection: exactly one tab, or an attempt error — never a guess.

Grok's review (2026-11-15) put it in one line: an empty CHAT_TARGET with two tabs must
be an attempt error, not a guess.  The old code took `cands[-1]` — "the freshest tab" —
but the order of tabs in the CDP listing is not a clock; it is just how Chrome happened
to list them.  Picking one is how a probe lands in the wrong chat, and a probe in the
wrong chat is evidence about the wrong thing.

These tests drive the pure `choose()` function, so they need no browser.
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

import pick_target  # noqa: E402

PAYDAY = "https://app.grayswan.ai/arena/challenge/lucky-break-payday/chat"
PG = "https://app.grayswan.ai/arena/challenge/proving-ground/chat"


def tab(tid, url, kind="page"):
    return {"id": tid, "type": kind, "url": url}


class ChooseTargetTest(unittest.TestCase):
    def test_exactly_one_match_wins(self):
        tid, reason, code = pick_target.choose([tab("A", PAYDAY)], "lucky-break-payday")
        self.assertEqual((tid, code), ("A", 0))

    def test_no_match_is_a_clean_none(self):
        tid, reason, code = pick_target.choose([tab("A", PG)], "lucky-break-payday")
        self.assertIsNone(tid)
        self.assertEqual(code, 1)
        self.assertIn("no tab", reason)

    def test_two_matching_tabs_are_ambiguous_not_a_guess(self):
        tabs = [tab("A", PAYDAY), tab("B", PAYDAY + "?x=1")]
        tid, reason, code = pick_target.choose(tabs, "lucky-break-payday")
        self.assertIsNone(tid, "ambiguity must NOT resolve to a tab")
        self.assertEqual(code, 2)
        self.assertIn("ambiguous: 2 tabs", reason)

    def test_non_page_targets_are_ignored(self):
        tabs = [tab("A", PAYDAY, kind="other"), tab("B", "https://example.com/x")]
        tid, _, code = pick_target.choose(tabs, "lucky-break-payday")
        self.assertIsNone(tid)
        self.assertEqual(code, 1)

    def test_a_foreign_board_tab_is_not_a_match(self):
        tabs = [tab("A", PAYDAY), tab("B", PG)]
        tid, _, code = pick_target.choose(tabs, "proving-ground")
        self.assertEqual((tid, code), ("B", 0), "the needle decides, not the order")

    def test_order_does_not_change_the_answer(self):
        a = pick_target.choose([tab("A", PAYDAY)], "lucky-break-payday")
        b = pick_target.choose([tab("A", PAYDAY)], "lucky-break-payday")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
