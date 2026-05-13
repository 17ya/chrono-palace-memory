#!/usr/bin/env python3
"""Expire session memories whose TTL has elapsed.

Rule (from references/lifecycle.md):
  A session may be deleted only if:
    1. expires_at <= today
    2. promoted_to is non-empty (i.e. its contents have been carried into daily/palace/entity)

If both conditions hold and --apply is passed, the session file is moved
to <root>/sessions/_expired/<original-relpath>.md (kept for audit, not deleted).
By default this command DRY-RUNS and only reports what it would do.

Exit codes:
  0 — clean run (whether or not anything was expired)
  1 — there are sessions past expires_at that cannot be cleaned (no promoted_to);
      the operator must promote them first.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

import _lib as lib


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--apply", action="store_true",
                    help="actually move expired files; without this flag, just report")
    args = ap.parse_args()

    root: pathlib.Path = args.root
    today = lib.today()

    to_archive: list[lib.MemoryFile] = []
    blocked: list[lib.MemoryFile] = []

    for mf in lib.walk(root):
        if mf.type != "session":
            continue
        if mf.expires_at is None:
            continue
        if mf.expires_at > today:
            continue
        promoted = mf.frontmatter.get("promoted_to") or []
        if not isinstance(promoted, list) or len(promoted) == 0:
            blocked.append(mf)
        else:
            to_archive.append(mf)

    print(f"Today: {today}")
    print(f"Expired & ready to archive: {len(to_archive)}")
    for mf in to_archive:
        print(f"  - {mf.rel_path} (expired {mf.expires_at})")

    print(f"\nExpired but BLOCKED (no promoted_to): {len(blocked)}")
    for mf in blocked:
        print(f"  - {mf.rel_path} (expired {mf.expires_at}) — promote it first!")

    if args.apply and to_archive:
        archive_root = root / "sessions" / "_expired"
        try:
            with lib.file_lock(root):
                for mf in to_archive:
                    rel_from_sessions = mf.path.relative_to(root / "sessions")
                    dest = archive_root / rel_from_sessions
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(mf.path), str(dest))
                    print(f"moved {mf.rel_path} → sessions/_expired/{rel_from_sessions}")
        except lib.LockTimeout as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    elif to_archive:
        print(f"\n(Dry run. Pass --apply to actually move {len(to_archive)} file(s).)")

    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
