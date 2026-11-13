#!/usr/bin/env python3
"""Repair indentation of the guard patches in driver.py / supervisor.py (2026-11-13)."""
import pathlib

W = pathlib.Path(__file__).resolve().parent.parent
H = W / "harness"

# ---------- driver.py ----------
dp = H / "driver.py"
lines = dp.read_text(encoding="utf-8").splitlines()
oi = next(i for i, l in enumerate(lines) if "engine = strategy.StrategyEngine(" in l)
# the bad block starts on the next non-empty line and is 6 lines long
assert lines[oi + 1].strip() == "try:", lines[oi + 1]
for k in range(oi + 1, oi + 7):
    assert lines[k].startswith(" " * 8), (k, lines[k])
    lines[k] = lines[k][4:]
dp.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("driver.py: dedented try-block")

# ---------- supervisor.py ----------
sp = H / "supervisor.py"
lines = sp.read_text(encoding="utf-8").splitlines()

# 1) argparse lines dedent (8 -> 4)
for i, l in enumerate(lines):
    if l.strip().startswith('ap.add_argument("--dry-run"') and l.startswith(" " * 8):
        lines[i] = l[4:]
    if l.strip().startswith('ap.add_argument("--stale-min"'):
        lines[i] = "    " + l.strip()
        lines[i + 1] = "                    " + lines[i + 1].strip()

# 2) watchdog block rebuild
start = next(i for i, l in enumerate(lines) if "Watchdog: p.wait() alone" in l)
end = next(i for i, l in enumerate(lines)
           if l.strip() == 'log(f"driver exit rc={rc}")' and i > start)
block = '''                # Watchdog: p.wait() alone cannot distinguish "attempt in flight"
                # from "driver wedged" — on 2026-11-13 a wedged driver kept the
                # lane dark for 2.5 h. Treat a non-growing log as stale.
                stale_s = max(int(a.stale_min), 5) * 60
                last_mark = time.time()
                last_sz = -1
                rc = None
                while True:
                    rc = p.poll()
                    if rc is not None:
                        break
                    try:
                        sz = out_path.stat().st_size
                    except OSError:
                        sz = last_sz
                    now = time.time()
                    if sz != last_sz:
                        last_sz, last_mark = sz, now
                    elif now - last_mark > stale_s:
                        log(f"driver STALE {int(now - last_mark)}s (log not growing); terminate")
                        try:
                            p.terminate()
                            time.sleep(10)
                            if p.poll() is None:
                                p.kill()
                        except Exception as exc:  # noqa: BLE001
                            log(f"terminate failed: {exc}")
                        rc = 124
                        break
                    time.sleep(5)
            log(f"driver exit rc={rc}")'''.splitlines()
lines[start:end + 1] = block
sp.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("supervisor.py: argparse + watchdog rebuilt")