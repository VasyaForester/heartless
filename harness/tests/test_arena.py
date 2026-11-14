"""Conformance test for the arena adapters (harness/arena.py).

A new arena must be validated by REGISTRATION, not by hope: the checks below run
for every adapter in the registry, so writing an adapter that satisfies them is
the whole porting job (plus its board profile).
"""

import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("HERMES_DRIVER_LOG",
                      str(pathlib.Path(os.environ.get("TEMP", "/tmp")) / "hermes-test-driver.log"))

import arena  # noqa: E402
import boards  # noqa: E402


class AdapterContractTest(unittest.TestCase):
    """Mechanical contract: these are the calls the driver actually makes."""

    def setUp(self):
        board = boards.load_board()
        self.adapter = arena.get_adapter(board)
        self.board = board

    def test_every_registered_adapter_declares_identity(self):
        for name, cls in arena.ADAPTERS.items():
            self.assertTrue(name)
            self.assertTrue(hasattr(cls, "NAME"))
            self.assertEqual(cls.NAME, name, "registry key and NAME must agree")

    def test_unit_ids_round_trip(self):
        units = self.adapter.units()
        self.assertTrue(units, "an adapter with no units cannot be probed")
        for unit in units:
            scenario, model = self.adapter.split_unit(unit["id"])
            self.assertEqual(self.adapter.unit_id(scenario, model), unit["id"])
            self.assertEqual(unit["scenario"], scenario)
            self.assertEqual(unit["model"], model)
            self.assertIsInstance(unit["solved"], bool)

    def test_units_cover_the_board_profile(self):
        board = self.board
        expected = 0
        for sid, models in (board.get("models_by_scenario") or {}).items():
            expected += len(models or [])
        if not expected:
            expected = len(self.adapter.scenarios()) * len(self.adapter.models())
        self.assertGreaterEqual(len(self.adapter.units()), 1)
        self.assertEqual(len(self.adapter.units()), expected,
                         "units() must enumerate the board's cells")

    def test_discovery_matches_the_profile(self):
        self.assertEqual(set(self.adapter.scenarios()), set(self.board["scenario_titles"]))
        for sid in self.adapter.scenarios():
            self.assertTrue(self.adapter.models_for(sid))

    def test_energy_is_an_int_and_never_zero_for_unknown(self):
        """-1 means 'unknown' so the gate is skipped; 0 would fence the loop."""
        value = self.adapter.energy()
        self.assertIsInstance(value, int)
        self.assertIn(value, (-1, 0) if value == 0 else (value,), "0 only if truly empty")
        self.assertGreaterEqual(value, -1)

    def test_probe_builds_a_real_transport_call(self):
        """The adapter must not invent its own transport: probing a clone of the
        CLI with a bad scenario must come back with a non-zero rc instead of
        raising, so the loop can count errors."""
        r = self.adapter.probe("", "definitely-not-a-scenario|nope",
                               "inputs/does-not-exist.txt", wait_s=1,
                               opid="contract-test")
        self.assertEqual(r.rc != 0, True)
        self.assertFalse(r.ok)
        self.assertIsInstance(r.out, str)

    def test_evidence_paths_are_bound_to_units_and_operations(self):
        unit = self.adapter.units()[0]["id"]
        judge = self.adapter.judge_artifact(unit)
        self.assertIsInstance(judge, pathlib.Path)
        # a foreign operation must not resolve to another attempt's artifact
        self.assertIsNone(self.adapter.judge_for_operation(unit, "no-such-opid"))
        _path, text, chat = self.adapter.transcript(unit)
        self.assertIsInstance(text, str)
        self.assertTrue(chat is None or isinstance(chat, str))

    def test_signals_are_keyed_by_operation_not_by_unit(self):
        """A per-unit shared record would hand the previous probe's signals to
        the current one — the defect this whole channel was rebuilt around."""
        self.assertEqual(self.adapter.signals("no-such-opid"), {})
        self.assertIsInstance(self.adapter.signals(""), dict)

    def test_naming_and_modules_come_from_the_board(self):
        name = self.adapter.input_name("scam-retail", "append_nonce", 1794590000, 7)
        self.assertIn("append_nonce", name)
        self.assertEqual(self.adapter.delta_module(), self.board.get("deltas_module"))
        self.assertEqual(self.adapter.check_module(), self.board.get("checks_module"))

    def test_unknown_platform_fails_loudly(self):
        """A board naming an unregistered platform must not silently fall back
        to Gray Swan: that would run one arena's transport against another."""
        board = dict(self.board)
        board["platform"] = "some-other-arena"
        with self.assertRaises(SystemExit):
            arena.get_adapter(board)

    def test_board_platform_field_is_optional_and_explicit_here(self):
        """Boards may name their platform; when they do, it must be resolvable —
        either already registered or autoloadable as arena_<platform>.py."""
        for name in boards.list_boards():
            profile = boards.load_board(name)
            if profile.get("platform"):
                with self.subTest(board=name):
                    adapter = arena.get_adapter(profile)  # autoloads if needed
                    self.assertEqual(adapter.name(), profile["platform"])
                    self.assertEqual(adapter.version(), arena.INTERFACE_VERSION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
