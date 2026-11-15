#!/usr/bin/env python3
"""Controlled restart of the Payday lane (supervisor + driver), windowless.

2026-11-15: switched from DETACHED_PROCESS to CREATE_NO_WINDOW + hidden
STARTUPINFO — a detached parent makes Windows create a VISIBLE console for every
console child (python supervisor -> python driver). Verification now requires a
NEW driver-start line (fresh pid, timestamp after the spawn).
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
import pathlib

W = pathlib.Path(__file__).resolve().parent.parent
A = W / "artifacts"
IS_WIN = os.name == "nt"


def winpids():
    out = subprocess.run(["ps", "-W"], capture_output=True, text=True).stdout
    pids = set()
    for row in out.splitlines()[1:]:
        cols = row.split()
        if len(cols) > 3 and cols[3].isdigit():
            pids.add(int(cols[3]))
    return pids


def read_lock():
    try:
        return int(json.loads((A / "supervisor.lock").read_text())["pid"])
    except Exception:
        return None


def last_driver_pid():
    try:
        for line in reversed((A / "supervisor.log").read_text(errors="replace").splitlines()):
            m = re.search(r"driver start pid=(\d+)", line)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


def kill(pid, why):
    if not pid or pid not in winpids():
        print(f"skip {why}: {pid} not running")
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception as exc:
        print(f"SIGTERM failed for {pid}: {exc}")
    for _ in range(10):
        if pid not in winpids():
            break
        time.sleep(1)
    if pid in winpids() and IS_WIN:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
        time.sleep(1)
    print(f"killed {why} pid={pid} alive={pid in winpids()}")


sup = read_lock()
drv = last_driver_pid()
print(f"supervisor pid={sup} driver pid={drv}")
kill(drv, "driver")
kill(sup, "supervisor")
time.sleep(2)

out = open(A / "supervisor.out", "a", encoding="utf-8")
kwargs = {}
if IS_WIN:
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
              "startupinfo": si}
t0 = time.time()
p = subprocess.Popen([sys.executable, str(W / "harness" / "supervisor.py"),
                      "--lane", "main", "--port", "9223", "--max-hours", "0"],
                     cwd=str(W), stdout=out, stderr=subprocess.STDOUT,
                     env=os.environ.copy(), **kwargs)
print(f"new supervisor pid={p.pid} (windowless)")

deadline = time.time() + 150
seen = None
while time.time() < deadline:
    try:
        lines = (A / "supervisor.log").read_text(errors="replace").splitlines()
    except OSError:
        lines = []
    for line in reversed(lines[-8:]):
        m = re.search(r"driver start pid=(\d+)", line)
        if not m or int(m.group(1)) == (drv or -1):
            continue
        tm = re.search(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]", line)
        if tm:
            try:
                ts = time.mktime(time.strptime(tm.group(1), "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                ts = 0
            if ts >= t0 - 3:
                seen = line.strip()
                break
    if seen:
        break
    time.sleep(5)
print("driver:", seen or "NOT STARTED within 150s")
try:
    print("lock:", (A / "supervisor.lock").read_text().strip())
except OSError:
    print("lock: missing")
try:
    for line in (A / "supervisor.log").read_text(errors="replace").splitlines()[-4:]:
        print("  " + line.strip())
except OSError:
    pass
