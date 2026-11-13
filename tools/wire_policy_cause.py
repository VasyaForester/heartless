#!/usr/bin/env python3
"""One-off: wire policy_classify into driver (import + CAUSE log line). 2026-11-13."""
import pathlib
import sys

p = pathlib.Path(__file__).resolve().parent.parent / "harness" / "driver.py"
lines = p.read_text(encoding="utf-8").splitlines()

# import
imp = "import policy_classify  # noqa: E402"
if not any(l.strip() == imp for l in lines):
    idx = next((i for i, l in enumerate(lines) if l.strip() == "import manifest  # noqa: E402"), None)
    if idx is None:
        print("import anchor not found")
        sys.exit(1)
    lines.insert(idx + 1, imp)
    print(f"import inserted at {idx + 2}")

# CAUSE log after attempts.mark_judge(...)
anchor = "attempts.mark_judge(conn, lease, attempt_id, result)"
idxs = [i for i, l in enumerate(lines) if l.strip() == anchor]
if not idxs:
    print("mark_judge anchor not found")
    sys.exit(1)
i = idxs[-1]
block = [
    "                    try:",
    "                        log(f\"CAUSE {attempt_id}: {policy_classify.summarize(text)}\")",
    "                    except Exception:",
    "                        pass",
]
# avoid double insert
if not any("policy_classify.summarize" in l for l in lines):
    lines[i + 1:i + 1] = block
    print(f"CAUSE log inserted after line {i + 1}")
else:
    print("CAUSE log already present")

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("done")