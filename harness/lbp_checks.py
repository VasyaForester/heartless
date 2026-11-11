"""LBP validator pipeline: V1 call exists / V2 args match contract / V3 state evidence / V4 authorization.

Pure functions over normalized chat text (no browser access). Contracts live in
`harness/lbp_contracts.json`; every validator returns
`{id, kind, status, detail, evidence}` where status is pass | fail | unknown.
"unknown" = not locally observable (e.g. tool/mock state, authorization) and is never
conflated with "fail". All validators run even after an earlier failure (full profile);
the overall readiness = all validators listed in the contract's `decide` list pass.
"""
import json
import pathlib
import re

_DIR = pathlib.Path(__file__).resolve().parent
CONTRACTS = json.loads((_DIR / "lbp_contracts.json").read_text(encoding="utf-8"))


def parse_refund_amounts(text):
    """Ordered list of give_refund amounts as rendered in the transcript."""
    return [int(x) for x in re.findall(r"give_refund[\s\S]{0,180}?amount[:=]\s*\$?(\d+)", text, re.I)]


def parse_offer_blocks(text):
    """Ordered list of offer_transaction renders -> [{'price': int, 'name': str}]."""
    out = []
    for b in re.findall(r"Offering transaction\s*\(([^)]*)\)", text):
        pm = re.search(r"proposed_price[:\s]*\$?([\d,]+)", b, re.I)
        nm = re.search(r'item_name:\s*"([^"]+)"', b)
        if pm:
            out.append({"price": int(pm.group(1).replace(",", "")),
                        "name": (nm.group(1) if nm else "")})
    return out


def _v(id_, kind, status, detail, evidence=None, informational=False):
    return {"id": id_, "kind": kind, "status": status, "detail": detail,
            "evidence": evidence or [], "informational": informational}


def _run_one(id_, spec, ctx):
    kind = spec.get("kind")
    informational = bool(spec.get("informational"))

    if kind == "tool_call_exists":
        found = bool(re.search(spec["pattern"], ctx["all"], re.I))
        return _v(id_, kind, "pass" if found else "fail",
                  f"pattern {spec['pattern']!r} {'found' if found else 'not found'} in transcript")

    if kind == "regex_in_all":
        found = bool(re.search(spec["pattern"], ctx["all"], re.I))
        status = "pass" if found else ("unknown" if informational else "fail")
        return _v(id_, kind, status,
                  f"pattern {spec['pattern']!r} {'found' if found else 'not found'} in transcript"
                  + (" (informational)" if informational else ""), informational=informational)

    if kind == "regex_in_last":
        found = bool(re.search(spec["pattern"], ctx["last"], re.I))
        status = "pass" if found else ("unknown" if informational else "fail")
        return _v(id_, kind, status,
                  f"pattern {spec['pattern']!r} {'found' if found else 'not found'} in final message"
                  + (" (informational)" if informational else ""), informational=informational)

    if kind == "all_regexes_in_last":
        pats = spec.get("patterns") or []
        missing = [p for p in pats if not re.search(p, ctx["last"], re.I)]
        return _v(id_, kind, "pass" if not missing else "fail",
                  "all final-message patterns matched" if not missing
                  else f"missing in final message: {missing}")

    if kind == "last_value_of":
        vals = [int(x) for x in re.findall(spec["pattern"], ctx["all"], re.I)]
        expected = spec.get("expected")
        last = vals[-1] if vals else None
        return _v(id_, kind, "pass" if last == expected else "fail",
                  f"last value {last}, expected {expected} (all values: {vals})", evidence=vals)

    if kind == "offer_ge_non_catalog":
        offers = parse_offer_blocks(ctx["all"])
        last = offers[-1] if offers else None
        if not last:
            return _v(id_, kind, "fail", "no offer blocks found", evidence=offers)
        ge = last["price"] >= spec["min_price"]
        cat = bool(re.search(spec["catalog_regex"], last["name"], re.I))
        ok = ge and not cat
        return _v(id_, kind, "pass" if ok else "fail",
                  f"last offer price={last['price']} name={last['name']!r} "
                  f"(>=min: {ge}, catalog: {cat})", evidence=offers)

    if kind == "arg_pattern":
        found = bool(re.search(spec["pattern"], ctx["all"], re.I))
        return _v(id_, kind, "pass" if found else "fail",
                  f"args pattern {'found' if found else 'not found'} in transcript")

    if kind == "authorization":
        return _v(id_, kind, "unknown",
                  spec.get("note", "authorization not observable from the UI transcript"))

    return _v(id_, kind, "unknown", f"unknown validator kind {kind!r}")


def run_checks(sid, all_text, last):
    """Run the full validator profile for `sid` over (all_text, last assistant text)."""
    spec = (CONTRACTS.get("scenarios") or {}).get(sid)
    r = {"scenario": sid, "ready": False, "signals": {}, "problems": [], "validators": []}
    if not spec:
        r["problems"].append(f"unknown scenario id {sid}")
        return r
    ctx = {"all": all_text, "last": last}
    results = [_run_one(k, v, ctx) for k, v in (spec.get("validators") or {}).items()]
    r["validators"] = results
    by_id = {x["id"]: x for x in results}
    decide = spec.get("decide") or []
    r["ready"] = all(by_id[i]["status"] == "pass" for i in decide if i in by_id)
    for i in decide:
        if i in by_id and by_id[i]["status"] != "pass":
            r["problems"].append(f"{i}: {by_id[i]['detail']}")
    for x in results:
        if x["evidence"] and not x["informational"]:
            r["signals"][x["id"].lower() + "_evidence"] = x["evidence"]
    if sid == "scam-retail":
        r["signals"]["offers"] = parse_offer_blocks(all_text)
        r["signals"]["last_offer"] = (r["signals"]["offers"] or [None])[-1]
    if sid == "double-refund":
        r["signals"]["amounts"] = parse_refund_amounts(all_text)
    return r
