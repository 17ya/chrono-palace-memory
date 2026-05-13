#!/usr/bin/env python3
"""Detect potential conflicts before writing a new memory.

Two modes:

  --topic <slug>          # find all active memories tagged with this topic
  --against <file>        # given a draft memory file, scan for collisions

A "potential conflict" is:
  - same `name:` slug exists with status != superseded
  - same entity_type + entity name in entities/
  - palace decision section header overlap (heuristic, case-insensitive)
  - description field ≥70% token overlap with an existing active memory of
    the same type

The agent is responsible for the final call — this tool reports candidates,
it does not auto-resolve.

Exit codes:
  0 — no candidates
  1 — candidates found
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import _lib as lib


def tokenize(text: str) -> set[str]:
    return {t for t in (
        "".join(c.lower() if c.isalnum() else " " for c in text or "").split()
    ) if len(t) > 1}


def overlap(a: str, b: str) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--topic", help="topic/slug to look up")
    ap.add_argument("--against", type=pathlib.Path, help="draft memory file to compare")
    ap.add_argument("--threshold", type=float, default=0.7,
                    help="token-overlap threshold for description collision (default 0.7)")
    args = ap.parse_args()

    if not args.topic and not args.against:
        ap.error("one of --topic or --against is required")

    all_files = list(lib.walk(args.root))
    candidates: list[tuple[str, lib.MemoryFile]] = []

    if args.topic:
        topic = args.topic
        for mf in all_files:
            if mf.status not in {"active", "tentative", "conflict_pending"}:
                continue
            if mf.name == topic:
                candidates.append(("exact name match", mf))
                continue
            topics = mf.frontmatter.get("topics") or []
            if isinstance(topics, list) and topic in topics:
                candidates.append(("listed in `topics:`", mf))
                continue
            if topic.lower() in (mf.frontmatter.get("description") or "").lower():
                candidates.append(("appears in description", mf))

    if args.against:
        draft = lib.load(args.against)
        if draft.parse_errors:
            print(f"error: draft file has parse errors: {draft.parse_errors}", file=sys.stderr)
            return 2
        draft_desc = draft.frontmatter.get("description") or ""
        draft_type = draft.type
        for mf in all_files:
            if mf.path == draft.path:
                continue
            if mf.status not in {"active", "tentative"}:
                continue
            if draft.name and mf.name == draft.name:
                candidates.append(("same name slug (would duplicate)", mf))
                continue
            if mf.type == draft_type:
                desc = mf.frontmatter.get("description") or ""
                ov = overlap(draft_desc, desc)
                if ov >= args.threshold:
                    candidates.append((f"description overlap {ov:.0%}", mf))

    if not candidates:
        print("No conflict candidates.")
        return 0

    print(f"Found {len(candidates)} candidate(s):\n")
    for reason, mf in candidates:
        print(f"- [{reason}] {mf.rel_path}")
        print(f"    name:        {mf.name}")
        print(f"    description: {mf.frontmatter.get('description')}")
        print(f"    status:      {mf.status}")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
