#!/usr/bin/env python3
"""Golden tests for the LBP validator pipeline (harness/lbp_checks.py).

Runs every fixture in datasets/lbp/fixtures/check_fixtures.json, compares the overall
readiness to `expect_ready`, prints the full validator profile per case and a summary.
Exit code 1 on any mismatch.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import lbp_checks  # noqa: E402


def main():
    fx_path = WORK / "datasets/lbp/fixtures/check_fixtures.json"
    fixtures = json.loads(fx_path.read_text(encoding="utf-8"))
    fails = 0
    for fx in fixtures:
        r = lbp_checks.run_checks(fx["scenario"], fx["all_text"], fx["last_text"])
        ok = (r["ready"] == fx["expect_ready"])
        fails += 0 if ok else 1
        prof = " ".join(f"{v['id']}:{v['status'][0].upper()}" for v in r["validators"])
        print(f"[{'PASS' if ok else 'FAIL'}] {fx['name']:<22} "
              f"expected={fx['expect_ready']} got={r['ready']} | {prof}")
        if not ok:
            for v in r["validators"]:
                print(f"      {v['id']} {v['status']}: {v['detail']}")
    print(f"\n{len(fixtures) - fails}/{len(fixtures)} fixtures pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
