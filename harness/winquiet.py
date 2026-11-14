#!/usr/bin/env python3
"""Spawn Windows children WITHOUT a console window (and never DETACH the parent).

The problem this solves (measured 2026-11-14): the lane's supervisor is started
DETACHED (no console at all), so EVERY console program it spawns — the driver at
each restart, `pick_target.py`, the per-probe `lbp.py` — gets a NEW console window
that Windows SHOWS.  The window's title is the interpreter path, which is why the
user kept seeing a black window branded `...\\WindowsApps\\PythonSoftwareFoundation...`;
closing that window kills the child with STATUS_CONTROL_C_EXIT (0xC000013A), the
supervisor restarts it, and a fresh window appears — forever.

Rules of thumb:
  * NEVER DETACH a parent that will spawn console children: DETACHED_PROCESS means
    "no console", and children then create (and show) their own.  Use
    CREATE_NO_WINDOW instead — the child gets a console that is not displayed, and
    its own children inherit it silently.
  * Every spawn site must pass `windowless_kwargs()`.  A hidden child is not
    enough if its own children are spawned bare.
  * GUI programs (chrome) may stay DETACHED — they never create consoles.

Verification: `python3 tools/console_probe.py` reports whether THIS process has a
visible console; `harness/tests/test_winquiet.py` spawns it from a detached parent
and asserts the window is gone.
"""

import os
import subprocess

IS_WINDOWS = os.name == "nt"
# 0x08000000 = CREATE_NO_WINDOW (present as subprocess.CREATE_NO_WINDOW on Windows)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)


def windowless_kwargs(*, new_process_group: bool = False) -> dict:
    """Keyword args for Popen/run that guarantee no console window is shown.

    Returns {} on POSIX.  On Windows: CREATE_NO_WINDOW plus a hidden STARTUPINFO,
    because some shells honour only one of the two.
    """
    if not IS_WINDOWS:
        return {}
    flags = CREATE_NO_WINDOW
    if new_process_group:
        flags |= CREATE_NEW_PROCESS_GROUP
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": flags, "startupinfo": startupinfo}


def windowless_popen(args, *, new_process_group: bool = False, **kwargs):
    """Popen with the window suppression already applied (kwargs win on conflict)."""
    opts = windowless_kwargs(new_process_group=new_process_group)
    opts.update(kwargs)
    return subprocess.Popen(args, **opts)


def windowless_run(args, *, new_process_group: bool = False, **kwargs):
    """subprocess.run with the window suppression already applied."""
    opts = windowless_kwargs(new_process_group=new_process_group)
    opts.update(kwargs)
    return subprocess.run(args, **opts)
