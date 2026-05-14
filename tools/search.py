#!/usr/bin/env python3
"""Keyword search across the memory store with the scoring formula from
references/retrieval.md:

  score = 0.40 * semantic   (neural embedding cosine if cache + library
                             available, else TF-IDF cosine)
        + 0.20 * recency    (created_at within last 90d → linear decay)
        + 0.20 * importance
        + 0.10 * entity     (query mentions an entity name)
        + 0.10 * confidence

The semantic component has two backends:

  1. neural (preferred): uses sentence-transformers + the SQLite cache
     built by `tools/embed.py`. Multilingual, semantic — finds files
     by meaning, not just shared tokens.
  2. tf-idf (fallback): pure stdlib, no model download. Mixed-language
     tokenizer; works out-of-the-box.

The choice is automatic. You can force one with `--backend {neural,tfidf}`.

Active-only by default — pass --include-superseded to widen.

Usage:
  python3 tools/search.py "chrono palace"
  python3 tools/search.py --type palace "memory"
  python3 tools/search.py --top 5 "user preference"
  python3 tools/search.py --backend tfidf "force fallback"
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sqlite3
import struct
import sys

import _lib as lib


# Pool the bits of a memory file that should participate in semantic matching.
# Body is capped to keep search snappy on large stores.
def _pool_text(mf: lib.MemoryFile) -> str:
    topics = mf.frontmatter.get("topics") or []
    if not isinstance(topics, list):
        topics = []
    return " ".join([
        mf.frontmatter.get("description") or "",
        mf.name or "",
        " ".join(str(t) for t in topics),
        mf.body[:4000],
    ])


def _corpus_vectors_and_idf(
    files: list[lib.MemoryFile],
) -> tuple[dict[pathlib.Path, dict[str, float]], dict[str, float]]:
    """Tokenize every file once, build IDF, then build a TF-IDF vector per file."""
    tokens_by_file: dict[pathlib.Path, list[str]] = {}
    for mf in files:
        tokens_by_file[mf.path] = lib.tokenize(_pool_text(mf))
    idf = lib.build_idf(list(tokens_by_file.values()))
    vectors = {p: lib.tfidf_vector(tokens, idf) for p, tokens in tokens_by_file.items()}
    return vectors, idf


def _score_query_semantic(
    query: str,
    idf: dict[str, float],
    vectors: dict[pathlib.Path, dict[str, float]],
    mf: lib.MemoryFile,
) -> float:
    q_tokens = lib.tokenize(query)
    if not q_tokens:
        return 0.0
    q_vec = lib.tfidf_vector(q_tokens, idf)
    d_vec = vectors.get(mf.path, {})
    return lib.cosine(q_vec, d_vec)


# ---------- Neural backend (optional) ----------

def _neural_available(root: pathlib.Path) -> tuple[bool, str | None]:
    """Return (True, model_name) if neural cache exists AND library importable.

    If the cache exists but sentence-transformers cannot be imported, emit a
    one-line stderr warning so the user notices the silent downgrade — they
    likely built a cache previously and a later environment change removed
    the library.
    """
    cache = root / ".cache" / "embeddings.sqlite"
    if not cache.exists():
        return False, None
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        print(
            f"warning: neural embedding cache exists at {cache} but "
            "sentence-transformers is not importable; falling back to TF-IDF. "
            "Run `pip install -r requirements-optional.txt` to restore neural search.",
            file=sys.stderr,
        )
        return False, None
    conn = sqlite3.connect(str(cache))
    row = conn.execute(
        "SELECT model, COUNT(*) FROM embeddings GROUP BY model "
        "ORDER BY COUNT(*) DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row or row[1] == 0:
        return False, None
    return True, row[0]


def _load_neural_cache(root: pathlib.Path, model_name: str) -> tuple[dict[str, list[float]], int]:
    conn = sqlite3.connect(str(root / ".cache" / "embeddings.sqlite"))
    out: dict[str, list[float]] = {}
    dim = 0
    for path, dim_, vec in conn.execute(
        "SELECT path, dim, vec FROM embeddings WHERE model = ?", (model_name,)
    ):
        dim = dim_
        out[path] = list(struct.unpack(f"{dim}f", vec))
    conn.close()
    return out, dim


def _encode_query_neural(query: str, model_name: str) -> list[float]:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    v = model.encode([query], normalize_embeddings=True)[0]
    return v.tolist()


def _dense_cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    # Both already L2-normalized by sentence-transformers; cosine = dot product
    return sum(x * y for x, y in zip(a, b))


def _score_recency(mf: lib.MemoryFile, today: object) -> float:
    if not mf.created_at:
        return 0.0
    age = (today - mf.created_at).days
    if age <= 0:
        return 1.0
    if age >= 90:
        return 0.0
    return 1.0 - (age / 90.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("query", nargs="+")
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--type", choices=["session", "daily", "palace", "entity", "reflection"],
                    help="restrict to one memory type")
    ap.add_argument("--top", type=int, default=10, help="number of hits to show")
    ap.add_argument("--include-superseded", action="store_true")
    ap.add_argument("--min-score", type=float, default=0.05,
                    help="drop hits below this total score (default 0.05)")
    ap.add_argument("--backend", choices=["auto", "neural", "tfidf"], default="auto",
                    help="semantic backend (default: auto — neural if available)")
    args = ap.parse_args()

    q = " ".join(args.query)
    today = lib.today()

    all_files = list(lib.walk(args.root))

    # Decide backend
    backend = args.backend
    neural_ok, neural_model = _neural_available(args.root)
    if backend == "auto":
        backend = "neural" if neural_ok else "tfidf"
    elif backend == "neural" and not neural_ok:
        print("warning: --backend neural requested but cache/library unavailable; "
              "falling back to tfidf", file=sys.stderr)
        backend = "tfidf"

    # Prepare per-backend state
    if backend == "neural":
        neural_vecs, _ = _load_neural_cache(args.root, neural_model)
        q_vec_neural = _encode_query_neural(q, neural_model)
        vectors_tfidf, idf = None, None
    else:
        vectors_tfidf, idf = _corpus_vectors_and_idf(all_files)
        neural_vecs, q_vec_neural = None, None

    # Entity name set, for entity_match scoring
    entity_names: set[str] = {mf.name for mf in all_files if mf.type == "entity" and mf.name}
    q_tokens = set(lib.tokenize(q))
    query_hits_entity = bool(q_tokens & entity_names)

    scored: list[tuple[float, lib.MemoryFile, dict[str, float]]] = []
    for mf in all_files:
        if args.type and mf.type != args.type:
            continue
        if not args.include_superseded and mf.status in {"superseded", "archived", "redacted"}:
            continue

        if backend == "neural":
            s_sem = _dense_cosine(q_vec_neural, neural_vecs.get(mf.rel_path, []))
        else:
            s_sem = _score_query_semantic(q, idf, vectors_tfidf, mf)
        s_rec = _score_recency(mf, today)
        s_imp = mf.importance or 0.0
        s_ent = 1.0 if (query_hits_entity and mf.name in q_tokens) else 0.0
        s_conf = mf.confidence or 0.0

        total = 0.40 * s_sem + 0.20 * s_rec + 0.20 * s_imp + 0.10 * s_ent + 0.10 * s_conf
        if total < args.min_score:
            continue
        scored.append((total, mf, {
            "semantic": s_sem, "recency": s_rec, "importance": s_imp,
            "entity": s_ent, "confidence": s_conf,
        }))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        print(f"No hits for {q!r} above min-score={args.min_score}.")
        return 0

    print(f"Query: {q!r}  [backend={backend}]"
          f"{f'  model={neural_model}' if backend == 'neural' else ''}"
          f"  (top {min(args.top, len(scored))} of {len(scored)})\n")
    for total, mf, breakdown in scored[: args.top]:
        bd = "  ".join(f"{k}={v:.2f}" for k, v in breakdown.items())
        print(f"[{total:.3f}] {mf.rel_path}")
        print(f"    {mf.frontmatter.get('description', '')}")
        print(f"    {bd}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
