#!/usr/bin/env python3
"""Refusal-cause mining (2026-11-13): classify captured transcripts at scale.

Scans the evidence store (artifacts/attempts/*/transcript.json) and legacy
submit transcripts, extracts the assistant text, runs policy_classify and
aggregates the probable refusal causes per pair.

Writes artifacts/refusal-causes.json and prints a compact table.
Usage: python3 harness/refusal_mining.py [--limit N]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))

import policy_classify  # noqa: E402


def collect_strings(obj, out, depth=0):
    if depth > 12:
        return
    if isinstance(obj, str):
        if len(obj) > 40:
            out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_strings(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            collect_strings(v, out, depth + 1)


def text_of(path: pathlib.Path) -> str:
    """Assistant-only text from a transcript; falls back to all long strings."""
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    msgs = d.get("messages") if isinstance(d, dict) else None
    if isinstance(msgs, list):
        parts = [m.get("text") or "" for m in msgs
                 if isinstance(m, dict) and str(m.get("role")) == "assistant"]
        joined = "\n".join(p for p in parts if p)
        if joined.strip():
            return joined
    chunks = []
    collect_strings(d, chunks)
    return "\n".join(chunks)


RENDER_SIG = re.compile(
    r"(?:^|\n)\s*(?:create_listing|get_user_info|purchase|give_refund|offer_transaction)\b", re.M)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    rows = []
    for man in (WORK / "artifacts" / "attempts").glob("*/manifest.json"):
        d = pathlib.Path(man).parent
        try:
            meta = json.loads(man.read_text(encoding="utf-8"))
        except Exception:
            continue
        tp = d / "transcript.json"
        if not tp.exists():
            continue
        rows.append({"attempt": meta.get("attempt_id"), "pair": f"{meta.get('scenario')}|{meta.get('model')}",
                     "src": str(tp.relative_to(WORK)), "text": text_of(tp)})
    for tp in (WORK / "artifacts").glob("lbp-*-submit-transcript.json"):
        rows.append({"attempt": tp.stem, "pair": tp.stem.replace("lbp-", "").replace("-submit-transcript", ""),
                     "src": str(tp.relative_to(WORK)), "text": text_of(tp)})
    if a.limit:
        rows = rows[:a.limit]

    stats = collections.defaultdict(lambda: {"n": 0, "refusal_n": 0, "render_n": 0,
                                             "causes": collections.Counter(),
                                             "weak": collections.Counter()})
    for r in rows:
        s = stats[r["pair"]]
        s["n"] += 1
        got = policy_classify.classify(r["text"])
        refused = bool(policy_classify.REFUSAL_MARKERS.search(r["text"]))
        rendered = bool(RENDER_SIG.search(r["text"]))
        if refused:
            s["refusal_n"] += 1
        if rendered:
            s["render_n"] += 1
        for o in got:
            (s["weak"] if o.get("weak") else s["causes"])[o["cause"]] += 1

    out = {"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
           "transcripts": len(rows), "pairs": {}}
    for pair, s in sorted(stats.items()):
        out["pairs"][pair] = {
            "transcripts": s["n"], "with_refusal_marker": s["refusal_n"],
            "rendered_tool_call": s["render_n"],
            "causes": dict(s["causes"]), "weak_mentions": dict(s["weak"]),
        }
    (WORK / "artifacts" / "refusal-causes.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"transcripts={len(rows)} pairs={len(out['pairs'])} -> artifacts/refusal-causes.json")
    for pair, s in sorted(out["pairs"].items()):
        top = sorted(s["causes"].items(), key=lambda kv: -kv[1])[:3]
        print(f"  {pair[:58]:58s} n={s['transcripts']:3d} refuse={s['with_refusal_marker']:3d} "
              f"render={s['rendered_tool_call']:3d} causes={top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())