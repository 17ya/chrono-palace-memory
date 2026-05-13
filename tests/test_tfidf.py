#!/usr/bin/env python3
"""Test that TF-IDF semantic scoring actually distinguishes documents.

Regression guard against the original 'all docs score 1.0' bug from the
naive token-overlap implementation.

Usage:
  python3 tests/test_tfidf.py

Exit 0 on success, 1 on failure.
"""

from __future__ import annotations

import pathlib
import sys

# Make tools/ importable
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import _lib as lib  # noqa: E402


def main() -> int:
    docs = [
        ["chrono", "palace", "memory", "system", "design"],
        ["chrono", "palace", "memory"],
        ["preferences", "user", "structured"],
        ["chrono", "palace"],
        ["unrelated", "topic", "elsewhere"],
    ]
    idf = lib.build_idf(docs)
    vectors = [lib.tfidf_vector(d, idf) for d in docs]

    query = lib.tfidf_vector(["chrono", "palace"], idf)
    scores = [lib.cosine(query, v) for v in vectors]

    # Doc 3 ("chrono palace") should score highest (perfectly aligned with the query).
    # Doc 4 ("unrelated") should score 0.
    # All non-zero scores should NOT be identical.
    failures: list[str] = []
    if scores[3] <= 0:
        failures.append(f"doc 3 should score > 0, got {scores[3]:.4f}")
    if scores[4] != 0.0:
        failures.append(f"doc 4 (unrelated) should score 0, got {scores[4]:.4f}")
    nonzero = [s for s in scores if s > 0]
    if len(set(round(s, 3) for s in nonzero)) < 2:
        failures.append(f"non-zero scores should differ; got {nonzero}")

    # Doc 3 should be a top-2 result
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
    if 3 not in ranked[:2]:
        failures.append(f"doc 3 should be in top-2 hits; ranking = {ranked}")

    # Tokenizer: Chinese + English mix should produce both kinds of tokens
    tokens = lib.tokenize("Chrono-Palace 五层架构 with 偏好")
    if "chrono-palace" not in tokens and not any("chrono" in t for t in tokens):
        failures.append(f"tokenizer dropped latin tokens: {tokens}")
    if not any(c in tokens for c in ("五", "层", "架", "构", "偏", "好")):
        failures.append(f"tokenizer dropped CJK tokens: {tokens}")

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        print(f"scores: {[round(s, 4) for s in scores]}")
        return 1

    print("PASS")
    print(f"  query 'chrono palace' scores: {[round(s, 4) for s in scores]}")
    print(f"  ranked top-3: {ranked[:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
