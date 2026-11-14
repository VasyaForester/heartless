#!/usr/bin/env python3
"""Controlled restart of the Payday lane (supervisor + driver), 2026-11-13.

Why: on 2026-11-13 a wedge left the lane dark for 2.5 h. The supervisor now has
a stale-log watchdog; this script replaces a supervisor that predates it.

Order: terminate driver -> terminate supervisor -> spawn fresh supervisor
(detached, logs to artifacts/supervisor.out) -> wait for a new driver start.
Safe with the sibling lane: only PID 1 (lock) and the last "driver start" PID
from THIS board's supervisor.log are touched.
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
sys.path.insert(0, str(W / "harness"))
from winquiet import windowless_kwargs  # noqa: E402


def winpids() -> set:
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
    except Exception as exc:  # noqa: BLE001
        print(f"SIGTERM failed for {pid}: {exc}")
    for _ in range(10):
        if pid not in winpids():
            break
        time.sleep(1)
    if pid in winpids():
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        time.sleep(1)
    print(f"killed {why} pid={pid} alive={pid in winpids()}")


sup = read_lock()
drv = last_driver_pid()
print(f"supervisor pid={sup} driver pid={drv}")
kill(drv, "driver")
kill(sup, "supervisor")
time.sleep(2)

out = open(A / "supervisor.out", "a", encoding="utf-8")
# 2026-11-14: was DETACHED_PROCESS — that is exactly what made every python the
# supervisor later spawned (the driver, pick_target, lbp.py) open a NEW VISIBLE
# console window branded with the WindowsApps interpreter path; closing that
# window even killed the driver (STATUS_CONTROL_C_EXIT 0xC000013A).  CREATE_NO_WINDOW
# keeps the supervisor equally outliving while leaving its children windowless.
p = subprocess.Popen(
    [sys.executable, str(W / "harness" / "supervisor.py"),
     "--lane", "main", "--port", "9223", "--max-hours", "0"],
    cwd=str(W), stdout=out, stderr=subprocess.STDOUT,
    env=os.environ.copy(), **windowless_kwargs(new_process_group=True))
print(f"new supervisor pid={p.pid}")

deadline = time.time() + 120
seen = None
while time.time() < deadline:
    try:
        log = (A / "supervisor.log").read_text(errors="replace").splitlines()
    except OSError:
        log = []
    for line in reversed(log[-8:]):
        m = re.search(r"driver start pid=(\d+)", line)
        if m and int(m.group(1)) != drv:
            seen = line.strip()
            break
    if seen:
        break
    time.sleep(5)
print("driver:", seen or "NOT STARTED within 120s")
print("lock:", (A / "supervisor.lock").read_text().strip())
print("supervisor.log tail:")
for line in (A / "supervisor.log").read_text(errors="replace").splitlines()[-5:]:
    print("  " + line.strip())