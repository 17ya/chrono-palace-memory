#!/usr/bin/env python3
"""Build / refresh the local neural-embedding cache for search.py.

Optional dependency: `sentence-transformers` (and its `torch` requirement).
If it's not installed, this tool tells you how to install it. search.py
silently falls back to TF-IDF when the cache is missing or sentence-
transformers is unavailable, so the skill remains zero-config without it.

Cache layout:
    ~/.memory/.cache/embeddings.sqlite
    Table: embeddings(path TEXT PRIMARY KEY, mtime REAL, model TEXT, dim INT, vec BLOB)
    Files whose mtime is unchanged are skipped — incremental builds.

Privacy note: all embedding is local. NO content leaves your machine.
This is deliberate — memory data is private.

Model selection (in order of precedence):
  1. --model <name>
  2. env var CPM_EMBEDDING_MODEL
  3. default: paraphrase-multilingual-MiniLM-L12-v2  (118MB, 384-d, 50+ langs)

Usage:
  python3 tools/embed.py              # incremental rebuild
  python3 tools/embed.py --full       # rebuild every file
  python3 tools/embed.py --stats      # report cache size / coverage
  python3 tools/embed.py --check      # check dependency availability
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sqlite3
import struct
import sys

import _lib as lib


DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def _resolve_model(cli_model: str | None) -> str:
    return cli_model or os.environ.get("CPM_EMBEDDING_MODEL") or DEFAULT_MODEL


def _import_st() -> tuple[bool, str]:
    """Return (available, message). Defers heavy import until needed."""
    try:
        import sentence_transformers  # noqa: F401
        return True, "sentence-transformers is available"
    except ImportError:
        return False, (
            "sentence-transformers is not installed.\n"
            "Install with one of:\n"
            "  pip install sentence-transformers\n"
            "  pip install -r requirements-optional.txt\n"
            "search.py will keep working — it falls back to TF-IDF."
        )


def _cache_path(root: pathlib.Path) -> pathlib.Path:
    return root / ".cache" / "embeddings.sqlite"


def _open_cache(root: pathlib.Path) -> sqlite3.Connection:
    p = _cache_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE IF NOT EXISTS embeddings (
        path TEXT PRIMARY KEY,
        mtime REAL NOT NULL,
        model TEXT NOT NULL,
        dim INTEGER NOT NULL,
        vec BLOB NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON embeddings(model)")
    return conn


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"{dim}f", blob))


def _text_of(mf: lib.MemoryFile) -> str:
    topics = mf.frontmatter.get("topics") or []
    if not isinstance(topics, list):
        topics = []
    return "\n".join([
        mf.frontmatter.get("description") or "",
        mf.name or "",
        " ".join(str(t) for t in topics),
        mf.body[:4000],
    ])


def cmd_check() -> int:
    ok, msg = _import_st()
    print(msg)
    return 0 if ok else 1


def cmd_stats(root: pathlib.Path) -> int:
    cache_file = _cache_path(root)
    if not cache_file.exists():
        print(f"No cache at {cache_file}.")
        return 0
    conn = _open_cache(root)
    total, = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
    by_model = conn.execute(
        "SELECT model, COUNT(*) FROM embeddings GROUP BY model"
    ).fetchall()
    size = cache_file.stat().st_size
    print(f"Cache: {cache_file} ({size / 1024:.1f} KB)")
    print(f"  total entries: {total}")
    for model, n in by_model:
        print(f"  - {model}: {n}")
    return 0


def cmd_build(root: pathlib.Path, model_name: str, full: bool) -> int:
    ok, msg = _import_st()
    if not ok:
        print(msg, file=sys.stderr)
        return 1
    from sentence_transformers import SentenceTransformer

    print(f"Loading model: {model_name} ...")
    model = SentenceTransformer(model_name)
    dim = model.get_sentence_embedding_dimension()
    print(f"  dim={dim}")

    conn = _open_cache(root)
    cur = conn.cursor()

    to_embed: list[tuple[lib.MemoryFile, float]] = []
    for mf in lib.walk(root):
        try:
            mtime = mf.path.stat().st_mtime
        except FileNotFoundError:
            continue
        if not full:
            row = cur.execute(
                "SELECT mtime, model FROM embeddings WHERE path = ?",
                (mf.rel_path,),
            ).fetchone()
            if row and row[0] == mtime and row[1] == model_name:
                continue
        to_embed.append((mf, mtime))

    if not to_embed:
        print("Cache is up to date.")
        return 0

    print(f"Embedding {len(to_embed)} file(s)...")
    texts = [_text_of(mf) for mf, _ in to_embed]
    vectors = model.encode(texts, show_progress_bar=len(texts) > 20, normalize_embeddings=True)

    for (mf, mtime), v in zip(to_embed, vectors):
        cur.execute(
            "REPLACE INTO embeddings(path, mtime, model, dim, vec) VALUES (?, ?, ?, ?, ?)",
            (mf.rel_path, mtime, model_name, dim, _pack(v.tolist())),
        )
    conn.commit()
    print(f"Wrote {len(to_embed)} embedding(s) to {_cache_path(root)}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--model", help=f"override embedding model (default {DEFAULT_MODEL})")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true",
                   help="rebuild every file, ignore mtime cache")
    g.add_argument("--stats", action="store_true", help="show cache stats and exit")
    g.add_argument("--check", action="store_true",
                   help="check dependency availability and exit")
    args = ap.parse_args()

    if args.check:
        return cmd_check()
    if args.stats:
        return cmd_stats(args.root)

    model_name = _resolve_model(args.model)
    return cmd_build(args.root, model_name, args.full)


if __name__ == "__main__":
    sys.exit(main())
