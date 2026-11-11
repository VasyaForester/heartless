#!/usr/bin/env python3
"""Verify a .tar.gz export: magic bytes, tar entries, multi-member gzip fallback."""
import gzip
import os
import sys
import tarfile


def main():
    p = sys.argv[1]
    print("size:", os.path.getsize(p))
    with open(p, "rb") as f:
        print("magic:", f.read(4).hex())
    try:
        with tarfile.open(p, "r:gz") as t:
            names = t.getnames()
        print("tar entries:", len(names))
        for n in names[:20]:
            print(" -", n)
        return
    except Exception as e:
        print("tarfile r:gz failed:", e)
    try:
        data = gzip.open(p, "rb").read()
        print("gzip decompressed bytes:", len(data), "head:", data[:16])
    except Exception as e2:
        print("gzip failed:", e2)
    try:
        import zipfile
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
        print("zip entries:", len(names))
        for n in names[:25]:
            print(" -", n)
    except Exception as e3:
        print("zip failed:", e3)


if __name__ == "__main__":
    main()
