#!/usr/bin/env python3
"""Fetch the web/abs pages the GitHub/HF intake cannot handle (no PDFs).

Saves raw/sources/web/<key>.html and <key>.md (title + clean text), and appends
a manifest record to raw/sources/artifacts/manifest.jsonl.

Usage: python3 tools/fetch_web_20261112.py [--only arxiv|web]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

WORK = pathlib.Path(__file__).resolve().parent.parent
OUT = WORK / "prompt_injection_ctf" / "raw" / "sources" / "web"
MAN = WORK / "prompt_injection_ctf" / "raw" / "sources" / "artifacts" / "manifest.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

WEB = [
    ("arxiv-2506.15740", "https://arxiv.org/abs/2506.15740", "arxiv"),
    ("arxiv-2507.20526", "https://arxiv.org/abs/2507.20526", "arxiv"),
    ("arxiv-2512.15163", "https://arxiv.org/abs/2512.15163", "arxiv"),
    ("arxiv-2410.11096", "https://arxiv.org/abs/2410.11096", "arxiv"),
    ("arxiv-2506.02548", "https://arxiv.org/abs/2506.02548", "arxiv"),
    ("arxiv-2303.06729", "https://arxiv.org/abs/2303.06729", "arxiv"),
    ("arxiv-2412.20787", "https://arxiv.org/abs/2412.20787", "arxiv"),
    ("arxiv-2601.03699", "https://arxiv.org/abs/2601.03699", "arxiv"),
    ("arxiv-2602.20708", "https://arxiv.org/abs/2602.20708", "arxiv"),
    ("arxiv-2605.17986", "https://arxiv.org/abs/2605.17986", "arxiv"),
    ("usenix-ling", "https://www.usenix.org/conference/usenixsecurity26/presentation/ling", "web"),
    ("lakera-backbone", "https://lakera.ai/blog/the-backbone-breaker-benchmark", "web"),
    ("baxbench", "https://baxbench.com", "web"),
    ("openreview-PFbt5pWWh7", "https://openreview.net/forum?id=PFbt5pWWh7", "web"),
    # addendum 2026-11-12 — defensive mechanisms / tool-agent safety evaluation
    ("arxiv-2605.28914", "https://arxiv.org/abs/2605.28914", "arxiv"),
    ("arxiv-2608.19861", "https://arxiv.org/abs/2608.19861", "arxiv"),
    ("arxiv-2606.29225", "https://arxiv.org/abs/2606.29225", "arxiv"),
    ("arxiv-2606.13715", "https://arxiv.org/abs/2606.13715", "arxiv"),
    ("agentabstain", "https://agentabstain.github.io/", "web"),
    ("anthropic-self-assessment-2026", "https://safeguards.anthropic.com/2026/self-assessment/", "web"),
    ("mdpi-ipi-defenses-2026", "https://www.mdpi.com/2073-431x/15/9/570", "web"),
    ("acl-emnlp-2026-76", "https://aclanthology.org/2026.emnlp-main.76/", "web"),
    ("airguard-github", "https://github.com/Sophie508/AIRGuard", "web"),
    ("zenodo-20731176", "https://doi.org/10.5281/zenodo.20731176", "web"),
    # FENCE 2026-11-12
    ("fence-github", "https://github.com/kakaobank/FENCE", "web"),
    ("arxiv-2602.18154", "https://arxiv.org/abs/2602.18154", "arxiv"),
    ("lrec2026-main-712", "https://lrec.elra.info/lrec2026-main-712", "web"),
    ("fence-dataset-doc", "https://github.com/kakaobank/FENCE/blob/main/assets/dataset.md", "web"),
]


def clean(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def title_of(html: str) -> str:
    for pat in (r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)",
                r"<title[^>]*>(.*?)</title>",
                r"<h1[^>]*>(.*?)</h1>"):
        m = re.search(pat, html, re.I | re.S)
        if m:
            return clean(m.group(1))[:200]
    return ""


def arxiv_abstract(html: str) -> str:
    m = re.search(r"<blockquote[^>]*class=[\"'][^\"']*abstract[^\"']*[\"'][^>]*>(.*?)</blockquote>",
                  html, re.I | re.S)
    if m:
        return clean(m.group(1)).replace("Abstract:", "").strip()[:3000]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["arxiv", "web"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    MAN.parent.mkdir(parents=True, exist_ok=True)
    ok = err = 0
    for key, url, kind in WEB:
        if a.only and kind != a.only:
            continue
        rec = {"type": "web-page", "key": key, "url": url,
               "sources": ["web:list-agent-security-2026-11-12"],
               "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", "replace")
            title = title_of(html)
            abstract = arxiv_abstract(html) if kind == "arxiv" else ""
            text = clean(html)
            body = text[:6000]
            (OUT / f"{key}.html").write_text(html, encoding="utf-8")
            md = f"# {title or key}\n\nURL: {url}\n\n"
            if abstract:
                md += f"## Abstract\n\n{abstract}\n\n"
            md += f"## Text\n\n{body}\n"
            (OUT / f"{key}.md").write_text(md, encoding="utf-8")
            rec.update({"status": "fetched", "path": str(OUT / f"{key}.md"),
                        "chars": len(text), "title": title, "note": kind})
            ok += 1
            print(f"OK  {key}  {len(text)} chars  {title[:80]}")
        except Exception as e:  # noqa: BLE001
            rec.update({"status": "error", "note": type(e).__name__ + ": " + str(e)[:160]})
            err += 1
            print(f"ERR {key}  {e}")
        with open(MAN, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": ok, "err": err, "dir": str(OUT)}, ensure_ascii=False))
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())