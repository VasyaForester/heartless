#!/usr/bin/env python3
"""One-off: normalize the evidence block in harness/driver.py and add evidence.finish (2026-11-13)."""
import pathlib
import sys

p = pathlib.Path(__file__).resolve().parent.parent / "harness" / "driver.py"
lines = p.read_text(encoding="utf-8").splitlines()

# --- 1) replace mark_submitted..correlate block with the canonical 16-space version ---
try:
    start = next(i for i, l in enumerate(lines)
                 if "attempts.mark_submitted(conn, lease, attempt_id, chat_id=chat," in l)
    end = next(i for i in range(start, len(lines))
               if "known_operations=store.known_judge_operations(conn))" in lines[i])
except StopIteration:
    print("evidence block not found")
    sys.exit(1)
block = [
    "                attempts.mark_submitted(conn, lease, attempt_id, chat_id=chat,",
    "                                        transcript_text=text)",
    "                ev = evidence.capture(attempt_id, key=key, input_path=input_path,",
    "                                      delta=delta, lane=a.lane,",
    "                                      transcript_path=transcript_path(key),",
    "                                      judge_path=judge_path(key))",
    "                attempt_row = store.get_attempt(conn, attempt_id)",
    "                result = judge_correlation.correlate(",
    "                    attempt_row, ev.get(\"judge_copy\") or judge_path(key), transcript_text=text,",
    "                    known_operations=store.known_judge_operations(conn))",
]
lines[start:end + 1] = block
print(f"evidence block rewritten: lines {start + 1}-{end + 1}")

# --- 2) insert evidence.finish right after the JUDGE-not-verified log line ---
idx = None
for i, l in enumerate(lines):
    if 'log(f"JUDGE {result[\'status\']} {attempt_id}: {result[\'reason\']}")' in l:
        idx = i
if idx is None:
    print("JUDGE log line not found")
    sys.exit(1)
finish = [
    "                evidence.finish(attempt_id, judge_result=result,",
    "                                evaluation={\"score\": result.get(\"score\"),",
    "                                            \"pcts\": result.get(\"pcts\"),",
    "                                            \"verdict\": result.get(\"verdict\"),",
    "                                            \"status\": result.get(\"status\")})",
]
lines[idx + 1:idx + 1] = finish
print(f"evidence.finish inserted after line {idx + 1}")

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("done")