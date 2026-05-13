#!/usr/bin/env python3
"""Validate the chrono-palace memory store.

Checks performed:
- every memory file has YAML frontmatter
- required fields are present per type (name / type / created_at / status)
- upper-layer files (daily / palace / entity / reflection) have non-empty `evidence:`
- every `evidence:` path resolves under <root>
- every [[name]] wikilink resolves to some other file's frontmatter `name:`
- reflection files have evidence_count >= 3
- index/keyword_index.md and index/entity_index.md mention every active file's name
- MEMORY.md exists and is non-empty
- session frontmatter `expires_at` is created_at + ~30 days

Exit codes:
  0 — all green
  1 — validation errors found
  2 — invocation error

Usage:
  python3 tools/validate.py
  python3 tools/validate.py --root /custom/path
  python3 tools/validate.py --json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict
from datetime import timedelta

import _lib as lib


REQUIRED_FIELDS = {"name", "type", "created_at", "status"}
EVIDENCE_REQUIRED_TYPES = {"daily", "palace", "entity", "reflection"}
WIKILINK_RE = re.compile(r"\[\[([a-z0-9][a-z0-9-]*)\]\]")
SESSION_TTL_DAYS = 30


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    args = ap.parse_args()

    root: pathlib.Path = args.root
    if not root.exists():
        print(f"error: root does not exist: {root}", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    names_to_files: dict[str, list[lib.MemoryFile]] = defaultdict(list)
    files: list[lib.MemoryFile] = []

    # Pass 1: load + per-file structural checks
    for mf in lib.walk(root):
        files.append(mf)
        rel = mf.rel_path
        if mf.parse_errors:
            for e in mf.parse_errors:
                errors.append(f"{rel}: {e}")
            continue

        for field in REQUIRED_FIELDS:
            if field not in mf.frontmatter:
                errors.append(f"{rel}: missing required field `{field}`")

        if mf.name:
            names_to_files[mf.name].append(mf)

        if mf.type in EVIDENCE_REQUIRED_TYPES and not mf.evidence:
            errors.append(
                f"{rel}: type={mf.type!r} requires non-empty `evidence:` (floating assertion)"
            )

        if mf.type == "reflection":
            ec = mf.frontmatter.get("evidence_count")
            if not isinstance(ec, int) or ec < 3:
                errors.append(
                    f"{rel}: reflection memory requires evidence_count >= 3 (got {ec!r})"
                )

        if mf.type == "session":
            if mf.created_at and mf.expires_at:
                expected = mf.created_at + timedelta(days=SESSION_TTL_DAYS)
                if abs((mf.expires_at - expected).days) > 1:
                    warnings.append(
                        f"{rel}: expires_at {mf.expires_at} != created_at + {SESSION_TTL_DAYS}d ({expected})"
                    )

        if mf.confidence is not None and not (0.0 <= mf.confidence <= 1.0):
            errors.append(f"{rel}: confidence out of range [0,1]: {mf.confidence}")
        if mf.importance is not None and not (0.0 <= mf.importance <= 1.0):
            errors.append(f"{rel}: importance out of range [0,1]: {mf.importance}")

        if mf.status not in {"active", "tentative", "superseded", "archived", "redacted", "conflict_pending"}:
            errors.append(f"{rel}: unknown status {mf.status!r}")

    # Duplicate `name:` slugs
    for name, fs in names_to_files.items():
        if len(fs) > 1:
            paths = ", ".join(f.rel_path for f in fs)
            errors.append(f"duplicate frontmatter name {name!r} in: {paths}")

    # Pass 2: evidence paths and wikilinks resolve
    name_index = set(names_to_files.keys())
    for mf in files:
        rel = mf.rel_path
        for ev in mf.evidence:
            if ev.startswith("<expired>"):
                continue
            ev_path = (root / ev).resolve()
            if not ev_path.exists():
                errors.append(f"{rel}: evidence path does not exist: {ev}")
        for m in WIKILINK_RE.finditer(mf.body):
            slug = m.group(1)
            if slug not in name_index:
                warnings.append(f"{rel}: dangling wikilink [[{slug}]] (no file has this name:)")

    # Pass 3: MEMORY.md sanity
    memory_md = root / "MEMORY.md"
    if not memory_md.exists():
        errors.append("MEMORY.md is missing at root (the index is mandatory)")
    else:
        text = memory_md.read_text(encoding="utf-8")
        if len(text.strip()) < 20:
            errors.append("MEMORY.md exists but is essentially empty")
        if len(text.splitlines()) > 200:
            warnings.append(
                f"MEMORY.md has {len(text.splitlines())} lines (>200 will be truncated on load)"
            )

    # Pass 4: index coverage (every active named file is in keyword/entity index)
    keyword_idx = (root / "index" / "keyword_index.md")
    entity_idx = (root / "index" / "entity_index.md")
    kw_text = keyword_idx.read_text(encoding="utf-8") if keyword_idx.exists() else ""
    ent_text = entity_idx.read_text(encoding="utf-8") if entity_idx.exists() else ""

    for mf in files:
        if mf.status != "active" or not mf.name:
            continue
        if mf.type == "entity" and mf.name not in ent_text:
            warnings.append(f"{mf.rel_path}: entity {mf.name!r} not referenced in entity_index.md")
        if mf.rel_path not in kw_text and mf.type in {"entity", "daily"}:
            warnings.append(f"{mf.rel_path}: not referenced from keyword_index.md")

    # Report
    report = {
        "root": str(root),
        "files_scanned": len(files),
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Scanned {len(files)} memory file(s) under {root}")
        if errors:
            print(f"\n{len(errors)} ERROR(S):")
            for e in errors:
                print(f"  - {e}")
        if warnings:
            print(f"\n{len(warnings)} warning(s):")
            for w in warnings:
                print(f"  - {w}")
        if not errors and not warnings:
            print("OK — all checks passed.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
