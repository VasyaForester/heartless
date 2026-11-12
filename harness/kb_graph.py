#!/usr/bin/env python3
"""Graph RAG over the local knowledge base (SQLite FTS5 + typed graph).

The "dump" (knowledge_base, datasets, raw READMEs) is indexed once into
artifacts/kb_graph.db. Retrieval is: FTS5 seed chunks -> their nodes ->
1-hop graph expansion -> ranked chunks with citations. No LLM, no embeddings.

Usage:
  python3 harness/kb_graph.py build
  python3 harness/kb_graph.py query "gift card discount structure"
  python3 harness/kb_graph.py related bench:injecagent
  python3 harness/kb_graph.py stats
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent
DB_DEFAULT = WORK / "artifacts" / "kb_graph.db"
BENCH_FILE = WORK / "datasets" / "agent-security-benchmarks-2026-11-12.md"
MAP_FILE = WORK / "datasets" / "lbp" / "benchmark-derived-classes-2026-11-12.md"

DOC_GLOBS = [
    "prompt_injection_ctf/knowledge_base/*.md",
    "prompt_injection_ctf/knowledge_base/source-cards/*.md",
    "prompt_injection_ctf/benchmarks/*.md",
    "prompt_injection_ctf/attacks/*.md",
    "datasets/**/*.md",
    "deliverables/ipi-knowledge-structure.md",
    "harness/*.md",
    "prompt_injection_ctf/raw/sources/web/*.md",
    "prompt_injection_ctf/raw/sources/artifacts/**/README.md",
]

SCEN = ["scam-retail", "double-refund", "christmas-giftcard-scam",
        "negative-quantity-exploit", "banking-idor-exploit"]
MODELS = ["Copper Turtle Brave", "Diamond Whale Bold",
          "Sand Ant Plus Ultra", "Yellow Kangaroo Extreme"]

SOURCE_RE = re.compile(
    r"https?://(?:github\.com|huggingface\.co/datasets|arxiv\.org/abs|"
    r"www\.usenix\.org|openreview\.net|lakera\.ai|baxbench\.com)[^\s\)\]\"'<>]+")
ARXIV_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})")
TECH_RE = re.compile(r"\b([A-F])(\d{1,2})\b")
BENCH: dict[str, tuple[str, str]] = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
  id INTEGER PRIMARY KEY, path TEXT UNIQUE, title TEXT, sha TEXT UNIQUE, bytes INTEGER);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY, doc_id INTEGER, heading TEXT, text TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text, content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TABLE IF NOT EXISTS nodes(
  id TEXT PRIMARY KEY, kind TEXT, title TEXT, url TEXT);
CREATE TABLE IF NOT EXISTS edges(
  src TEXT, dst TEXT, kind TEXT, weight INTEGER DEFAULT 1, PRIMARY KEY(src, dst, kind));
CREATE TABLE IF NOT EXISTS chunk_nodes(
  chunk_id INTEGER, node_id TEXT, PRIMARY KEY(chunk_id, node_id));
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
"""


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def load_bench() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    if not BENCH_FILE.exists():
        return out
    text = BENCH_FILE.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"^\d+\.\s+(https?://\S+)", text, re.M):
        url = m.group(1).rstrip(".,;")
        if "github.com/" in url:
            name = url.rstrip("/").split("/")[-1]
        elif "huggingface.co/datasets/" in url:
            name = url.split("datasets/")[-1].split("/")[-1]
        elif "arxiv.org/abs/" in url:
            name = "arXiv " + url.rsplit("/", 1)[-1]
        else:
            name = url.split("//")[-1].split("/")[0]
        out[slug(name)] = (name, url)
    return out


def source_id(url: str) -> tuple[str, str]:
    u = url.rstrip(".,;")
    m = re.search(r"github\.com/([^/]+)/([^/?#]+)", u)
    if m:
        return f"src:github/{slug(m.group(1) + '-' + m.group(2))}", u
    m = re.search(r"huggingface\.co/datasets/([^/?#]+)/([^/?#]+)", u)
    if m:
        return f"src:hf/{slug(m.group(1) + '-' + m.group(2))}", u
    m = re.search(r"arxiv\.org/abs/([^/?#]+)", u)
    if m:
        return f"src:arxiv/{m.group(1)}", u
    return "src:" + slug(u), u


def extract_nodes(text: str) -> dict[str, dict]:
    nodes: dict[str, dict] = {}
    for m in SOURCE_RE.finditer(text):
        nid, u = source_id(m.group(0))
        nodes[nid] = {"kind": "source", "title": u, "url": u}
    for m in ARXIV_RE.finditer(text):
        pid = m.group(1)
        nodes[f"paper:{pid}"] = {"kind": "paper", "title": f"arXiv {pid}",
                                 "url": f"https://arxiv.org/abs/{pid}"}
    for s in SCEN:
        if s in text:
            nodes[f"scen:{s}"] = {"kind": "scenario", "title": s, "url": ""}
    for m in TECH_RE.finditer(text):
        t = m.group(1) + m.group(2)
        nodes[f"tech:{t}"] = {"kind": "technique", "title": t, "url": ""}
    low = text.lower()
    for m in MODELS:
        if m.lower() in low:
            nodes[f"model:{m}"] = {"kind": "model", "title": m, "url": ""}
    for b, (title, url) in BENCH.items():
        if title.lower() in low or b in low:
            nodes[f"bench:{b}"] = {"kind": "benchmark", "title": title, "url": url}
    return nodes


def chunk_doc(text: str):
    lines = text.splitlines()
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    chunks = []
    heading = ""
    buf = []
    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            if buf:
                chunks.append((heading, "\n".join(buf).strip()))
            heading = line.lstrip("#").strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        chunks.append((heading, "\n".join(buf).strip()))
    out = []
    for h, c in chunks:
        if len(c) <= 2500:
            if c:
                out.append((h, c))
            continue
        cur = ""
        for part in c.split("\n\n"):
            if len(cur) + len(part) + 2 > 2000 and cur:
                out.append((h, cur.strip()))
                cur = part
            else:
                cur += ("\n\n" if cur else "") + part
        if cur.strip():
            out.append((h, cur.strip()))
    return title or "untitled", out


def counts(conn: sqlite3.Connection) -> dict:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("docs", "chunks", "nodes", "edges", "chunk_nodes")}


def build(db: pathlib.Path) -> dict:
    global BENCH
    BENCH = load_bench()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    for t in ("chunks_fts", "chunk_nodes", "edges", "nodes", "chunks", "docs"):
        try:
            conn.execute(f"DELETE FROM {t}")
        except sqlite3.OperationalError:
            pass
    paths = set()
    for pat in DOC_GLOBS:
        for p in WORK.glob(pat):
            if p.is_file():
                paths.add(p)
    docs = chunks = duplicates = skipped = 0
    for path in sorted(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped += 1
            continue
        if len(text.strip()) < 40:
            skipped += 1
            continue
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if conn.execute("SELECT 1 FROM docs WHERE sha=?", (sha,)).fetchone():
            duplicates += 1
            continue
        title, chunks_list = chunk_doc(text)
        rel = str(path.relative_to(WORK))
        cur = conn.execute("INSERT INTO docs(path,title,sha,bytes) VALUES(?,?,?,?)",
                           (rel, title, sha, len(text)))
        doc_id = cur.lastrowid
        docs += 1
        doc_node = f"doc:{rel}"
        conn.execute("INSERT OR IGNORE INTO nodes(id,kind,title,url) VALUES(?,?,?,?)",
                     (doc_node, "doc", title, rel))
        for heading, ctext in chunks_list:
            cur = conn.execute("INSERT INTO chunks(doc_id,heading,text) VALUES(?,?,?)",
                               (doc_id, heading, ctext))
            cid = cur.lastrowid
            chunks += 1
            conn.execute("INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", (cid, ctext))
            ns = extract_nodes(ctext)
            node_ids = list(ns.keys())
            for nid, meta in ns.items():
                conn.execute("INSERT OR IGNORE INTO nodes(id,kind,title,url) VALUES(?,?,?,?)",
                             (nid, meta["kind"], meta["title"], meta["url"]))
                conn.execute("INSERT OR IGNORE INTO chunk_nodes(chunk_id,node_id) VALUES(?,?)",
                             (cid, nid))
                conn.execute("INSERT OR IGNORE INTO edges(src,dst,kind,weight) VALUES(?,?,?,1)",
                             (doc_node, nid, "mentions"))
                if nid.startswith("src:"):
                    conn.execute("INSERT OR IGNORE INTO edges(src,dst,kind,weight) VALUES(?,?,?,1)",
                                 (doc_node, nid, "cites"))
            for i in range(len(node_ids)):
                for j in range(i + 1, len(node_ids)):
                    conn.execute(
                        "INSERT INTO edges(src,dst,kind,weight) VALUES(?,?,?,1)"
                        " ON CONFLICT(src,dst,kind) DO UPDATE SET weight=weight+1",
                        (node_ids[i], node_ids[j], "related"))
    if MAP_FILE.exists():
        text = MAP_FILE.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"-\s+\*\*(.+?)\*\*\s*→\s*(.+)", text):
            name = m.group(1).strip()
            bnode = f"bench:{slug(name)}"
            conn.execute("INSERT OR IGNORE INTO nodes(id,kind,title,url) VALUES(?,?,?,?)",
                         (bnode, "benchmark", name, ""))
            for s in re.split(r"[/,]", m.group(2)):
                s = s.strip().split()[0].strip("`") if s.strip() else ""
                if not s:
                    continue
                snode = f"scen:{s}"
                conn.execute("INSERT OR IGNORE INTO nodes(id,kind,title,url) VALUES(?,?,?,?)",
                             (snode, "scenario", s, ""))
                conn.execute("INSERT OR IGNORE INTO edges(src,dst,kind,weight) VALUES(?,?,?,5)",
                             (bnode, snode, "maps_to"))
    conn.commit()
    stats = counts(conn)
    stats.update({"duplicates": duplicates, "skipped": skipped})
    conn.close()
    return stats


def query(db: pathlib.Path, question: str, limit: int = 8, hops: int = 1, as_json: bool = False):
    conn = sqlite3.connect(str(db), timeout=30)
    conn.row_factory = sqlite3.Row
    toks = [t for t in re.findall(r"[\w\-]+", question, flags=re.UNICODE) if len(t) > 1]
    if not toks:
        return []
    match = " OR ".join('"' + t.replace('"', '""') + '"' for t in toks)
    try:
        rows = conn.execute(
            "SELECT c.id,c.heading,c.text,d.path,d.title,bm25(chunks_fts) AS r"
            " FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid"
            " JOIN docs d ON d.id=c.doc_id WHERE chunks_fts MATCH ?"
            " ORDER BY r LIMIT ?", (match, limit)).fetchall()
    except sqlite3.OperationalError as e:
        print(f"FTS error: {e}", file=sys.stderr)
        return []
    seed_ids = {r["id"] for r in rows}
    nodes = set()
    for r in rows:
        for x in conn.execute("SELECT node_id FROM chunk_nodes WHERE chunk_id=?", (r["id"],)):
            nodes.add(x["node_id"])
    extra = []
    if hops:
        for n in list(nodes):
            for e in conn.execute(
                    "SELECT dst FROM edges WHERE src=? AND kind='related' ORDER BY weight DESC LIMIT 6",
                    (n,)):
                if e["dst"] not in nodes:
                    nodes.add(e["dst"])
    for n in nodes:
        for c in conn.execute(
                "SELECT c.id,c.heading,c.text,d.path,d.title"
                " FROM chunk_nodes cn JOIN chunks c ON c.id=cn.chunk_id"
                " JOIN docs d ON d.id=c.doc_id WHERE cn.node_id=? ORDER BY c.id LIMIT 1", (n,)):
            if c["id"] not in seed_ids:
                extra.append(dict(c))
    out = []
    for r in rows:
        out.append({"path": r["path"], "title": r["title"], "heading": r["heading"],
                    "text": r["text"][:1200], "rank": r["r"], "nodes": sorted(nodes)[:12]})
    for r in extra[:limit]:
        out.append({"path": r["path"], "title": r["title"], "heading": r["heading"],
                    "text": r["text"][:800], "rank": None, "nodes": []})
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for i, r in enumerate(out, 1):
            print(f"## {i}. {r['title']} — {r['heading']} ({r['path']})")
            print(r["text"].strip())
            if r["nodes"]:
                print("nodes:", ", ".join(r["nodes"]))
            print()
    return out


def related(db: pathlib.Path, node: str, limit: int = 20) -> None:
    conn = sqlite3.connect(str(db), timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT src,dst,kind,weight FROM edges WHERE src=? OR dst=?"
        " ORDER BY weight DESC LIMIT ?", (node, node, limit)).fetchall()
    for r in rows:
        print(f"{r['weight']:3}  {r['kind']:10}  {r['src']} -> {r['dst']}")


def stats(db: pathlib.Path) -> None:
    conn = sqlite3.connect(str(db), timeout=30)
    print(json.dumps(counts(conn), ensure_ascii=False, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--db", default=str(DB_DEFAULT))
    q = sub.add_parser("query")
    q.add_argument("question", nargs="+")
    q.add_argument("--db", default=str(DB_DEFAULT))
    q.add_argument("--limit", type=int, default=8)
    q.add_argument("--hops", type=int, default=1)
    q.add_argument("--json", action="store_true")
    r = sub.add_parser("related")
    r.add_argument("node")
    r.add_argument("--db", default=str(DB_DEFAULT))
    r.add_argument("--limit", type=int, default=20)
    s = sub.add_parser("stats")
    s.add_argument("--db", default=str(DB_DEFAULT))
    a = ap.parse_args()
    db = pathlib.Path(a.db)
    if a.cmd == "build":
        print(json.dumps(build(db), ensure_ascii=False, indent=1))
    elif a.cmd == "query":
        query(db, " ".join(a.question), a.limit, a.hops, a.json)
    elif a.cmd == "related":
        related(db, a.node, a.limit)
    else:
        stats(db)
    return 0


if __name__ == "__main__":
    sys.exit(main())