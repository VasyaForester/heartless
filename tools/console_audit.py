#!/usr/bin/env python3
"""List VISIBLE console windows that belong to our own process chain.

Read-only (EnumWindows + title match).  Console windows are titled with the
executable path, so a leaked window shows up as `...\\python.exe` — and if the
interpreter is the Store one, with `WindowsApps` in the name, which is exactly
what the user kept seeing flash.

Usage:
    python3 tools/console_audit.py            # human table, exit 1 if any leak
    python3 tools/console_audit.py --json     # machine output
"""

import ctypes
import json
import os
import sys

MARKERS = ("python", "WindowsApps", "harness", "supervisor", "driver.py", "lbp.py",
           "console_probe", "nightly")


def visible_windows() -> list:
    if os.name != "nt":
        return []
    user32 = ctypes.windll.user32
    found = []
    ENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value
        if not title:
            return True
        low = title.lower()
        if any(m.lower() in low for m in MARKERS):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append({"handle": int(hwnd), "title": title, "pid": int(pid.value)})
        return True

    user32.EnumWindows(ENUMPROC(cb), None)
    return found


def main() -> int:
    rows = visible_windows()
    if "--json" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 1 if rows else 0
    if not rows:
        print("no visible console windows from our chain — clean")
        return 0
    print("VISIBLE console windows from our chain (these are what flashes):")
    for r in rows:
        print(f"  hwnd={r['handle']:<10} pid={r['pid']:<8} title={r['title']!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
