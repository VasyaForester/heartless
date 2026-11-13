#!/usr/bin/env python3
"""RETIRED 2026-11-13 (RULES 65/66). This is a hard-exit stub.

The v1 loop lives only in the archive: archive/legacy/harness/loop_v1_2026-11-13.py
Working execution: harness/supervisor.py --lane main  (v2; accounting = artifacts/harness.db).
This stub exits immediately and never reads datasets/lbp/pairs.jsonl.
"""
import sys


def main() -> int:
    print("loop.py retired (v1). Use: python3 harness/supervisor.py --lane main; "
          "live accounting = artifacts/harness.db; archive = archive/legacy/harness/loop_v1_2026-11-13.py",
          file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())