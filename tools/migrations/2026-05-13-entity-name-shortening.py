"""2026-05-13: shorten entity frontmatter `name:` slugs.

Before:
    name: entity-user
    name: entity-project-memory-skill
    name: entity-concept-chrono-palace-memory

After:
    name: user
    name: memory-skill
    name: chrono-palace-memory

Rationale: long prefixed names didn't match wikilinks (`[[memory-skill]]`)
or entity_index entries. Now entity files use the bare slug; palace files
keep their `palace-*` prefix for disambiguation.

Also normalizes confidence from string {high,medium,low} to numeric.

Idempotent: files already using short names / numeric confidence are
left alone.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

# Make _lib importable when invoked via migrate.py
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import _lib as lib  # noqa: E402


CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}

ENTITY_NAME_RE = re.compile(
    r"^name:\s*entity-(?:user|project|concept|tool|person)-?(.*)$",
    re.MULTILINE,
)
CONFIDENCE_STR_RE = re.compile(
    r"^confidence:\s*(high|medium|low)\b.*$",
    re.MULTILINE,
)


def migrate(root: pathlib.Path, dry_run: bool) -> dict[str, list[str]]:
    changed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    entities_dir = root / "entities"
    if not entities_dir.exists():
        return {"changed": changed, "skipped": ["no entities/ directory"], "errors": errors}

    for path in sorted(entities_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"{path}: read failed: {e}")
            continue

        original = text
        # Shorten name
        m = ENTITY_NAME_RE.search(text)
        if m:
            slug = m.group(1).strip().lstrip("-")
            if slug:
                text = ENTITY_NAME_RE.sub(f"name: {slug}", text, count=1)

        # Normalize confidence
        m2 = CONFIDENCE_STR_RE.search(text)
        if m2:
            v = CONFIDENCE_MAP[m2.group(1).lower()]
            text = CONFIDENCE_STR_RE.sub(f"confidence: {v}", text, count=1)

        rel = path.relative_to(root)
        if text == original:
            skipped.append(str(rel))
            continue
        if dry_run:
            changed.append(f"{rel} (preview)")
        else:
            lib.atomic_write(path, text)
            changed.append(str(rel))

    return {"changed": changed, "skipped": skipped, "errors": errors}
