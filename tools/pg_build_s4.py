#!/usr/bin/env python3
"""Build single-line SIEM username payloads for scenario owlsec-security-alert.

Modes:
  tag   : visible text + Unicode TAG-encoded hidden text (U+E0000+ASCII)
  u2028 : visible text + U+2028 + hidden text (raw line-separator smuggling probe)

Guarantees: no newline/CR anywhere; no trailing whitespace (fill field must not see \n).
"""
import argparse


def tag_encode(s: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) if 0x20 <= ord(c) <= 0x7E else c for c in s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["tag", "u2028"], required=True)
    ap.add_argument("--visible", required=True)
    ap.add_argument("--hidden", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    vis = open(a.visible, encoding="utf-8").read().rstrip("\n")
    hid = open(a.hidden, encoding="utf-8").read().strip("\n")
    sep = "\u2028" if a.mode == "u2028" else ""
    enc = hid if a.mode == "u2028" else tag_encode(hid)
    payload = vis + sep + enc

    assert "\n" not in payload and "\r" not in payload, "payload must be single-line"
    assert not payload.endswith(("\n", "\r", " ")), "payload must not end with whitespace"
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        fh.write(payload)
    print(f"wrote {a.out}: visible={len(vis)} hidden={len(hid)} total={len(payload)} mode={a.mode}")


if __name__ == "__main__":
    main()
