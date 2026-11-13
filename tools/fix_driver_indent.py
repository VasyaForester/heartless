#!/usr/bin/env python3
"""One-off: repair the over-indented lease/manifest block in harness/driver.py (2026-11-13)."""
import pathlib
import sys

p = pathlib.Path(__file__).resolve().parent.parent / "harness" / "driver.py"
lines = p.read_text(encoding="utf-8").splitlines()
try:
    start = next(i for i, l in enumerate(lines)
                 if l.strip() == "lease = store.acquire_lease(conn, a.lane, target)")
    end = next(i for i in range(start, len(lines)) if 'profile={PROFILE_HASH}")' in lines[i])
except StopIteration:
    print("block not found")
    sys.exit(1)
new = []
for j, l in enumerate(lines[start:end + 1]):
    stripped = l.lstrip(" ")
    indent = len(l) - len(stripped)
    new_indent = 4 if j == 0 else max(indent - 4, 0)
    new.append(" " * new_indent + stripped)
lines[start:end + 1] = new
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"rewrote lines {start + 1}-{end + 1}")
for l in lines[start:end + 1]:
    print("|" + l[:110])