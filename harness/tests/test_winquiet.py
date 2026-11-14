"""No console window may ever appear — proven, not assumed.

The symptom this locks out (2026-11-14): a black window branded with the
interpreter path (`...\\WindowsApps\\PythonSoftwareFoundation...`) kept flashing
for the user.  Cause: the lane's supervisor was started DETACHED (no console), so
every console program it spawned got a NEW VISIBLE console; closing that window
killed the child with STATUS_CONTROL_C_EXIT (0xC000013A) and the supervisor
restarted it — forever.

These tests spawn a real child from a DETACHED parent (the exact hostile setup)
and assert the child reports no visible console.
"""

import json
import os
import pathlib
import subprocess
import sys
import textwrap
import unittest

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
sys.path.insert(0, str(WORK / "harness"))

import winquiet  # noqa: E402

PROBE = WORK / "tools" / "console_probe.py"
IS_WINDOWS = os.name == "nt"


def spawn_from_detached_parent(child_kwargs_expr: str) -> dict:
    """Run console_probe as a GRANDCHILD of a process that has no console."""
    parent = textwrap.dedent(f"""
        import json, subprocess, sys
        sys.path.insert(0, r"{WORK / 'harness'}")
        import winquiet
        opts = {child_kwargs_expr}
        p = subprocess.run([sys.executable, r"{PROBE}", "--json"],
                           capture_output=True, text=True, **opts)
        print(p.stdout.strip() or p.stderr.strip()[:300])
    """)
    parent_args = [sys.executable, "-c", parent]
    if IS_WINDOWS:
        r = subprocess.run(parent_args, capture_output=True, text=True,
                           creationflags=subprocess.DETACHED_PROCESS)
    else:
        r = subprocess.run(parent_args, capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"error": out[:300]}


@unittest.skipUnless(IS_WINDOWS, "console windows are a Windows concern")
class WindowlessTest(unittest.TestCase):
    def test_helper_asks_for_a_window_less_child(self):
        kwargs = winquiet.windowless_kwargs()
        self.assertTrue(kwargs["creationflags"] & winquiet.CREATE_NO_WINDOW)
        self.assertTrue(kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(kwargs["startupinfo"].wShowWindow, subprocess.SW_HIDE)

    def test_new_process_group_combines_with_no_window(self):
        kwargs = winquiet.windowless_kwargs(new_process_group=True)
        self.assertTrue(kwargs["creationflags"] & winquiet.CREATE_NO_WINDOW)
        self.assertTrue(kwargs["creationflags"] & winquiet.CREATE_NEW_PROCESS_GROUP)

    def test_a_bare_spawn_would_flash(self):
        """The regression this whole module exists for: without the flags the
        child gets a VISIBLE console — the flashing window the user saw."""
        data = spawn_from_detached_parent("{}")
        self.assertTrue(data.get("visible") is True,
                        f"expected a visible console for the bare spawn, got {data}")

    def test_windowless_spawn_shows_nothing(self):
        data = spawn_from_detached_parent("winquiet.windowless_kwargs()")
        self.assertIn(data.get("visible"), (False, None),
                      f"child still got a visible console: {data}")
        self.assertFalse(data.get("visible") is True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
