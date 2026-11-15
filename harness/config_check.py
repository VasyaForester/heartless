#!/usr/bin/env python3
"""Single source of truth check: code, board profiles and the rule registry.

The independent review (2026-11-13) scored the project 4/10 on maturity and
called out "documentation lags implementation" as a concrete defect: `CLAUDE.md`
told the reader to run `harness/loop.py`, which had already been retired, and
`RULES.md` required one board while the code defaulted to another.  Wrong
configuration means running the wrong test profile, so this is not cosmetic.

This command makes the drift MECHANICAL: it compares what the registry and the
instructions claim against what the code actually is, and fails loudly.  It runs
in the offline suite (tests/test_config.py), so a stale claim breaks the build
instead of misleading the next session.

Checks:
  rules_present          — RULES.md exists, is versioned, mentions the harness gates
  deprecated_is_stub     — every file the registry retires is really inert
  infra_files_present    — live infrastructure named by the registry exists
  archived_absent        — retired modules are gone from harness/
  boards_valid           — every board profile loads and validates
  default_board_pinned   — the default board equals the documented one
  board_runtime_parity   — lbp.py constants match the active profile (acceptance)
  deltas_catalog         — the active board's mutation catalog loads and is non-empty
  checks_module          — the active board's pre-submit checker loads
  manifest_fields        — the run manifest carries the documented fields
  strategy_engine        — the Strategy Engine exposes its five policies
  docs_claims            — registry claims about modules match the filesystem

Run: python3 harness/config_check.py [--json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

RULES = WORK / "RULES.md"
CLAUDE = WORK / "CLAUDE.md"
README = WORK / "README.md"
TREE = WORK / "HARNESS-TREE.md"
DEFAULT_BOARD_DOCUMENTED = "lucky-break-payday"

# RULES 61: live infrastructure — never deleted, must exist
LIVE_INFRA = (
    "tools/loop_watchdog.sh",
    "tools/lane_auto.sh",
    "tools/run1.sh",
    "harness/loop.py",
    "harness/lbp.py",
)
# RULES 66 / JOURNALS: retired modules that must NOT be back in harness/
ARCHIVED = (
    "harness/lbp_update.py",
    "harness/lbp_update2.py",
    "harness/lbp_update_verdict.py",
)
# modules the registry names as the live path (RULES 67/68)
LIVE_MODULES = (
    "harness/supervisor.py",
    "harness/driver.py",
    "harness/store.py",
    "harness/attempts.py",
    "harness/manifest.py",
    "harness/evidence.py",
    "harness/judge_correlation.py",
    "harness/judge_calib.py",
    "harness/judge_ledger.py",
    "harness/strategy.py",
    "harness/strategy_bench.py",
    "harness/policy_classify.py",
    "harness/boards.py",
    "harness/lbcore.py",
)


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _result(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def check_rules() -> dict:
    text = _read(RULES)
    if not text:
        return _result("rules_present", False, "RULES.md missing")
    m = re.search(r"Версия:\s*(\S+)", text)
    gates = ["использовать", "сабмит", "правил"]
    missing = [g for g in gates if g.lower() not in text.lower()]
    return _result("rules_present", bool(m) and not missing,
                   f"version={m.group(1) if m else '?'} missing={missing}")


def check_deprecated_stub() -> dict:
    """A retired entry point must be inert: no pair journal, immediate exit."""
    loop = HERE / "loop.py"
    if not loop.is_file():
        return _result("deprecated_is_stub", False, "harness/loop.py missing")
    text = _read(loop)
    reads_pairs = "pairs.jsonl" in text and "read_text" in text
    inert = ("sys.exit(3)" in text) or ("return 3" in text) or ("SystemExit(3)" in text)
    return _result("deprecated_is_stub", (not reads_pairs) and inert,
                   f"reads_pairs={reads_pairs} inert={inert}")


def check_infra_files() -> dict:
    missing = [p for p in LIVE_INFRA if not (WORK / p).is_file()]
    return _result("infra_files_present", not missing, f"missing={missing}")


def check_archived_absent() -> dict:
    present = [p for p in ARCHIVED if (WORK / p).is_file()]
    return _result("archived_absent", not present, f"back in harness/: {present}")


def check_boards() -> dict:
    import boards
    problems = []
    for name in boards.list_boards():
        try:
            p = boards.load_board(name)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name}: {exc}")
            continue
        if p.get("sandbox"):
            # An offline sandbox board (fake arena) is allowed a non-live URL, but
            # it must SAY it is one — otherwise a sandbox could be mistaken for a
            # real target and get probed.
            if not str(p.get("_note") or "").strip():
                problems.append(f"{name}: sandbox board without a _note")
            continue
        if not p.get("url", "").startswith("https://"):
            problems.append(f"{name}: non-https url")
        if not isinstance(p.get("models"), list):
            problems.append(f"{name}: models not a list")
    return _result("boards_valid", not problems, "; ".join(problems))


def check_default_board() -> dict:
    import boards
    got = boards.DEFAULT_BOARD
    return _result("default_board_pinned", got == DEFAULT_BOARD_DOCUMENTED,
                   f"boards.DEFAULT_BOARD={got!r} documented={DEFAULT_BOARD_DOCUMENTED!r}")


def check_board_runtime_parity() -> dict:
    try:
        import acceptance
        ok, detail = acceptance.check_boards()
    except Exception as exc:  # noqa: BLE001
        return _result("board_runtime_parity", False, f"{exc}")
    return _result("board_runtime_parity", ok, str(detail)[:200])


def check_deltas() -> dict:
    try:
        from lbcore import DELTAS, DELTAS_MODULE
    except Exception as exc:  # noqa: BLE001
        return _result("deltas_catalog", False, f"lbcore import failed: {exc}")
    return _result("deltas_catalog", bool(DELTAS),
                   f"module={DELTAS_MODULE} arms={len(DELTAS)}")


def check_checks_module() -> dict:
    try:
        import lbcore
        module = __import__(lbcore.CHECKS_MODULE)
    except Exception as exc:  # noqa: BLE001
        return _result("checks_module", False, f"{exc}")
    # each board's checker exposes run_checks(); the tool map is board-specific
    has_api = hasattr(module, "run_checks")
    label = f"module={lbcore.CHECKS_MODULE} run_checks={has_api}"
    plain = module.run_checks("__unknown__", "text", "text") if has_api else {}
    label += f" keys={sorted(plain)[:6]}"
    return _result("checks_module", has_api and isinstance(plain, dict), label)


def check_manifest_fields() -> dict:
    import manifest
    required = {"run_id", "board_id", "lane_id", "cdp_endpoint", "browser_profile",
                "harness_git_commit", "database_schema_version", "delta_catalog_version",
                "model_roster_hash", "pricing_source", "started_at"}
    src = _read(HERE / "manifest.py")
    missing = [f for f in sorted(required) if f'"{f}"' not in src]
    has_split = hasattr(manifest, "validate_split")
    return _result("manifest_fields", not missing and has_split,
                   f"missing={missing} validate_split={has_split}")


def check_strategy_engine() -> dict:
    try:
        import strategy
    except Exception as exc:  # noqa: BLE001
        return _result("strategy_engine", False, f"import failed: {exc}")
    want = {"random", "ucb", "ucb_improved", "thompson", "contextual_ts"}
    missing = want - set(strategy.POLICIES)
    functions = all(hasattr(strategy, n) for n in
                    ("context_key", "arm_family", "local_reward", "judge_reward",
                     "IndependentEvaluator", "AdaptiveScheduler", "ExperienceMemory",
                     "StrategyEngine", "successive_halving_keep"))
    return _result("strategy_engine", (not missing) and functions,
                   f"policies={sorted(strategy.POLICIES)} missing={sorted(missing)} "
                   f"components={functions}")


def check_docs_claims() -> dict:
    """Registry claims about files must match the filesystem."""
    text = _read(RULES) + "\n" + _read(CLAUDE) + "\n" + _read(README)
    problems = []
    referenced = set(re.findall(r"harness/([A-Za-z0-9_]+\.py)", text))
    for name in sorted(referenced):
        path = HERE / name
        if not path.is_file():
            problems.append(f"harness/{name} named in the docs but missing")
    # a retired entry point must not be presented as the way to run the loop
    for line in _read(CLAUDE).splitlines():
        if "loop.py" in line and "supervisor" not in line and not line.strip().startswith("#"):
            problems.append(f"CLAUDE.md still points at loop.py: {line.strip()[:80]}")
    return _result("docs_claims", not problems, "; ".join(problems))


def check_readme() -> dict:
    """The public README must stay a description of THIS repository.

    A README rots the way the review found CLAUDE.md rotting (it still pointed
    at a retired entry point), so the claims that can be checked mechanically
    are checked: every entry point it names exists, the two commands it presents
    as Definition of Done exist, and the module table is not missing a live
    module of the loop.
    """
    problems = []
    text = _read(README)
    if not text.strip():
        return _result("readme", False, "README.md is missing or empty")
    for path in re.findall(r"(harness/[A-Za-z0-9_]+\.py|tools/[A-Za-z0-9_]+\.(?:sh|py)|"
                           r"boards/[A-Za-z0-9_*.]+\.json)", text):
        if "*" in path:
            continue
        if not (WORK / path).is_file():
            problems.append(f"README names {path}, which does not exist")
    for cmd in ("harness/run_offline_tests.py", "harness/config_check.py"):
        if cmd in text and not (WORK / cmd).is_file():
            problems.append(f"README presents {cmd} but the file is missing")
    for module in ("driver.py", "arena.py", "store.py", "strategy.py", "supervisor.py"):
        if module not in text:
            problems.append(f"README module table does not mention {module}")
    docs = ("RULES.md", "CLAUDE.md", "HARNESS-TREE.md")
    for doc in docs:
        if doc not in text:
            problems.append(f"README does not point at {doc}")
        elif not (WORK / doc).is_file():
            problems.append(f"README points at {doc}, which does not exist")
    return _result("readme_matches_repo", not problems, "; ".join(problems))


def check_tree_claims() -> dict:
    """HARNESS-TREE.md must not describe the retired contour as the live one.

    The review found exactly this rot (CLAUDE.md still pointed at loop.py, the
    loop had moved to supervisor.py).  The tree doc had the same defect: it
    labelled loop.py LIVE and called the v2 loop "not live".  These checks make
    the claim mechanical instead of trusting the next editor.
    """
    problems = []
    text = _read(TREE)
    if not text.strip():
        return _result("tree_doc", False, "HARNESS-TREE.md is missing or empty")
    for line in text.splitlines():
        if "loop.py" in line and "LIVE" in line and "RETIRED" not in line:
            problems.append(f"tree doc still calls loop.py live: {line.strip()[:80]}")
        if "V2 не live" in line:
            problems.append("tree doc still claims the v2 loop is not live")
    if "supervisor.py" not in text:
        problems.append("tree doc does not name supervisor.py as the loop entry point")
    if "README.md" not in text:
        problems.append("tree doc does not point at README.md (current overview)")
    return _result("tree_doc_matches_reality", not problems, "; ".join(problems))


def check_live_modules() -> dict:
    missing = [p for p in LIVE_MODULES if not (WORK / p).is_file()]
    return _result("live_modules_present", not missing, f"missing={missing}")


ARCHIVE_JOURNAL = "pairs.jsonl"
JOURNAL_CONSUMERS = ("lbp.py", "lbp_plan.py", "lbp_report.py")


def check_single_journal() -> dict:
    """ONE journal: the matrix is read from harness/journal.py, never from the archive.

    Grok's review (2026-11-15, axis "one journal": 4/10) named three live readers that
    still counted pairs from the v1 journal datasets/lbp/pairs.jsonl — and one of them
    still WROTE it, so an archive nobody maintained was being treated as the present.
    This check is the axis-10 invariant: it goes red the moment live code reads the
    archive as data again.
    """
    problems = []
    for name in JOURNAL_CONSUMERS:
        path = WORK / "harness" / name
        if not path.is_file():
            problems.append(f"harness/{name} missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            if ARCHIVE_JOURNAL in code and any(
                    k in code for k in ("read_text(", "open(", "glob(", "json.loads(")):
                problems.append(f"harness/{name}:{i} reads the archive as data")
        if "journal" not in text:
            problems.append(f"harness/{name} does not go through harness/journal.py")
    jr = WORK / "harness" / "journal.py"
    if not jr.is_file():
        problems.append("harness/journal.py (the single reader) is missing")
    else:
        jt = jr.read_text(encoding="utf-8", errors="replace")
        for needed in ("def live_matrix", "def render_markdown", "def summary"):
            if needed not in jt:
                problems.append(f"harness/journal.py lost {needed}")
    return _result("single_journal", not problems, "; ".join(problems))


CHECKS = (check_rules, check_deprecated_stub, check_single_journal, check_infra_files, check_archived_absent,
          check_boards, check_default_board, check_board_runtime_parity, check_deltas,
          check_checks_module, check_manifest_fields, check_strategy_engine,
          check_docs_claims, check_readme, check_tree_claims, check_live_modules)


def run() -> dict:
    results = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as exc:  # noqa: BLE001
            results.append(_result(fn.__name__, False, f"raised {exc}"))
    failed = [r for r in results if not r["ok"]]
    return {"checks": len(results), "failed": len(failed),
            "ok": not failed, "results": results}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    report = run()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    if not a.quiet:
        for r in report["results"]:
            print(f"[{'PASS' if r['ok'] else 'FAIL'}] {r['check']}: {r['detail']}")
        print(f"{report['checks'] - report['failed']}/{report['checks']} checks passed")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
