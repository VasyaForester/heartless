#!/usr/bin/env python3
"""A deterministic offline arena — the portability proof, not a simulator of Gray Swan.

Advice taken (frontier review, 2026-11-14): "write a stub adapter with
deterministic behaviour and run the whole supervisor → driver → store cycle
through it, without a browser.  If that stub takes an hour to write and the cycle
works, the abstraction holds."

What it is: a full implementation of `ArenaAdapter` whose transport is the local
filesystem.  A probe writes a transcript, a signals record and a judge artifact
keyed by the operation id (`opid`), and spends energy from a counter file.  The
verdict is deterministic: the input text containing the solve marker (env
`HERMES_FAKE_SOLVE_MARKER`, default "SOLVE") is accepted, anything else rejected —
so a test can drive both outcomes without randomness.

What it is NOT: a model of Gray Swan's UI, judge criteria or timing.  A green run
here proves the LOOP and the seam (naming, evidence binding, energy, "no verdict
yet"), never that a policy works against the real arena.

State layout (all under $HERMES_FAKE_ROOT, default artifacts/fake-arena):
    energy.json          remaining energy
    ops/<opid>.json      signals + verdict for ONE operation (never per unit)
    judges/<unit>.json   newest verdict for a unit (mirrors a platform artifact)
    transcripts/<unit>.txt  last reply text
    inputs/              sandbox copy of the probe inputs
"""

import json
import os
import pathlib
import re
import time

import arena

ROOT_ENV = "HERMES_FAKE_ROOT"
SOLVE_MARKER = os.environ.get("HERMES_FAKE_SOLVE_MARKER", "SOLVE")
DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent / "artifacts" / "fake-arena"
START_ENERGY = int(os.environ.get("HERMES_FAKE_ENERGY", "1000"))


def _chat(unit: str) -> str:
    """A stable hex chat id per unit (mirrors chatId=<hex> in the platform URL)."""
    return f"{abs(hash(unit)) % (16 ** 8):08x}"


def _safe(name: str) -> str:
    """A filename that is legal on Windows too: operation ids carry ':' and '|'."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))


class FakeArena:
    """Filesystem-backed arena.  Deterministic, offline, no browser.

    Platform name is "fake" so the autoload convention holds literally:
    platform "fake" -> harness/arena_fake.py (see arena.get_adapter).
    """

    NAME = "fake"
    # The driver refuses to start without a browser target unless the adapter says
    # it does not need one — this is that declaration.
    NEEDS_BROWSER = False

    def __init__(self, board: dict | None = None):
        import boards
        self.board = board if board is not None else boards.load_board()
        self.root = pathlib.Path(os.environ.get(ROOT_ENV) or DEFAULT_ROOT)
        for sub in ("ops", "judges", "transcripts", "inputs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self._scenarios = dict(self.board.get("scenario_titles") or {})
        self._models = list(self.board.get("models") or [])
        self._by_scenario = dict(self.board.get("models_by_scenario")
                                 or {sid: list(self._models) for sid in self._scenarios})

    # --- identity / discovery -------------------------------------------
    def name(self) -> str:
        return self.NAME

    def version(self) -> int:
        return arena.INTERFACE_VERSION

    def scenarios(self) -> dict:
        return dict(self._scenarios)

    def models(self) -> list:
        seen, out = set(), []
        for models in self._by_scenario.values():
            for m in models:
                if m not in seen:
                    seen.add(m)
                    out.append(m)
        return out

    def models_for(self, scenario: str) -> list:
        return list(self._by_scenario.get(scenario, []))

    def solved_seed(self) -> dict:
        return {}

    def unit_id(self, scenario: str, model: str) -> str:
        return f"{scenario}|{model}"

    def split_unit(self, unit: str):
        scenario, _, model = str(unit).partition("|")
        return scenario, model

    def units(self) -> list:
        out = []
        for sid in self._scenarios:
            for model in self.models_for(sid):
                out.append({"id": self.unit_id(sid, model), "scenario": sid,
                            "model": model, "solved": False})
        return out

    # --- probe transport -------------------------------------------------
    def energy(self, target: str = "") -> int:
        path = self.root / "energy.json"
        try:
            return int(json.loads(path.read_text(encoding="utf-8"))["energy"])
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            path.write_text(json.dumps({"energy": START_ENERGY}), encoding="utf-8")
            return START_ENERGY

    def _spend(self, amount: int) -> None:
        left = max(0, self.energy() - amount)
        (self.root / "energy.json").write_text(json.dumps({"energy": left}), encoding="utf-8")

    def probe(self, target: str, unit: str, input_path: str, wait_s: int,
              opid: str) -> arena.ProbeResult:
        scenario, model = self.split_unit(unit)
        if scenario not in self._scenarios or model not in self.models_for(scenario):
            # The contract requires a non-zero rc (and no raise) for a bad unit, so
            # the loop can count errors instead of dying.
            return arena.ProbeResult(rc=2, err=f"unknown unit {unit!r}")
        src = pathlib.Path(input_path)
        if not src.is_file():
            return arena.ProbeResult(rc=3, err=f"input not found: {input_path}")
        text = src.read_text(encoding="utf-8", errors="replace")
        sandbox_input = self.root / "inputs" / f"{_safe(opid)}.txt"
        sandbox_input.write_text(text, encoding="utf-8")
        solved = SOLVE_MARKER in text
        pcts = [100, 100] if solved else [10, 0]
        signals = {
            "probe_ok": True, "fill_ok": True, "sent_ok": True, "send": "sent",
            "tool_invoked": True, "check_ready": solved,
            "failure_class": "NONE_READY" if solved else "A_TOOL_NOT_CALLED",
            "refusal_category": None if solved else "category_block",
            "invalid": None if solved else "refused",
            "reply_tail": ("SOLVED" if solved else "I cannot help with that") + " " + opid[:8],
            "opid": opid, "unit": unit, "input_sha256": abs(hash(text)) % (10 ** 12),
        }
        # The artifact mirrors the REAL platform shape on purpose: operationId
        # (camelCase), criteriaPercents/evidence as [{text}] with "NN%" inside,
        # status in {accepted,rejected,...}.  A fake that speaks a different
        # dialect would test nothing (found 2026-11-14 by running the loop on it).
        verdict = {
            "operationId": opid,
            "status": "accepted" if solved else "rejected",
            "criteriaPercents": [{"text": f"Criterion {i + 1}: {p}%"}
                                 for i, p in enumerate(pcts)],
            "evidence": [{"text": "fake arena: deterministic verdict"}],
            "submittedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "url": f"https://sandbox.local/chat?chatId={_chat(unit)}",
        }
        (self.root / "ops" / f"{_safe(opid)}.json").write_text(
            json.dumps({"signals": signals, "verdict": verdict, "unit": unit},
                       ensure_ascii=False),
            encoding="utf-8")
        (self.root / "judges" / f"{_safe(unit)}.json").write_text(
            json.dumps(verdict, ensure_ascii=False), encoding="utf-8")
        (self.root / "transcripts" / f"{_safe(unit)}.txt").write_text(
            signals["reply_tail"], encoding="utf-8")
        self._spend(2)  # the board's cost model: one message + one judge run
        return arena.ProbeResult(rc=0, out=f"fake probe ok opid={opid}",
                                 err="", signals=signals)

    # --- evidence -------------------------------------------------------
    def _op(self, opid: str) -> dict:
        path = self.root / "ops" / f"{_safe(opid)}.json"
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def signals(self, opid: str, input_path: str = "") -> dict:
        return dict(self._op(opid).get("signals") or {})

    def judge_artifact(self, unit: str) -> pathlib.Path:
        return self.root / "judges" / f"{_safe(unit)}.json"

    def judge_for_operation(self, unit: str, opid: str) -> pathlib.Path | None:
        """Bound to the OPERATION: a foreign opid must resolve to nothing."""
        op = self._op(opid)
        verdict = op.get("verdict")
        if not verdict or op.get("unit") != unit:
            return None
        path = self.root / "ops" / f"{_safe(opid)}.verdict.json"
        path.write_text(json.dumps(verdict, ensure_ascii=False), encoding="utf-8")
        return path

    def transcript(self, unit: str):
        path = self.root / "transcripts" / f"{_safe(unit)}.txt"
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        return path, text, (_chat(unit) if text else None)

    # --- naming / layout -------------------------------------------------
    def input_name(self, scenario: str, arm: str, ts: int, rnd: int) -> str:
        prefix = str(self.board.get("file_prefix") or "fake")
        return f"{prefix}-{scenario}-{arm}-{ts}-{rnd}.txt"

    def newest_input(self, scenario: str, model: str):
        """Self-seeding: the sandbox writes its own bootstrap probe when the
        workspace has none for this scenario (a live board always has one), so the
        offline cycle needs no committed fixtures."""
        ws_inputs = pathlib.Path(__file__).resolve().parent.parent / "inputs"
        files = sorted(ws_inputs.glob(f"*{scenario}*"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0]
        seed = self.root / "inputs" / f"seed-{scenario}.txt"
        if not seed.is_file():
            seed.write_text(
                f"{scenario} bootstrap probe for {model}\n"
                f"# offline sandbox input written by harness/arena_fake.py\n",
                encoding="utf-8")
        return seed

    def delta_module(self) -> str:
        return str(self.board.get("deltas_module") or "")

    def check_module(self) -> str:
        return str(self.board.get("checks_module") or "")


arena.register(FakeArena.NAME, FakeArena)
