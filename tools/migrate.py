#!/usr/bin/env python3
"""Apply schema migrations to a memory store.

Migrations live in `tools/migrations/<YYYY-MM-DD>-<slug>.py`. Each one
exposes a function:

    def migrate(root: pathlib.Path, dry_run: bool) -> dict:
        '''Return {"changed": [...], "skipped": [...], "errors": [...]}'''

A migration MUST be idempotent — running it twice yields the same result
as running it once. The framework tracks applied migrations in
`<root>/.migrations-applied` (one slug per line). Migrations already
listed are skipped.

Migrations are applied in alphabetical order of filename, which equals
chronological order if you stick to the YYYY-MM-DD prefix.

Usage:
  python3 tools/migrate.py --list             # show pending / applied
  python3 tools/migrate.py                    # dry-run all pending
  python3 tools/migrate.py --apply            # actually apply all pending
  python3 tools/migrate.py --only <slug>      # run one migration by slug

Exit codes:
  0 — clean (nothing to apply, or all applied successfully)
  1 — a migration reported errors or was needed but not applied (dry-run)
  2 — invocation error
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
from typing import Any

import _lib as lib


MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent / "migrations"


def _list_migrations() -> list[pathlib.Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(p for p in MIGRATIONS_DIR.glob("*.py") if not p.name.startswith("_"))


def _slug(path: pathlib.Path) -> str:
    return path.stem


def _applied_set(root: pathlib.Path) -> set[str]:
    f = root / ".migrations-applied"
    if not f.exists():
        return set()
    return {line.strip() for line in f.read_text(encoding="utf-8").splitlines() if line.strip()}


def _record_applied(root: pathlib.Path, slug: str) -> None:
    f = root / ".migrations-applied"
    with f.open("a", encoding="utf-8") as fp:
        fp.write(slug + "\n")


def _load(path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load migration: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--list", action="store_true", help="show migrations and exit")
    ap.add_argument("--apply", action="store_true", help="actually run migrations")
    ap.add_argument("--only", help="run a specific migration by slug")
    args = ap.parse_args()

    root: pathlib.Path = args.root
    if not root.exists():
        print(f"error: root does not exist: {root}", file=sys.stderr)
        return 2

    all_migrations = _list_migrations()
    applied = _applied_set(root)
    pending = [m for m in all_migrations if _slug(m) not in applied]

    if args.list:
        print(f"Root: {root}")
        print(f"Applied ({len(applied)}):")
        for slug in sorted(applied):
            print(f"  ✓ {slug}")
        print(f"Pending ({len(pending)}):")
        for m in pending:
            print(f"  · {_slug(m)}")
        return 0

    if args.only:
        target = next((m for m in all_migrations if _slug(m) == args.only), None)
        if not target:
            print(f"error: no migration {args.only!r}", file=sys.stderr)
            return 2
        if _slug(target) in applied:
            print(f"already applied: {args.only}")
            return 0
        pending = [target]

    if not pending:
        print("Nothing to do — memory store is up to date.")
        return 0

    total_errors = 0

    def _run_one(m: pathlib.Path) -> int:
        slug = _slug(m)
        print(f"\n=== {'Applying' if args.apply else 'DRY-RUN'} migration: {slug} ===")
        errs = 0
        try:
            mod = _load(m)
            if not hasattr(mod, "migrate"):
                print(f"  error: migration {slug} is missing migrate() function",
                      file=sys.stderr)
                return 1
            report: dict[str, list[str]] = mod.migrate(root, dry_run=not args.apply)
            for k in ("changed", "skipped", "errors"):
                items = report.get(k, [])
                if items:
                    print(f"  {k}: {len(items)}")
                    for x in items[:20]:
                        print(f"    - {x}")
                    if len(items) > 20:
                        print(f"    ... and {len(items) - 20} more")
            if report.get("errors"):
                return len(report["errors"])
            if args.apply:
                _record_applied(root, slug)
                print(f"  recorded as applied")
        except Exception as e:
            print(f"  CRASH: {e}", file=sys.stderr)
            errs += 1
        return errs

    if args.apply:
        # Hold the lock for the duration of all migrations
        try:
            with lib.file_lock(root, timeout=30.0):
                for m in pending:
                    total_errors += _run_one(m)
        except lib.LockTimeout as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    else:
        for m in pending:
            total_errors += _run_one(m)

    if not args.apply and pending:
        print(f"\n(Dry run. {len(pending)} migration(s) pending. Pass --apply to run them.)")
        return 1
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
