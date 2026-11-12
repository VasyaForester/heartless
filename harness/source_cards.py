#!/usr/bin/env python3
"""Source cards: the missing layer between a reference list and raw text.

The knowledge base has four layers:
  1. technique cards (long, readable descriptions);
  2. article lists (short annotations);
  3. full texts (raw, unsummarised);
  4. repo/dataset clones (mostly only a manifest row).

This generator adds the missing fifth layer for layer 4: one card per
manifest entry with "what is inside / which file to open / what is absent".
It never edits the source; cards are derived and can be regenerated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
MANIFEST = WORK / "prompt_injection_ctf" / "raw" / "sources" / "artifacts" / "manifest.jsonl"
OUT = WORK / "prompt_injection_ctf" / "knowledge_base" / "source-cards"
README_NAMES = ("README.md", "README.rst", "README.txt", "readme.md")


def _repo_path(entry: dict) -> pathlib.Path | None:
    raw = entry.get("path") or ""
    if not raw:
        return None
    p = pathlib.Path(raw)
    if not p.is_absolute():
        p = WORK / p
    if p.is_file():
        p = p.parent
    return p if p.exists() else None


def _readme(path: pathlib.Path):
    for name in README_NAMES:
        p = path / name
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"^#\s+(.+)$", text, re.M)
            title = m.group(1).strip() if m else path.name
            return str(p), title, text[:900]
    return None, path.name, ""


def _top_files(path: pathlib.Path, limit: int = 14) -> str:
    try:
        names = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
    except OSError:
        return "(unreadable)"
    return ", ".join(names[:limit]) + (" ..." if len(names) > limit else "")


def _key(entry: dict, path: pathlib.Path | None) -> str:
    raw = entry.get("key") or entry.get("url") or (path.name if path else "source")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw)).strip("-")[:90]
    return safe or "source"


def build_card(entry: dict) -> str:
    path = _repo_path(entry)
    readme_path, title, readme_text = (None, entry.get("key") or entry.get("url") or "source", "")
    if path:
        readme_path, title, readme_text = _readme(path)
    status = entry.get("status") or "unknown"
    absent = []
    if status != "cloned":
        absent.append(f"manifest status: {status}")
    if path and not readme_path:
        absent.append("no README")
    if entry.get("note"):
        absent.append(str(entry["note"]))
    if not path:
        absent.append("local path missing")
    body = [
        f"# {title}",
        "",
        f"- canonical: {entry.get('url') or entry.get('key') or 'unknown'}",
        f"- local: {path or 'missing'}",
        f"- type: {entry.get('type') or 'repo/dataset'}",
        f"- status: {status}",
        f"- what inside: {_top_files(path) if path else 'not available'}",
        f"- which file to open: {readme_path or 'README first, then the manifest row'}",
        f"- what is absent: {'; '.join(absent) if absent else 'nothing recorded'}",
        f"- content hash: {entry.get('sha256') or entry.get('hash') or (str(path) if path else 'n/a')}",
        "",
        "## README head",
        "",
        readme_text.strip()[:900] if readme_text.strip() else "_(no README)_",
        "",
    ]
    return "\n".join(body)


def write_cards(limit: int | None = None) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    entries = []
    if MANIFEST.is_file():
        for line in MANIFEST.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    for entry in entries:
        path = _repo_path(entry)
        key = _key(entry, path)
        target = OUT / f"{key}.md"
        card = build_card(entry)
        if target.exists() and target.read_text(encoding="utf-8", errors="replace") == card:
            skipped += 1
        else:
            target.write_text(card, encoding="utf-8")
            written += 1
        if limit and written >= limit:
            break
    return {"written": written, "unchanged": skipped, "total": len(entries),
            "dir": str(OUT)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    print(json.dumps(write_cards(a.limit or None), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())