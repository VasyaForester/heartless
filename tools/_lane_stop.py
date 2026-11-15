#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop the lane (driver, then supervisor) without a window — for a manual operation.

Останавливает полосу на время ручной операции: сначала водителя (чтобы сторож не поднял
его заново), затем сторожа. Окна не создаются. Перезапуск — `python3 tools/lane_restart.py`.
"""
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import time

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


def main():
    sup, drv = read_lock(), last_driver_pid()
    print(f"supervisor pid={sup} driver pid={drv}")
    kill(drv, "driver")
    kill(sup, "supervisor")
    time.sleep(2)
    print("lane stopped:", "yes" if (sup not in winpids() and drv not in winpids()) else "CHECK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
