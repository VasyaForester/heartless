#!/usr/bin/env python3
"""Local hackathon setup, append-only attempts, and source-only submissions.

Python 3.9+, standard library only. Setup and local checks send no evaluation
inputs. The arena command delegates explicitly requested browser operations
to the companion Node engine. No dependencies are installed automatically.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import html
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import winquiet  # noqa: E402

TRACKS = frozenset({"Chat", "Image", "Agent", "Indirect"})
STATUSES = frozenset({"pending", "completed", "error"})
JUDGE_STATUSES = frozenset({"pending", "passed", "failed", "unknown"})
REQUIRED_SKILLS = ("gray-swan-cdp-automation", "gray-swan-arena-attempt-tracking", "gray-swan-training-solver")
CDP_URL = os.environ.get("HACKATHON_CDP_URL", "http://127.0.0.1:9223")
TRAINING_URL = "https://app.grayswan.ai/training"
SOURCE_SUFFIXES = frozenset({
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".txt", ".rst", ".sh", ".bash", ".zsh",
    ".ps1", ".bat", ".cmd", ".css", ".html", ".svg", ".sql", ".rs", ".go", ".c",
    ".h", ".cpp", ".hpp", ".java", ".kt", ".rb", ".r", ".xml", ".lock",
})
SOURCE_NAMES = frozenset({"dockerfile", "makefile", "license", "licence", "notice"})
EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".local", ".venv", "venv", "__pycache__", "node_modules",
    "attempts", "artifacts", "input", "inputs", "logs", "transcripts", "history", "histories",
    "browser-data", "browser-profile", "browser-profiles", "chrome-debug", "cookies",
    "sessions", "auth", "credentials", "secrets", "cache", "state", "screenshots",
    "downloads", "outputs", "results", ".pytest_cache", ".mypy_cache",
})
PRIVATE_NAME = re.compile(
    r"(?:^|[._-])(?:auth|credentials?|secrets?|cookies?|history|transcripts?|"
    r"sessions?|attempts?|journal|state|logs?|screenshots?)(?:[._-]|$)", re.I)
MAX_SOURCE_BYTES = 5 * 1024 * 1024
TOKEN_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----")),
    ("API token", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{18,}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{24,})\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{18,}\b")),
    ("Google API key", re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.I)),
)
PERSONAL_PATHS = re.compile(
    r"/(?:Users|home)/[A-Za-z0-9._@ -]+/|[A-Za-z]:[\\/]+Users[\\/]+[^\\/\r\n\"'<>]+[\\/]",
    re.I,
)
SECRET_ASSIGNMENT = re.compile(
    r"[\"']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"password|passwd|authorization|secret|token)[\"']?\s*[:=]\s*"
    r"(?P<quote>[\"'])(?P<value>[^\"'\r\n]{6,})(?P=quote)", re.I,
)
UNQUOTED_SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|password|passwd|secret|token)\s*[:=]\s*(?P<value>[A-Za-z0-9_./+=-]{12,})\s*(?:#.*)?$"
)


class HelperError(Exception):
    """A useful, non-secret error suitable for the command line."""


@dataclass(frozen=True)
class Layout:
    profile: Path

    @classmethod
    def current(cls) -> "Layout":
        return cls(Path(__file__).resolve().parents[2])

    @property
    def workspace(self) -> Path:
        return self.profile / "workspace"

    @property
    def harness(self) -> Path:
        return self.workspace / "harness"

    @property
    def journal(self) -> Path:
        return self.workspace / "attempts" / "attempts.jsonl"


def is_link(path: Path) -> bool:
    """Detect POSIX links and Windows junction/reparse points without following."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def reject_link_components(path: Path, root: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise HelperError("Path must stay inside the profile.") from exc
    current = root
    for part in ("", *relative.parts):
        current = current / part if part else current
        if is_link(current):
            raise HelperError(f"Refusing a symlink or junction: {current.name}")


def setup(layout: Layout, write_config: bool = False) -> dict:
    for directory in (layout.journal.parent, layout.workspace / "artifacts", layout.workspace / "inputs"):
        reject_link_components(directory, layout.profile)
        directory.mkdir(parents=True, exist_ok=True)
    reject_link_components(layout.journal, layout.profile)
    fd = os.open(layout.journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.close(fd)
    if write_config:
        config = layout.harness / ".local.json"
        reject_link_components(config, layout.profile)
        if not config.exists():
            config.write_text(json.dumps({"cdpUrl": CDP_URL}, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "journal": "workspace/attempts/attempts.jsonl", "installed": []}


@lru_cache(maxsize=1)
def managed_environment() -> dict:
    """Read installed Hermes runtimes, without installing packages or changing config."""
    cli = shutil.which("hermes")
    if not cli:
        candidate = Path.home() / ".local" / "bin" / "hermes"
        cli = str(candidate) if candidate.is_file() else None
    if cli:
        try:
            result = subprocess.run([cli, "pm", "env", "node", "chromium"],
                                    capture_output=True, text=True, timeout=15, check=False,
                                    **winquiet.windowless_kwargs())
            value = json.loads(result.stdout)
            if result.returncode == 0 and isinstance(value, dict):
                return {key: value[key] for key in ("PATH", "AGENT_BROWSER_EXECUTABLE_PATH")
                        if isinstance(value.get(key), str)}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return {}


def discover_node() -> tuple[str, dict]:
    managed = managed_environment()
    candidates = [os.environ.get("HACKATHON_NODE"),
                  shutil.which("node", path=managed.get("PATH", os.environ.get("PATH", ""))),
                  shutil.which("node")]
    roots = [Path.home() / ".hermes" / "tools"]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "hermes" / "tools")
    for root in roots:
        for pattern in ("node-*/bin/node", "node-*/node.exe"):
            candidates.extend(str(p) for p in sorted(root.glob(pattern), reverse=True) if p.is_file())
    for node in dict.fromkeys(p for p in candidates if p):
        try:
            result = subprocess.run(
                [node, "-e", "console.log(JSON.stringify({version:process.versions.node,webSocket:typeof WebSocket==='function'}))"],
                capture_output=True, text=True, timeout=10, check=False,
                **winquiet.windowless_kwargs(),
            )
            info = json.loads(result.stdout)
            if result.returncode or int(info["version"].split(".")[0]) < 22 or info.get("webSocket") is not True:
                continue
            return node, {**info, "executable": node}
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            continue
    raise HelperError("Node.js 22+ not found. First run: hermes pm install node. Reopen Hermes and retry doctor. Alternatively install https://nodejs.org/ or set HACKATHON_NODE.")


def _pm_roots(layout: Layout) -> list[Path]:
    roots = [Path.home() / ".hermes" / "tools"]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "hermes" / "tools")
    if layout.profile.parent.name == "profiles":
        roots.append(layout.profile.parent.parent / "tools")
    if os.environ.get("HERMES_RUNTIME_DIR"):
        roots.append(Path(os.environ["HERMES_RUNTIME_DIR"]))
    return list(dict.fromkeys(roots))


def chrome_candidates(layout: Layout) -> list[Path]:
    """Inspect known executable locations; never invoke a Hermes PM launcher."""
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    managed_chrome = managed_environment().get("AGENT_BROWSER_EXECUTABLE_PATH")
    if managed_chrome:
        candidates.insert(0, Path(managed_chrome))
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "Google/Chrome/Application/chrome.exe")
    for executable in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))
    # Hermes PM's read-only store uses chromium* entries and CfT platform folders.
    patterns = (
        "chrome-mac-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-linux*/chrome", "chrome-win*/chrome.exe", "chrome-linux/chrome",
    )
    for root in _pm_roots(layout):
        if not root.is_dir() or is_link(root):
            continue
        for entry in sorted(root.glob("chromium*"))[:30]:
            if not entry.is_dir() or is_link(entry):
                continue
            for pattern in patterns:
                candidates.extend(sorted(entry.glob(pattern)))
    return [path for path in dict.fromkeys(candidates) if path.is_file()]


def installed_skills(layout: Layout) -> list[str]:
    root = layout.profile / "skills"
    if not root.exists() or is_link(root):
        return []
    names = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = [name for name in dirs if not is_link(base / name) and not name.startswith(".")]
        if "SKILL.md" in files and not is_link(base / "SKILL.md"):
            names.append(base.name)
    return sorted(set(names))


def engine(layout: Layout, command: str, extra=()) -> dict:
    node, _ = discover_node()
    script = layout.harness / "engine" / "arena.mjs"
    if not script.is_file():
        raise HelperError("Missing harness/engine/arena.mjs.")
    env = os.environ.copy()
    env["HACKATHON_CDP_URL"] = CDP_URL
    try:
        result = subprocess.run([node, str(script), command, *extra], cwd=layout.workspace,
                                env=env, capture_output=True, text=True, timeout=360, check=False,
                                **winquiet.windowless_kwargs())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HelperError(f"Engine {command} could not finish: {type(exc).__name__}.") from exc
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else None
    except ValueError:
        output = result.stdout.strip()
    if result.returncode:
        # Engine diagnostics may include browser page text; keep them local to this invocation.
        raise HelperError(f"Engine {command} failed ({result.returncode}): {(result.stderr or result.stdout).strip()[:1500]}")
    return {"ok": True, "command": command, "result": output}


def doctor(layout: Layout, browser: bool = False) -> dict:
    report = {"python": sys.version.split()[0], "pythonSupported": sys.version_info >= (3, 9),
              "profile": str(layout.profile), "workspace": str(layout.workspace),
              "currentDirectory": os.getcwd(), "journal": str(layout.journal), "cdpUrl": CDP_URL,
              "browserTransportAvailable": None, "arenaTabAvailable": None,
              "matchingArenaTabs": None,
              "arenaReadiness": {"login": "not_verified", "training": "not_verified", "judge": "not_verified",
                                 "note": "Tab metadata does not verify login, Training selection, or judge readiness."}}
    try:
        _, report["node"] = discover_node()
    except HelperError as exc:
        report["nodeError"] = str(exc)
    report["chromeCandidates"] = [str(path) for path in chrome_candidates(layout)]
    report["skills"] = installed_skills(layout)
    report["missingSkills"] = sorted(set(REQUIRED_SKILLS) - set(report["skills"]))
    report["enginePresent"] = (layout.harness / "engine" / "arena.mjs").is_file()
    if browser:
        report["browserTransportAvailable"] = False
        report["arenaTabAvailable"] = False
        report["matchingArenaTabs"] = 0
        try:
            report["browser"] = engine(layout, "tabs")
            report["browserTransportAvailable"] = True
            tabs = report["browser"]["result"]
            if not isinstance(tabs, list):
                raise HelperError("Engine returned unexpected Arena tab metadata; expected an array.")
            report["matchingArenaTabs"] = len(tabs)
            report["arenaTabAvailable"] = bool(tabs)
            if not tabs:
                report["arenaTabMessage"] = "CDP is reachable, but no matching Arena tab is open. Open Arena in the dedicated browser."
        except HelperError as exc:
            report["browserError"] = str(exc)
    report["ok"] = not (not report["pythonSupported"] or report.get("nodeError") or report.get("browserError") or report["missingSkills"]
                         or not report["enginePresent"] or not report["chromeCandidates"]
                         or (browser and not report["arenaTabAvailable"]))
    return report


def launch_browser(layout: Layout, chrome: str | None = None, url: str = TRAINING_URL) -> dict:
    destination = urlsplit(url)
    if destination.scheme != "https" or destination.netloc != "app.grayswan.ai":
        raise HelperError("Use an https://app.grayswan.ai/ URL for this Arena browser.")
    endpoint = urlsplit(CDP_URL)
    if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost") or endpoint.username or endpoint.password or endpoint.path not in ("", "/") or endpoint.query or endpoint.fragment or endpoint.port is None:
        raise HelperError("HACKATHON_CDP_URL must be an unauthenticated HTTP loopback endpoint with explicit port, e.g. http://127.0.0.1:9223.")
    port = endpoint.port
    # Reuse an already reachable local browser; never kill an occupied process.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        result = engine(layout, "open", ["--url", url, "--cdp", CDP_URL])
        return {"ok": True, "reusedBrowser": True, "cdpUrl": CDP_URL, "page": result["result"],
                "note": "Existing local CDP browser reused. Check the visible account before evaluation."}
    candidates = [Path(chrome).expanduser()] if chrome else chrome_candidates(layout)
    if not candidates or not candidates[0].is_file():
        raise HelperError("Chrome not found. Install Chrome or pass --chrome /path/to/browser-executable.")
    browser_data = layout.profile / "browser-data"
    reject_link_components(browser_data, layout.profile)
    browser_data.mkdir(parents=True, exist_ok=True)
    command = [str(candidates[0]), f"--user-data-dir={browser_data}",
               "--remote-debugging-address=127.0.0.1", f"--remote-debugging-port={port}",
               "--no-first-run", "--no-default-browser-check", url]
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **options)
    except OSError as exc:
        raise HelperError(f"Could not start Chrome: {type(exc).__name__}.") from exc
    return {"ok": True, "pid": process.pid, "cdpUrl": CDP_URL,
            "browserData": "browser-data", "openedUrl": url,
            "note": "Arena opened. Sign in in this browser if requested, then run doctor --browser."}


def make_image(layout: Layout, text_file: Path, destination: Path, width=1280, height=720, font_size=48) -> dict:
    """Render participant text via an isolated Chrome CDP page, never the Arena browser."""
    if not (128 <= width <= 2048 and 128 <= height <= 2048 and 16 <= font_size <= 256):
        raise HelperError("Image dimensions must be 128..2048; font size 16..256.")
    text = text_file.read_text(encoding="utf-8-sig")
    if not text.strip() or len(text) > 20000:
        raise HelperError("Image text must contain 1..20000 characters.")
    candidates = chrome_candidates(layout)
    if not candidates:
        raise HelperError("Chromium/Chrome is required. Run: hermes pm install chromium")
    node, _ = discover_node()
    renderer = layout.harness / "render-image.mjs"
    if not renderer.is_file():
        raise HelperError("Missing harness/render-image.mjs. Re-import the complete profile package.")
    destination = destination.resolve()
    if destination.exists():
        raise HelperError("Image destination already exists; choose a new filename.")
    with tempfile.TemporaryDirectory(prefix="arena-image-") as tmp:
        directory = Path(tmp)
        page = directory / "image.html"
        screenshot = directory / "image.png"
        document = ('<!doctype html><meta charset="utf-8"><style>'
                    f'html,body{{margin:0;width:{width}px;height:{height}px;background:white;overflow:hidden;}}'
                    f'main{{box-sizing:border-box;padding:48px;color:#111;font:{font_size}px/1.25 Arial,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;}}'
                    '</style><main>' + html.escape(text) + '</main>')
        page.write_text(document, encoding="utf-8")
        command = [node, str(renderer), "--chrome", str(candidates[0]),
                   "--html", str(page), "--out", str(screenshot),
                   "--width", str(width), "--height", str(height)]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=60,
                                     check=False, **winquiet.windowless_kwargs())
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HelperError(f"Image renderer failed: {type(exc).__name__}.") from exc
        if process.returncode or not screenshot.is_file():
            raise HelperError("Chrome did not create the PNG: " + (process.stderr or process.stdout).strip()[:1000])
        try:
            render_info = json.loads(process.stdout)
        except ValueError as exc:
            raise HelperError("Image renderer returned invalid status JSON.") from exc
        payload = screenshot.read_bytes()
        if (len(payload) < 24 or not payload.startswith(b"\x89PNG\r\n\x1a\n")
                or int.from_bytes(payload[16:20], "big") != width
                or int.from_bytes(payload[20:24], "big") != height):
            raise HelperError("Renderer returned an invalid PNG or incorrect dimensions.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(payload)
    return {"ok": True, "image": str(destination), "width": width, "height": height,
            "textClipped": bool(render_info.get("textClipped")),
            "note": "Preview the PNG before uploading. If textClipped is true, shorten text or reduce font size. No Arena submission was made."}


def validate_attempt(value: object) -> dict:
    if not isinstance(value, dict):
        raise HelperError("Attempt must be a JSON object.")
    result = dict(value)
    for key in ("attemptId", "track", "scenarioId", "modelId", "status"):
        text = result.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > 200 or any(ord(c) < 32 for c in text):
            raise HelperError(f"{key} must be a nonempty single-line string (at most 200 characters).")
        result[key] = text.strip()
    if result["track"] not in TRACKS:
        raise HelperError("track must be Chat, Image, Agent, or Indirect.")
    if result["status"] not in STATUSES:
        raise HelperError("status must be pending, completed, or error.")
    result.setdefault("judgeStatus", "unknown")
    if not isinstance(result["judgeStatus"], str) or result["judgeStatus"] not in JUDGE_STATUSES:
        raise HelperError("judgeStatus must be pending, passed, failed, or unknown.")
    result.setdefault("judgeEvidence", "")
    if not isinstance(result["judgeEvidence"], str):
        raise HelperError("judgeEvidence must be a string containing exact evidence or its source.")
    if result["judgeStatus"] == "passed" and result["status"] != "completed":
        raise HelperError("A passed judge result requires status completed.")
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise HelperError("Attempt contains a value that is not valid JSON.") from exc
    return result


@contextlib.contextmanager
def journal_lock(path: Path):
    deadline = time.monotonic() + 5
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise HelperError("Journal is locked by another record operation; retry after it finishes.")
            time.sleep(0.05)
    try:
        os.close(descriptor)
        yield
    finally:
        path.unlink()


def record(layout: Layout, value: object) -> dict:
    event = validate_attempt(value)  # No writes occur before all validation succeeds.
    event["eventId"] = str(uuid.uuid4())
    event["recordedAt"] = datetime.now(timezone.utc).isoformat()
    encoded = (json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    reject_link_components(layout.journal, layout.profile)
    layout.journal.parent.mkdir(parents=True, exist_ok=True)
    with journal_lock(layout.journal.with_suffix(".lock")):
        # Refuse to append to a damaged journal, including a truncated final line.
        read_events(layout)
        descriptor = os.open(layout.journal, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise HelperError("Could not append the full event.")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return {"ok": True, "eventId": event["eventId"], "attemptId": event["attemptId"]}


def read_events(layout: Layout) -> list[dict]:
    reject_link_components(layout.journal, layout.profile)
    if not layout.journal.exists():
        return []
    events = []
    with layout.journal.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                if not line.endswith("\n"):
                    raise ValueError("truncated line")
                events.append(validate_attempt(json.loads(line)))
            except (ValueError, HelperError) as exc:
                raise HelperError(f"Journal event {number} is invalid; preserve the file and inspect it locally.") from exc
    return events


def summary(layout: Layout) -> dict:
    events = read_events(layout)
    latest = {event["attemptId"]: event for event in events}
    pairs = set()
    covered = set()
    counts = {status: 0 for status in sorted(STATUSES)}
    attempts = []
    for attempt_id, event in sorted(latest.items()):
        counts[event["status"]] += 1
        covered.add((event["track"], event["scenarioId"]))
        evidenced = bool(event["judgeEvidence"].strip())
        if event["judgeStatus"] == "passed" and evidenced:
            pairs.add((event["track"], event["scenarioId"], event["modelId"]))
        attempts.append({"attemptId": attempt_id, "track": event["track"], "scenarioId": event["scenarioId"],
                         "modelId": event["modelId"], "status": event["status"],
                         "judgeStatus": event["judgeStatus"], "hasJudgeEvidence": evidenced})
    return {"schemaVersion": 1, "totalEvents": len(events), "totalAttempts": len(latest),
            "statusCounts": counts, "confirmedPassedPairs": len(pairs), "coveredScenarios": len(covered),
            "confirmedPassedScenarios": len({(track, scenario) for track, scenario, _ in pairs}),
            "coverageDefinition": "Distinct (track, scenarioId) with any recorded attempt; not a tiebreak.",
            "confirmedPairs": [dict(zip(("track", "scenarioId", "modelId"), pair)) for pair in sorted(pairs)],
            "attempts": attempts}


def summary_csv(report: dict) -> str:
    stream = io.StringIO(newline="")
    fields = ("attemptId", "track", "scenarioId", "modelId", "status", "judgeStatus", "hasJudgeEvidence")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    # Spreadsheet formula injection must not turn a participant ID into executable content.
    for row in report["attempts"]:
        writer.writerow({key: ("'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value)
                         for key, value in row.items()})
    return stream.getvalue()


def scan_text(text: str, name: str) -> list[str]:
    findings = [f"{name}: {label}" for label, pattern in TOKEN_PATTERNS if pattern.search(text)]
    if PERSONAL_PATHS.search(text):
        findings.append(f"{name}: absolute personal path")
    for match in (*SECRET_ASSIGNMENT.finditer(text), *UNQUOTED_SECRET_ASSIGNMENT.finditer(text)):
        value = match.group("value").strip()
        if not value or value.upper().startswith(("YOUR_", "REPLACE_", "EXAMPLE_", "CHANGEME", "${", "<")):
            continue
        findings.append(f"{name}: possible credential assignment")
        break
    return findings


def _private_file(path: Path) -> bool:
    name = path.name.casefold()
    if name.startswith(".env") or name in {".local.json", "npmrc", ".npmrc", "id_rsa", "id_ed25519"}:
        return True
    return bool(PRIVATE_NAME.search(name)) and path.suffix.lower() not in {".py", ".js", ".ts", ".mjs", ".cjs"}


def _source_entries(root: Path, archive_prefix: str) -> tuple[list[tuple[str, bytes]], list[str], list[str]]:
    entries, excluded, findings = [], [], []
    if not root.exists():
        return entries, excluded, findings
    if is_link(root):
        return [], [], [f"{archive_prefix}: symlink or junction"]
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        descend = []
        for dirname in sorted(dirs):
            child = base / dirname
            label = f"{archive_prefix}/{child.relative_to(root).as_posix()}"
            if is_link(child):
                findings.append(f"{label}: symlink or junction")
            elif dirname.casefold() in EXCLUDED_DIRS and not (child / "SKILL.md").is_file():
                excluded.append(label + "/")
            else:
                descend.append(dirname)
        dirs[:] = descend
        for filename in sorted(files):
            path = base / filename
            label = f"{archive_prefix}/{path.relative_to(root).as_posix()}"
            if is_link(path):
                findings.append(f"{label}: symlink or junction")
                continue
            if not path.is_file():
                findings.append(f"{label}: not a regular file")
                continue
            if _private_file(path) or (path.suffix.lower() not in SOURCE_SUFFIXES and filename.casefold() not in SOURCE_NAMES):
                excluded.append(label)
                continue
            if path.stat().st_size > MAX_SOURCE_BYTES:
                findings.append(f"{label}: source file exceeds 5 MiB")
                continue
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                findings.append(f"{label}: source is not UTF-8 text")
                continue
            findings.extend(scan_text(text, label))
            if path.suffix.lower() == ".json":
                try:
                    data = json.loads(text)
                    if isinstance(data, dict) and ("attemptId" in data or {"input", "response"} <= data.keys()
                                                  or {"sessionId", "messages"} <= data.keys()):
                        findings.append(f"{label}: possible attempt or transcript data")
                except ValueError:
                    findings.append(f"{label}: invalid JSON source")
            entries.append((label, raw))
    return entries, excluded, findings


def export_submission(layout: Layout, destination: Path) -> dict:
    destination = destination.expanduser().absolute()
    if destination.exists() or is_link(destination):
        raise HelperError("Submission destination already exists; choose a new filename.")
    report = summary(layout)
    entries, excluded, findings = [], [], []
    for root, prefix in ((layout.harness, "harness"), (layout.profile / "skills", "skills")):
        selected, skipped, suspicious = _source_entries(root, prefix)
        entries.extend(selected)
        excluded.extend(skipped)
        findings.extend(suspicious)
    if not any(name == "harness/hackathon.py" for name, _ in entries):
        findings.append("harness/hackathon.py: missing source")
    generated = {
        "summary.json": json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        "summary.csv": summary_csv(report),
    }
    for name, text in generated.items():
        findings.extend(scan_text(text, name))
        entries.append((name, text.encode("utf-8")))
    if findings:
        raise HelperError("Submission refused. Review locally (values are not printed):\n" + "\n".join(sorted(set(findings))))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="submission-build-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "submission.zip"
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(entries):
                item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.create_system = 3
                item.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(item, raw)
        # Exclusive create keeps an existing submission immutable, including a race.
        try:
            with destination.open("xb") as target, staged.open("rb") as source:
                shutil.copyfileobj(source, target)
        except FileExistsError as exc:
            raise HelperError("Submission destination was created by another process.") from exc
    return {"ok": True, "file": str(destination), "includedFiles": len(entries), "excluded": sorted(excluded),
            "confirmedPassedPairs": report["confirmedPassedPairs"],
            "confirmedPassedScenarios": report["confirmedPassedScenarios"], "coveredScenarios": report["coveredScenarios"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("setup", help="Create local working folders; install nothing.")
    init.add_argument("--write-config", action="store_true", help="Create optional excluded harness/.local.json.")
    check = commands.add_parser("doctor", help="Check runtime, browser executable, and skills.")
    check.add_argument("--browser", action="store_true", help="Read Arena tab metadata through the engine.")
    launch = commands.add_parser("launch-browser", help="Open Arena in a dedicated browser or reuse the local CDP browser.")
    launch.add_argument("--chrome", help="Explicit browser executable path.")
    launch.add_argument("--url", default=TRAINING_URL, help="Arena URL; defaults to Training.")
    start = commands.add_parser("start", help="Prepare folders, test the adapter, and open Training. Sends no evaluation input.")
    start.add_argument("--chrome", help="Explicit browser executable path.")
    start.add_argument("--url", default=TRAINING_URL)
    adapter = commands.add_parser("arena", help="Run the Arena adapter with the installed Hermes/Node runtime.")
    adapter.add_argument("arguments", nargs=argparse.REMAINDER, help="Example: arena context --target ID")
    render = commands.add_parser("make-image", help="Make a PNG from your own UTF-8 text file using local Chrome.")
    render.add_argument("--file", required=True, type=Path)
    render.add_argument("--out", required=True, type=Path)
    render.add_argument("--width", type=int, default=1280)
    render.add_argument("--height", type=int, default=720)
    render.add_argument("--font-size", type=int, default=48)
    commands.add_parser("dry-run", help="Run the engine's offline self-test.")
    add = commands.add_parser("record", help="Append a validated event; never rewrite previous events.")
    add.add_argument("--file", required=True, type=Path)
    show = commands.add_parser("summary", help="Count latest attempts, evidenced passes, and scenario coverage.")
    show.add_argument("--out", type=Path, help="Optionally write the summary JSON.")
    export = commands.add_parser("export-submission", help="Export reviewed harness/skill source and summary only.")
    export.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None, layout: Layout | None = None) -> int:
    args = build_parser().parse_args(argv)
    layout = layout or Layout.current()
    try:
        if args.command == "setup":
            result = setup(layout, args.write_config)
        elif args.command == "doctor":
            result = doctor(layout, args.browser)
        elif args.command == "launch-browser":
            result = launch_browser(layout, args.chrome, args.url)
        elif args.command == "start":
            result = {"ok": True, "setup": setup(layout), "selfTest": engine(layout, "dry-run"),
                      "browser": launch_browser(layout, args.chrome, args.url),
                      "next": "Inspect the Arena tab. If login is shown, sign in yourself in this browser. No evaluation input has been sent."}
        elif args.command == "arena":
            argv = args.arguments or ["help"]
            result = engine(layout, argv[0], argv[1:])
        elif args.command == "make-image":
            result = make_image(layout, args.file, args.out, args.width, args.height, args.font_size)
        elif args.command == "dry-run":
            result = engine(layout, "dry-run")
        elif args.command == "record":
            result = record(layout, json.loads(args.file.read_text(encoding="utf-8-sig")))
        elif args.command == "summary":
            result = summary(layout)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                with args.out.open("x", encoding="utf-8") as output:
                    output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        else:
            result = export_submission(layout, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    except (HelperError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
