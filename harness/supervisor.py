#!/usr/bin/env python3
"""LBP supervisor v2: one long-lived process, one driver, one lane.

- starts the lane Chrome only if its CDP port is down; NEVER kills a browser
- restarts the driver only when it exits (the driver's lease prevents duplicates)
- no cron, no manual confirmation, no pkill/Stop-Process
- cooperative stop: create <state_dir>/restart.requested (driver exits; supervisor restarts)
- full stop: terminate this process; the driver's lease expires after 30 min

Run: python3 harness/supervisor.py --lane main --max-hours 0   (CDP 9223, browser-data; the working entrance)
"""
from __future__ import annotations

import atexit
import argparse
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))
from boards import load_board  # noqa: E402
from store import pid_alive  # noqa: E402

CHROME_DEFAULT = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# board comes from $HERMES_BOARD (default: lucky-break-payday)
URL_DEFAULT = load_board()["url"]
BOARD_NAME = load_board()["name"]
_SUFFIX = "" if BOARD_NAME == "lucky-break-payday" else f"-{BOARD_NAME}"
LOCK = WORK / "artifacts" / f"supervisor{_SUFFIX}.lock"
LOG_PATH = WORK / "artifacts" / f"supervisor{_SUFFIX}.log"
OUT_PATH = WORK / "artifacts" / f"driver{_SUFFIX}.out"


def acquire_lock(path: pathlib.Path) -> pathlib.Path | None:
    """Single-instance protection; a stale lock with a dead pid is replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            data = __import__("json").loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        pid = int(data.get("pid") or 0)
        if pid and pid_alive(pid):
            return None
    path.write_text(__import__("json").dumps(
        {"pid": os.getpid(), "ts": time.time()}), encoding="utf-8")
    return path


def release_lock(path: pathlib.Path) -> None:
    try:
        data = __import__("json").loads(path.read_text(encoding="utf-8"))
        if int(data.get("pid") or 0) == os.getpid():
            path.unlink()
    except Exception:
        pass


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def chrome_up(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start_chrome(chrome: str, profile: pathlib.Path, port: int, url: str) -> None:
    if not pathlib.Path(chrome).exists():
        log(f"chrome not found: {chrome}")
        return
    profile.mkdir(parents=True, exist_ok=True)
    args = [chrome, f"--user-data-dir={profile}",
            "--remote-debugging-address=127.0.0.1", f"--remote-debugging-port={port}",
            "--no-first-run", "--no-default-browser-check",
            url]
    # DETACHED_PROCESS: the browser must outlive this supervisor.
    flags = 0x00000008 if os.name == "nt" else 0
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True)
    log(f"chrome started on {port} profile={profile}")
    time.sleep(10)


def pick_target(env: dict) -> str:
    try:
        p = subprocess.run([sys.executable, str(WORK / "harness" / "pick_target.py")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, env=env)
        return (p.stdout or "").strip()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="main")
    ap.add_argument("--port", type=int, default=9223)
    ap.add_argument("--chrome", default=CHROME_DEFAULT)
    ap.add_argument("--profile", default=str(WORK.parent / "browser-data"))
    ap.add_argument("--url", default=URL_DEFAULT)
    ap.add_argument("--db", default=str(WORK / "artifacts" / "harness.db"))
    ap.add_argument("--target", default="")
    ap.add_argument("--max-hours", type=float, default=0.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    lock = acquire_lock(LOCK)
    if not lock:
        log("another supervisor is running; exit")
        return 2
    atexit.register(release_lock, LOCK)

    env = os.environ.copy()
    env["HACKATHON_CDP_URL"] = f"http://127.0.0.1:{a.port}"
    if not chrome_up(a.port):
        start_chrome(a.chrome, pathlib.Path(a.profile), a.port, a.url)
    if not chrome_up(a.port):
        log(f"CDP {a.port} is down; start the lane browser and rerun")
        return 1

    target = a.target or pick_target(env)
    if not target:
        log(f"no {BOARD_NAME} tab on {a.port}; open the arena in the lane browser")
        return 1
    log(f"SUPERVISOR START board={BOARD_NAME} lane={a.lane} target={target} port={a.port} max_hours={a.max_hours}")
    try:
        import manifest as manifest_mod
        man = manifest_mod.build(lane=a.lane, cdp=f"127.0.0.1:{a.port}",
                                 browser_profile=a.profile, board_name=BOARD_NAME)
        log(f"MANIFEST {man['run_id']} board={man['board_id']} lane={man['lane_id']} cdp={man['cdp_endpoint']}")
    except Exception as exc:  # noqa: BLE001
        log(f"MANIFEST build failed: {exc}")

    out_path = OUT_PATH
    try:
        while True:
            args = [sys.executable, str(WORK / "harness" / "driver.py"),
                    "--lane", a.lane, "--target", target, "--db", a.db,
                    "--max-hours", str(a.max_hours)]
            if a.dry_run:
                args.extend(["--dry-run", "--once"])
            elif a.once:
                args.append("--once")
            with open(out_path, "a", encoding="utf-8") as out:
                p = subprocess.Popen(args, cwd=str(WORK), env=env,
                                     stdout=out, stderr=subprocess.STDOUT)
                log(f"driver start pid={p.pid} target={target}")
                rc = p.wait()
            log(f"driver exit rc={rc}")
            if a.once or a.dry_run:
                return 0
            if rc == 3:
                time.sleep(300)  # another worker holds the lease
            elif rc == 0:
                time.sleep(45)  # short pause; restart.requested is the normal cooperative path (v3)
            else:
                time.sleep(10)
            target = a.target or pick_target(env)
            if not target:
                log(f"no {BOARD_NAME} tab on {a.port} after restart; sleep 60")
                time.sleep(60)
    except KeyboardInterrupt:
        log("supervisor interrupted")
        return 0


if __name__ == "__main__":
    sys.exit(main())