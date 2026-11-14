#!/usr/bin/env python3
"""Start a long-running command with NO console window, from a shell script.

Why: a shell script started by a scheduler/keeper may itself have no console, in
which case every console program it starts (python, node) gets a NEW visible
window.  This launcher applies CREATE_NO_WINDOW (+ hidden STARTUPINFO) and returns
immediately, so the caller's shell can exit without taking the child down.

Usage:
    python3 tools/spawn_hidden.py --out <logfile> [--cwd DIR] -- <cmd> [args...]

Prints the child pid; exits 0 on success, 2 when the child could not start.
"""

import argparse
import os
import pathlib
import subprocess
import sys

W = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(W / "harness"))
from winquiet import windowless_kwargs  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--out", default="", help="append the child's stdout/stderr here")
    ap.add_argument("--cwd", default=str(W))
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- <cmd> [args...] (the leading -- is dropped)")
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        print("usage: spawn_hidden.py --out LOG -- cmd [args...]", file=sys.stderr)
        return 2
    out = open(a.out, "a", encoding="utf-8") if a.out else subprocess.DEVNULL
    try:
        p = subprocess.Popen(cmd, cwd=a.cwd, stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, env=os.environ.copy(),
                             **windowless_kwargs(new_process_group=True))
    except OSError as exc:
        print(f"spawn failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(p.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
