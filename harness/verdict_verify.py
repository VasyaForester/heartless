#!/usr/bin/env python3
"""Reconcile ALL local records against the SUBMITTED list (authoritative source).

One pass checks:
  1) every farm checkpoint (artifacts/farm-*.json, excluding *-run-* logs):
     judge pending/unknown -> passed/failed when a SUBMITTED row matches
     (model + scenario filter). Checkpoint files are written only with --apply.
  2) journal (attempts/attempts.jsonl) entries with judgeStatus pending/unknown
     that are status=completed: proposes an append-only correction event with the
     SAME attemptId (passed/failed + evidence citing the SUBMITTED row). Applied
     via `hackathon.py record` only with --apply.
  3) artifacts/pending_ledger.json waiting items: proposes resolve(found) when a
     matching row exists. Applied only with --apply.

Default is a read-only report (artifacts/verdict-verify-<ts>.json). Facts only:
unmatched rows/entries stay untouched; orphans are reported, never auto-recorded.
Never run while a farm is driving the same tab (this navigates to the modal).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
HACK = HERE / "hackathon.py"

sys.path.insert(0, str(HERE))
from scenario_filters import filter_for, filter_for_ckpt  # noqa: E402


def sh(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def today_tag():
    return time.strftime("%Y-%m-%d")


def read_submitted(target, out):
    rc, o, e = sh([sys.executable, str(HERE / "arena_chats.py"), "--target", target,
                   "--tab", "submitted", "--out", out])
    if rc != 0:
        return None, None, (o + e)[:400]
    try:
        d = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
    except Exception as exc:
        return None, None, f"parse failed: {exc}"
    return d.get("entries", []), d.get("counters", {}), None


def scan_checkpoints(slug_filter=None):
    found = []
    for p in sorted(pathlib.Path("artifacts").glob("farm-*.json")):
        if "-run-" in p.name or p.name.startswith("farm-_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict) or "models" not in d:
            continue
        slug = p.stem[len("farm-"):]
        if slug_filter and slug_filter not in slug:
            continue
        found.append((p, slug, d))
    return found


def best_row(entries, model, filt):
    if not filt:
        return None
    for e in entries:
        if ((e.get("model") or "") == model
                and e.get("status") in ("ACCEPTED", "REJECTED")
                and filt.lower() in (e.get("scenario") or "").lower()):
            return e
    return None


def journal_latest(path):
    latest = {}
    if not pathlib.Path(path).exists():
        return latest
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            latest[e.get("attemptId")] = e
    return latest


def row_id(e):
    return [e.get("status"), e.get("time"), e.get("model"), (e.get("scenario") or "")[:60]]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--journal", default="attempts/attempts.jsonl")
    ap.add_argument("--scenario", help="limit checkpoint scan to slugs containing this")
    ap.add_argument("--out")
    ap.add_argument("--apply", action="store_true",
                    help="write checkpoint updates, journal corrections, ledger resolves")
    a = ap.parse_args()

    out_path = a.out or f"artifacts/verdict-verify-{time.strftime('%Y%m%d-%H%M%S')}.json"
    tmp = f"artifacts/_vv_submitted_{int(time.time())}.json"
    entries, counters, err = read_submitted(a.target, tmp)
    if err:
        print(json.dumps({"error": "submitted read failed", "detail": err}, ensure_ascii=False))
        return 1

    report = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "apply": bool(a.apply),
              "counters": counters, "submitted_rows": len(entries),
              "ckpt_proposals": [], "journal_proposals": [], "ledger_proposals": [],
              "warnings": [], "applied": [], "orphans": [], "hint_assumptions": []}

    latest = journal_latest(a.journal)
    passed_pairs = {(e["scenarioId"], e["modelId"]) for e in latest.values()
                    if e.get("judgeStatus") == "passed"}
    referenced = set()

    # Rows already attributed to a checkpoint in an EARLIER run (verdictTime match)
    # must not be re-attributed to another round's checkpoint of the same model.
    consumed = set()
    for p in pathlib.Path("artifacts").glob("farm-*.json"):
        if "-run-" in p.name:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for cmodel, cm in (d.get("models") or {}).items():
            vt, cj = cm.get("verdictTime"), cm.get("judge")
            if vt and cj in ("passed", "failed"):
                consumed.add((cmodel, vt))

    # 1) checkpoints — collect candidates, then suppress duplicate attribution:
    # when one row matches the same model in several round checkpoints, only the
    # most recent send can own the verdict; the others are left untouched.
    candidates = []
    for path, slug, ck in scan_checkpoints(a.scenario):
        if ck.get("scenario"):
            filt, src = filter_for(ck["scenario"]), "ckpt-scenario"
        else:
            filt, src = filter_for_ckpt(slug)
        if not filt:
            report["warnings"].append(f"no scenario filter for {slug}: skipped "
                                      f"(add it to scenario_filters.py)")
            continue
        if src and src.startswith("stem-hint"):
            report["hint_assumptions"].append(f"{slug}:{src}")
        for model, m in (ck.get("models") or {}).items():
            judge, stage = m.get("judge"), m.get("stage")
            targeted = (judge in ("pending", "unknown")
                        or (stage == "sent" and judge in (None, "not-judged")))
            if not targeted:
                continue
            match = best_row(entries, model, filt)
            if not match:
                continue
            if (model, match["time"]) in consumed:
                report["warnings"].append(
                    f"{slug}: row {match['time']} for {model} already attributed to a "
                    f"checkpoint earlier; left untouched")
                continue
            candidates.append({"path": path, "slug": slug, "ck": ck, "model": model,
                               "m": m, "match": match, "ts": m.get("ts") or ""})
    grouped = {}
    for c in candidates:
        grouped.setdefault((c["model"], tuple(row_id(c["match"]))), []).append(c)
    for key, group in grouped.items():
        group.sort(key=lambda c: c["ts"], reverse=True)
        chosen, rest = group[0], group[1:]
        for c in rest:
            report["warnings"].append(
                f"{c['slug']}: row for {c['model']} attributed to {chosen['slug']} "
                f"(later send ts {chosen['ts']}); left untouched")
        prop = {"type": "ckpt", "ckpt": str(chosen["path"]), "model": chosen["model"],
                "judge": "passed" if chosen["match"]["status"] == "ACCEPTED" else "failed",
                "time": chosen["match"]["time"], "applied": False}
        if a.apply:
            m = chosen["m"]
            m["judge"] = prop["judge"]
            m["verdictTime"] = chosen["match"]["time"]
            m["stage"] = "judged"
            prop["applied"] = True
        report["ckpt_proposals"].append(prop)
        referenced.add(tuple(row_id(chosen["match"])))
    if a.apply:
        changed_paths = {p["ckpt"] for p in report["ckpt_proposals"] if p.get("applied")}
        for pth in changed_paths:
            ck2 = next((c["ck"] for c in candidates if str(c["path"]) == pth), None)
            if ck2 is not None:
                pathlib.Path(pth).write_text(json.dumps(ck2, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
                report["applied"].append(f"ckpt {pth}")

    # 2) journal corrections
    for aid, ev in sorted(latest.items()):
        if not (ev.get("status") == "completed" and ev.get("judgeStatus") in ("pending", "unknown")):
            continue
        sc, mo = ev.get("scenarioId"), ev.get("modelId")
        filt = filter_for(sc)
        if not filt:
            report["warnings"].append(f"no scenario filter for {sc} (attempt {aid}): skipped")
            continue
        if (sc, mo) in passed_pairs:
            report["warnings"].append(f"{aid}: pair already has a passed record; "
                                      f"row not auto-attributed")
            continue
        match = best_row(entries, mo, filt)
        if not match:
            continue
        referenced.add(tuple(row_id(match)))
        verdict = "passed" if match["status"] == "ACCEPTED" else "failed"
        prop = {"type": "journal", "attemptId": aid, "model": mo, "to": verdict,
                "time": match["time"], "applied": False}
        if a.apply:
            correction = dict(ev)
            correction.pop("eventId", None)
            correction.pop("recordedAt", None)
            correction["judgeStatus"] = verdict
            correction["judgeEvidence"] = (
                f"{match['status']} — SUBMITTED list '{match['status']} {match['time']} …', "
                f"model {mo} (verdict_verify {today_tag()}).")
            note = (correction.get("note") or "").strip()
            correction["note"] = (note + f" | vv-correction {today_tag()}").strip(" |")
            tmpf = f"artifacts/_vv_record_{re.sub(r'[^A-Za-z0-9._-]', '_', aid)}.json"
            pathlib.Path(tmpf).write_text(json.dumps(correction, ensure_ascii=False),
                                          encoding="utf-8")
            rc, o, e = sh([sys.executable, str(HACK), "record", "--file", tmpf])
            ok = rc == 0 and '"ok": true' in o
            prop["applied"] = bool(ok)
            prop["record_out"] = (o + e)[:200]
            if ok:
                report["applied"].append(f"journal {aid} -> {verdict}")
        report["journal_proposals"].append(prop)

    # 3) pending ledger
    led_path = pathlib.Path("artifacts/pending_ledger.json")
    if led_path.exists():
        led = json.loads(led_path.read_text(encoding="utf-8"))
        led_changed = False
        for it in led.get("items", []):
            if it.get("status") != "waiting":
                continue
            filt = filter_for(it.get("scenario"))
            if not filt:
                report["warnings"].append(f"ledger {it['id']}: no filter for {it.get('scenario')}")
                continue
            match = best_row(entries, it.get("model"), filt)
            if not match:
                continue
            referenced.add(tuple(row_id(match)))
            prop = {"type": "ledger", "id": it["id"], "to": "found",
                    "evidence": f"SUBMITTED {match['status']} {match['time']}", "applied": False}
            if a.apply:
                it["status"] = "found"
                it["evidence"] = prop["evidence"]
                it["resolvedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                led_changed = True
                prop["applied"] = True
            report["ledger_proposals"].append(prop)
        if led_changed:
            led_path.write_text(json.dumps(led, indent=2, ensure_ascii=False), encoding="utf-8")
            report["applied"].append("pending_ledger.json")

    # orphans: ACCEPTED rows not referenced and not covered by any passed pair
    def covered(e):
        for (sc, mo) in passed_pairs:
            if mo == e.get("model"):
                f2 = filter_for(sc)
                if f2 and f2.lower() in (e.get("scenario") or "").lower():
                    return True
        return False

    for e in entries:
        if e.get("status") == "ACCEPTED" and tuple(row_id(e)) not in referenced and not covered(e):
            report["orphans"].append(row_id(e))

    pathlib.Path(out_path).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    print(json.dumps({
        "counters": counters, "submitted_rows": len(entries),
        "ckpt_proposals": len(report["ckpt_proposals"]),
        "journal_proposals": len(report["journal_proposals"]),
        "ledger_proposals": len(report["ledger_proposals"]),
        "orphans": len(report["orphans"]),
        "warnings": len(report["warnings"]),
        "hint_assumed_ckpts": len(report["hint_assumptions"]),
        "applied": len(report["applied"]),
        "out": out_path}, ensure_ascii=False))
    for p in report["ckpt_proposals"]:
        print(f"  ckpt:    {p['model']} @ {p['ckpt']} -> {p['judge']} ({p['time']})")
    for p in report["journal_proposals"]:
        print(f"  journal: {p['attemptId']} -> {p['to']} ({p['time']})")
    for p in report["ledger_proposals"]:
        print(f"  ledger:  {p['id']} -> {p['to']} ({p['evidence']})")
    for w in report["warnings"]:
        print("  WARN:", w)
    print("saved:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
