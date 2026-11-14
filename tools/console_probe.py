#!/usr/bin/env python3
"""Report whether THIS process got a visible console window (Windows only).

Used to prove/verify console-flash fixes: a process started from a parent that
has no console (a DETACHED process, a GUI app, a cron runner) gets a NEW console
that Windows SHOWS — the black window flashing with the interpreter path in its
title, e.g. ...\\WindowsApps\\PythonSoftwareFoundation...\\python.exe.

Usage:
    python3 tools/console_probe.py           # human line
    python3 tools/console_probe.py --json    # machine line
"""

import ctypes
import json
import os
import sys


def probe() -> dict:
    out = {"pid": os.getpid(), "executable": sys.executable, "console": None,
           "visible": None, "title": None, "console_window": None}
    if os.name != "nt":
        out["console"] = "n/a (posix)"
        return out
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    hwnd = kernel32.GetConsoleWindow()
    out["console"] = bool(hwnd)
    out["console_window"] = int(hwnd) if hwnd else 0
    if hwnd:
        out["visible"] = bool(user32.IsWindowVisible(hwnd))
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        out["title"] = buf.value
    return out


def main() -> int:
    data = probe()
    if "--json" in sys.argv:
        print(json.dumps(data, ensure_ascii=False))
    else:
        if data["console"] is None:
            print(f"posix: no windows here")
        elif not data["console"]:
            print(f"NO console at all (pid={data['pid']}) — a child console app "
                  f"would get a NEW VISIBLE window")
        else:
            state = "VISIBLE" if data["visible"] else "hidden"
            print(f"console={state} title={data['title']!r} exe={data['executable']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
