#!/usr/bin/env python3
"""Invisible Unicode payload tool: encode hidden text as Unicode TAG characters (U+E0000+ASCII),
decode them back, and build visible+hidden message files.

Usage:
  python3 unicode_hide.py build --visible visible.txt --hidden hidden.txt --out message.txt
  python3 unicode_hide.py decode --file message.txt
  python3 unicode_hide.py count --file message.txt
"""
from __future__ import annotations
import argparse


ZERO, ONE = "\u200b", "\u200c"  # ZWSP / ZWNJ


def tag_encode(s: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) if 0x20 <= ord(c) <= 0x7E else c for c in s)


def tag_decode(s: str) -> str:
    return "".join(chr(ord(c) - 0xE0000) if 0xE0000 <= ord(c) <= 0xE007F else "" for c in s)


def zw_encode(s: str) -> str:
    """Encode text as zero-width binary (ZWSP=0, ZWNJ=1), 8 bits per UTF-8 byte."""
    out = []
    for byte in s.encode("utf-8"):
        for i in range(7, -1, -1):
            out.append(ONE if (byte >> i) & 1 else ZERO)
    return "".join(out)


def zw_decode(s: str) -> str:
    bits = [c for c in s if c in (ZERO, ONE)]
    if len(bits) < 8:
        return ""
    bits = bits[: len(bits) // 8 * 8]
    data = bytes(int("".join("1" if b == ONE else "0" for b in bits[i:i + 8]), 2)
                 for i in range(0, len(bits), 8))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--visible", required=True)
    b.add_argument("--hidden", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--separator", default="\n\n")
    b.add_argument("--mode", default="tag", choices=["tag", "zw"])
    d = sub.add_parser("decode")
    d.add_argument("--file", required=True)
    c = sub.add_parser("count")
    c.add_argument("--file", required=True)
    a = ap.parse_args()

    if a.cmd == "build":
        visible = open(a.visible, encoding="utf-8").read().rstrip("\n")
        hidden = open(a.hidden, encoding="utf-8").read().strip("\n")
        enc = zw_encode(hidden) if a.mode == "zw" else tag_encode(hidden)
        payload = visible + a.separator + enc + "\n"
        open(a.out, "w", encoding="utf-8").write(payload)
        print(f"built {a.out}: visible={len(visible)} ch, hidden={len(hidden)} ch "
              f"-> {len(tag_encode(hidden))} tag chars")
    elif a.cmd == "decode":
        text = open(a.file, encoding="utf-8").read()
        print("tag:", repr(tag_decode(text)))
        print("zw:", repr(zw_decode(text)))
    elif a.cmd == "count":
        text = open(a.file, encoding="utf-8").read()
        n = sum(1 for ch in text if 0xE0000 <= ord(ch) <= 0xE007F)
        print(f"tag chars: {n}, total chars: {len(text)}")


if __name__ == "__main__":
    main()
