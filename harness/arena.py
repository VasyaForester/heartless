#!/usr/bin/env python3
"""Arena adapter: the seam that keeps the platform out of the driver.

Why this module exists
----------------------
The independent review scored portability 3/10: the transport, the evidence
layout and the unit naming were all woven through the loop, so a second arena
would have meant editing the driver.  Everything the driver needs from a
platform now goes through this interface, and a new arena means writing one
adapter + one board profile — not touching the loop.

The interface was DERIVED from the calls the driver actually makes (see the
`ArenaAdapter` docstring); it is not a wish list.  `GraySwanLBP` is the
Gray Swan implementation: it delegates to `lbcore` (board data + file layout)
and to the `lbp.py` CLI, so nothing about today's behaviour moves.

Contract: `harness/tests/test_arena.py` checks every registered adapter
mechanically (unit ids round-trip, probe returns a run record, energy is an int
or -1, evidence paths resolve), so a future adapter can be validated by
registration instead of by hope.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

from boards import load_board  # noqa: E402  (needs the path insert above)

INTERFACE_VERSION = 1


@dataclass
class ProbeResult:
    """One probe as the platform reports it.

    rc/out/err come from the transport; `signals` is the run record the platform
    CLI wrote for that operation (local validator evidence).  A probe with
    rc == 0 may still carry no signals if the record was lost.
    """

    rc: int
    out: str = ""
    err: str = ""
    signals: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.rc == 0


@runtime_checkable
class ArenaAdapter(Protocol):
    """What the driver is allowed to expect from an arena.

    Identity / discovery
        name(), version(), scenarios(), models(), models_for(), solved_seed(),
        units(), unit_id(), split_unit()

    Probe transport
        energy(target)            -> int (-1 means "unknown", never 0)
        probe(target, unit, input_path, wait_s, opid) -> ProbeResult

    Evidence (bound to ONE operation, never a per-unit shared file)
        signals(opid, input_path)
        judge_artifact(unit)
        judge_for_operation(unit, opid)
        transcript(unit)          -> (path, text, chat_id)

    Naming / layout
        input_name(scenario, arm, ts, rnd)
        delta_module(), check_module()
    """

    # --- identity / discovery -------------------------------------------
    def name(self) -> str: ...
    def version(self) -> int: ...
    def scenarios(self) -> dict: ...
    def models(self) -> list: ...
    def models_for(self, scenario: str) -> list: ...
    def solved_seed(self) -> dict: ...
    def units(self) -> list: ...
    def unit_id(self, scenario: str, model: str) -> str: ...

    # --- probe transport ------------------------------------------------
    def energy(self, target: str = "") -> int: ...
    def probe(self, target: str, unit: str, input_path: str, wait_s: int,
              opid: str) -> ProbeResult: ...

    # --- evidence -------------------------------------------------------
    def signals(self, opid: str, input_path: str = "") -> dict: ...
    def judge_artifact(self, unit: str) -> pathlib.Path: ...
    def judge_for_operation(self, unit: str, opid: str) -> pathlib.Path | None: ...
    def transcript(self, unit: str) -> tuple[pathlib.Path, str, Any]: ...

    # --- naming / layout ------------------------------------------------
    def input_name(self, scenario: str, arm: str, ts: int, rnd: int) -> str: ...
    def newest_input(self, scenario: str, model: str): ...
    def delta_module(self) -> str: ...
    def check_module(self) -> str: ...


class GraySwanLBP:
    """Gray Swan (Lucky Break / Proving Ground) over the `lbp.py` CLI + CDP.

    Every method is a delegation: the adapter does not own any new behaviour, it
    names the platform surface the loop depends on.
    """

    NAME = "gray-swan-lbp"

    def __init__(self, board: dict | None = None):
        import lbcore
        self._core = lbcore
        self._board = board if board is not None else lbcore.BOARD

    # --- identity / discovery -------------------------------------------
    def name(self) -> str:
        return self.NAME

    def version(self) -> int:
        return INTERFACE_VERSION

    def scenarios(self) -> dict:
        return dict(self._core.SCENARIOS)

    def models(self) -> list:
        return list(self._core.MODELS)

    def models_for(self, scenario: str) -> list:
        return list(self._core.models_for(scenario))

    def solved_seed(self) -> dict:
        return {k: sorted(v) for k, v in self._core.SOLVED.items()}

    def unit_id(self, scenario: str, model: str) -> str:
        return f"{scenario}|{model}"

    def split_unit(self, unit: str) -> tuple[str, str]:
        scenario, _, model = unit.partition("|")
        return scenario, model

    def units(self) -> list:
        """Every (scenario, model) cell with its seeded solved state."""
        solved = self._core.SOLVED
        out = []
        for sid in self.scenarios():
            for model in self.models_for(sid):
                out.append({"id": self.unit_id(sid, model), "scenario": sid,
                            "model": model, "solved": model in solved.get(sid, set())})
        return out

    # --- probe transport ------------------------------------------------
    def energy(self, target: str = "") -> int:
        cmd = [sys.executable, str(self._core.LBP), "state"]
        if target:
            cmd += ["--target", target]
        rc, out, _err = self._core.sh(cmd, timeout=90)
        try:
            data = json.loads(out)
        except (json.JSONDecodeError, TypeError):
            return -1
        e = data.get("energy")
        # Unreadable energy (e.g. Proving Ground shows no "Energy N of M") means
        # "unknown" (-1: skip the gate), NOT zero (which would fence the loop).
        if not isinstance(e, dict) or e.get("current") is None:
            return -1
        try:
            return int(e["current"])
        except (TypeError, ValueError):
            return -1

    def probe(self, target: str, unit: str, input_path: str, wait_s: int,
              opid: str) -> ProbeResult:
        scenario, model = self.split_unit(unit)
        cmd = [sys.executable, str(self._core.LBP), "repeat",
               "--scenario", scenario, "--model", model,
               "--input", input_path, "--n", "1", "--wait-s", str(wait_s),
               "--submit", "--opid", opid]
        if target:
            cmd += ["--target", target]
        try:
            rc, out, err = self._core.sh(cmd, timeout=wait_s + 260)
        except subprocess.TimeoutExpired:
            return ProbeResult(rc=-9, out="", err="timeout")
        return ProbeResult(rc=rc, out=out or "", err=err or "")

    # --- evidence -------------------------------------------------------
    def signals(self, opid: str, input_path: str = "") -> dict:
        """Run record for THIS operation from the platform's probe ledger.

        `lbp.py repeat` writes one JSON row per probe tagged with the `--opid`
        the driver passed, which is how a live attempt is joined to its local
        validator evidence without touching the browser again.  The input-file
        basename is the fallback for rows written before the opid handshake
        existed — matching by unit instead would hand the previous probe's
        record to the current one, the defect the channel was rebuilt around.
        """
        path = WORK / "datasets" / "lbp" / "repeats.jsonl"
        if not path.is_file():
            return {}
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return {}
        best: dict = {}
        wanted = pathlib.Path(input_path).name if input_path else ""
        for line in lines[-40:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if opid and row.get("opid") == opid:
                best = row
            elif wanted and str(row.get("input") or "").endswith(wanted):
                best = row
        return best

    def judge_artifact(self, unit: str) -> pathlib.Path:
        scenario, model = self.split_unit(unit)
        return self._core.judge_path(scenario, model)

    def judge_for_operation(self, unit: str, opid: str) -> pathlib.Path | None:
        import judge_ledger
        return judge_ledger.path_for(opid)

    def transcript(self, unit: str) -> tuple[pathlib.Path, str, Any]:
        scenario, model = self.split_unit(unit)
        p = self._core.transcript_path(scenario, model)
        if not p.is_file():
            return p, "", None
        text = p.read_text(encoding="utf-8", errors="replace")
        try:
            chat = json.loads(text).get("chatId") or json.loads(text).get("chat_id")
        except (json.JSONDecodeError, AttributeError):
            chat = None
        return p, text, chat

    # --- naming / layout ------------------------------------------------
    def input_name(self, scenario: str, arm: str, ts: int, rnd: int) -> str:
        return self._core.loop_input_name(scenario, arm, ts, rnd)

    def newest_input(self, scenario: str, model: str):
        """Newest input file for a unit (file layout, not arena logic)."""
        return self._core.newest_input(scenario, model)

    def delta_module(self) -> str:
        return str(self._board.get("deltas_module") or "deltas_payday")

    def check_module(self) -> str:
        return str(self._board.get("checks_module") or "lbp_checks")


ADAPTERS: dict[str, type] = {GraySwanLBP.NAME: GraySwanLBP}


def register(name: str, cls: type) -> None:
    """Register an adapter class under a board-profile platform name."""
    ADAPTERS[name] = cls


def adapter_name(board: dict | None = None) -> str:
    """Which adapter this board needs: board["platform"], then $HERMES_PLATFORM."""
    env = os.environ.get("HERMES_PLATFORM")
    if env:
        return env
    if board and board.get("platform"):
        return str(board["platform"])
    return GraySwanLBP.NAME


def get_adapter(board: dict | None = None):
    """Instantiate the adapter for a board profile (defaults to Gray Swan).

    A board that names an unknown platform fails loudly here — silently falling
    back to Gray Swan would run the wrong arena's transport against a new board.
    """
    profile: dict = load_board() if board is None else board
    name = adapter_name(profile)
    try:
        cls = ADAPTERS[name]
    except KeyError:
        raise SystemExit(
            f"board {profile.get('name')!r} needs platform adapter {name!r}, "
            f"which is not registered (have: {sorted(ADAPTERS)})") from None
    return cls(board=profile)


def selftest() -> int:
    a = GraySwanLBP()
    ids = [u["id"] for u in a.units()]
    assert ids, "no units discovered"
    for unit in ids:
        scenario, model = a.split_unit(unit)
        assert a.unit_id(scenario, model) == unit, f"unit id does not round-trip: {unit}"
    assert a.version() == INTERFACE_VERSION
    assert isinstance(a.energy(), int)
    assert a.delta_module() and a.check_module()
    p, _text, _chat = a.transcript(ids[0])
    assert p.suffix == ".json" or not p.is_file()
    print(f"SELFTEST PASS — adapter {a.name()} v{a.version()}, "
          f"{len(ids)} units, energy={a.energy()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest())
