#!/usr/bin/env python3
"""Is THIS lane making progress? — the shared-log trap.

`artifacts/driver.log` is written by EVERY lane: lines carry the lane marker in
the attempt id (`...:main:...`, `...:pg:...`) and in `lane=` fields.  A watchdog
that watches the file's size or mtime therefore sees the OTHER lane's chatter as
progress and can leave a wedged driver running (measured 2026-11-14: the whole
file is shared, and a supervisor whose driver wedged kept seeing bytes appear).

`lane_progress()` counts THIS lane's marker lines in the tail of the log, so the
signal belongs to the lane that is being watched.
"""

import pathlib

TAIL_BYTES = 512 * 1024


def lane_progress(log_path, lane: str, *, tail_bytes: int = TAIL_BYTES) -> int:
    """Number of marker lines for `lane` in the tail of the log (monotone-ish).

    Cheap: reads at most `tail_bytes` from the end.  Returns -1 when the file is
    unreadable, so callers can decide (a missing log is not progress).
    """
    p = pathlib.Path(log_path)
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
            data = f.read()
    except OSError:
        return -1
    marker = f":{lane}:".encode("utf-8", "replace")
    field = f"lane={lane}".encode("utf-8", "replace")
    return data.count(marker) + data.count(field)
