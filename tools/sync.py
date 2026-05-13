#!/usr/bin/env python3
"""Sync ~/.memory across machines using a private git repository.

The store itself is just markdown — git is the right transport. This
script is a thin wrapper that:

  - inits ~/.memory as a git repo if needed
  - configures a sensible .gitignore (locks, caches, audit logs stay local)
  - pulls, commits unsynced changes, pushes
  - holds the file_lock so a sync can't race with a memory write

Set up a private remote (GitHub private repo, self-hosted git, etc.):

  cd ~/.memory
  git init
  git remote add origin <private-url>
  python3 ~/.claude/skills/chrono-palace-memory/tools/sync.py --init
  python3 ~/.claude/skills/chrono-palace-memory/tools/sync.py

Usage:
  python3 tools/sync.py --init           # one-time: configure gitignore + initial commit
  python3 tools/sync.py                  # pull, commit any changes, push
  python3 tools/sync.py --status         # show local changes vs remote
  python3 tools/sync.py --dry-run        # show what would happen

Privacy note:
  Use a PRIVATE remote. Memory contains your conversations, preferences,
  user identity. Don't push to a public repo, even an "anonymous" one —
  the content can identify you.

Exit codes:
  0 — success
  1 — git command failed
  2 — invocation / setup error
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

import _lib as lib


MEMORY_GITIGNORE = """\
# chrono-palace-memory: machine-local state.
# Committing these would cause merge conflicts on every sync.
.lock
.cache/
.audit-redactions.log
.status.log

# Never commit OS / editor noise
.DS_Store
*.swp
"""


def _run(cmd: list[str], cwd: pathlib.Path, dry_run: bool, capture: bool = False) -> subprocess.CompletedProcess:
    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(
        cmd, cwd=cwd, capture_output=capture, text=True, check=False
    )


def _git_available() -> bool:
    return shutil.which("git") is not None


def _is_repo(root: pathlib.Path) -> bool:
    return (root / ".git").exists()


def cmd_init(root: pathlib.Path, dry_run: bool) -> int:
    if not _git_available():
        print("error: git not found in PATH", file=sys.stderr)
        return 2
    root.mkdir(parents=True, exist_ok=True)

    gi = root / ".gitignore"
    if not gi.exists() or MEMORY_GITIGNORE not in gi.read_text(encoding="utf-8"):
        if dry_run:
            print(f"  [dry-run] write {gi}")
        else:
            existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
            lib.atomic_write(gi, existing + ("\n" if existing else "") + MEMORY_GITIGNORE)

    if not _is_repo(root):
        r = _run(["git", "init"], root, dry_run, capture=True)
        if r.returncode:
            print(r.stderr, file=sys.stderr)
            return 1
    # Initial add+commit if there's nothing yet
    if not dry_run:
        # Only commit if the working tree has changes
        st = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True)
        if st.stdout.strip():
            subprocess.run(["git", "add", "."], cwd=root, check=False)
            subprocess.run(["git", "commit", "-m", "chrono-palace-memory: initial sync"],
                           cwd=root, check=False)
    print(f"Initialized memory store as git repo at {root}")
    print("Next: add a private remote, e.g.")
    print("  git -C ~/.memory remote add origin git@github.com:you/memory.git")
    print("  git -C ~/.memory push -u origin main")
    return 0


def cmd_status(root: pathlib.Path) -> int:
    if not _is_repo(root):
        print(f"{root} is not a git repo (run with --init first).")
        return 2
    subprocess.run(["git", "status", "-sb"], cwd=root)
    print()
    print("Last 5 commits:")
    subprocess.run(["git", "log", "--oneline", "-5"], cwd=root)
    return 0


def cmd_sync(root: pathlib.Path, dry_run: bool) -> int:
    if not _git_available():
        print("error: git not found in PATH", file=sys.stderr)
        return 2
    if not _is_repo(root):
        print(f"{root} is not a git repo. Run `tools/sync.py --init` first.", file=sys.stderr)
        return 2

    # Check there's a remote
    rem = subprocess.run(["git", "remote"], cwd=root, capture_output=True, text=True)
    if not rem.stdout.strip():
        print("warning: no git remote configured.", file=sys.stderr)
        print("Configure one with:", file=sys.stderr)
        print("  git -C ~/.memory remote add origin <private-url>", file=sys.stderr)
        return 2

    print("Acquiring memory-store lock...")
    try:
        with lib.file_lock(root, timeout=30.0):
            print("Pulling (rebase)...")
            r = _run(["git", "pull", "--rebase"], root, dry_run)
            if r.returncode:
                print("pull failed — resolve conflicts manually and re-run sync.", file=sys.stderr)
                return 1

            # Are there local changes to commit?
            st = subprocess.run(
                ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
            )
            if st.stdout.strip():
                print(f"Committing {len(st.stdout.splitlines())} local change(s)...")
                _run(["git", "add", "."], root, dry_run)
                _run(["git", "commit", "-m", "chrono-palace-memory: sync"], root, dry_run)
            else:
                print("Nothing to commit locally.")

            print("Pushing...")
            r = _run(["git", "push"], root, dry_run)
            if r.returncode:
                print("push failed.", file=sys.stderr)
                return 1
    except lib.LockTimeout as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print("Sync complete.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--init", action="store_true",
                   help="one-time setup: make ~/.memory a git repo with sensible gitignore")
    g.add_argument("--status", action="store_true",
                   help="show local vs remote status")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.init:
        return cmd_init(args.root, args.dry_run)
    if args.status:
        return cmd_status(args.root)
    return cmd_sync(args.root, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
