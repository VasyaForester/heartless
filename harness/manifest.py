#!/usr/bin/env python3
"""RunManifest v3 (Phase 1: Environment Intelligence).

One immutable manifest per supervisor start. Every component consumes the same
resolved runtime configuration; a mismatch between manifest and actual runtime
fails closed (driver exits before touching the arena).

Files:
  artifacts/run-manifest.json            — current manifest (pointer copy)
  artifacts/run-manifests/<run_id>.json  — immutable per-run archive
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
# One workspace may host several boards; each keeps its own pointer file.
# Payday (the default board) keeps the legacy name for compatibility.
_BOARD_ENV = os.environ.get("HERMES_BOARD") or "lucky-break-payday"
_SUFFIX = "" if _BOARD_ENV == "lucky-break-payday" else f"-{_BOARD_ENV}"
MANIFEST_PATH = WORK / "artifacts" / f"run-manifest{_SUFFIX}.json"
ARCHIVE_DIR = WORK / "artifacts" / "run-manifests"


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(WORK),
                           capture_output=True, text=True, timeout=20)
        return (p.stdout or "").strip() if p.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def build(*, lane: str, cdp: str, browser_profile: str, board_name: str | None = None) -> dict:
    from boards import load_board  # noqa: E402
    from lbcore import MODELS, DELTAS_MODULE  # noqa: E402
    from store import SCHEMA_VERSION  # noqa: E402
    try:
        import generation  # noqa: E402
        _delta_version = generation.DELTA_VERSION
    except Exception:
        _delta_version = 1

    board = load_board(board_name)
    board_file = WORK / "boards" / f"{board['name']}.json"
    prof_hash = hashlib.sha256(board_file.read_bytes()).hexdigest() if board_file.exists() else "unknown"
    # Which arena adapter ran this manifest: a run is only reproducible if the
    # platform seam is recorded, not just the board profile.
    try:
        from arena import get_adapter  # noqa: E402
        _adapter = get_adapter(board)
        _platform, _platform_iface = _adapter.name(), _adapter.version()
    except Exception as exc:  # noqa: BLE001 — never block a run on bookkeeping
        _platform, _platform_iface = f"unknown ({type(exc).__name__})", 0

    m = {
        "run_id": "run-" + time.strftime("%Y%m%d-%H%M%S"),
        "board_id": board["name"],
        "board_url": board["url"],
        "board_profile_hash": prof_hash,
        "scenario_selector": board.get("scenario_selector"),
        "platform": _platform,
        "platform_interface_version": _platform_iface,
        "lane_id": lane,
        "cdp_endpoint": cdp,
        "browser_profile": str(browser_profile),
        "harness_git_commit": _git_commit(),
        "database_schema_version": SCHEMA_VERSION,
        "delta_catalog_version": _delta_version,
        "delta_catalog_module": DELTAS_MODULE,
        "model_roster_hash": _sha_text("|".join(MODELS)),
        "pricing_source": "unknown",  # arena UI cost not exposed to the transport
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "configuration_validated": True,
        "env": {"HERMES_BOARD": os.environ.get("HERMES_BOARD"),
                "python": sys.version.split()[0]},
    }
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(m, ensure_ascii=False, indent=2)
    (ARCHIVE_DIR / f"{m['run_id']}.json").write_text(text, encoding="utf-8")
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(MANIFEST_PATH)  # atomic
    return m


def load() -> dict | None:
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def validate_split(man: dict, *, board_name: str | None = None, lane: str | None = None,
                   cdp: str | None = None) -> tuple[list[str], list[str]]:
    """Separate FATAL mismatches from recoverable drift.

    Fatal (fail closed): board, lane, cdp — running a lane against another
    board's manifest must never happen.
    Recoverable: the board profile file changed since the manifest was written.
    This distinction is not cosmetic: on 2026-11-13 a profile edit turned into a
    permanent fail-closed crash loop (driver exit 2 every 10 s, 16:58-17:0x)
    because the supervisor only builds the manifest at its OWN start.  The
    supervisor now re-baselines per driver start and this path only warns.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for msg in validate(man, board_name=board_name, lane=lane, cdp=cdp):
        (warnings if "profile hash changed" in msg else errors).append(msg)
    return errors, warnings


def validate(man: dict, *, board_name: str | None = None, lane: str | None = None,
             cdp: str | None = None) -> list[str]:
    """Return a list of mismatches (empty = consistent)."""
    out: list[str] = []
    if not man:
        return ["no manifest"]
    if board_name and man.get("board_id") != board_name:
        out.append(f"board {man.get('board_id')} != {board_name}")
    if lane and man.get("lane_id") != lane:
        out.append(f"lane {man.get('lane_id')} != {lane}")
    if cdp:
        want = str(cdp).replace("http://", "").replace("https://", "").rstrip("/")
        got = str(man.get("cdp_endpoint") or "").rstrip("/")
        if want != got:
            out.append(f"cdp {got} != {want}")
    try:
        from boards import load_board  # noqa: E402
        board = load_board(man.get("board_id"))
        bf = WORK / "boards" / f"{board['name']}.json"
        if bf.exists() and hashlib.sha256(bf.read_bytes()).hexdigest() != man.get("board_profile_hash"):
            out.append("board profile hash changed since manifest")
    except Exception:
        pass
    return out