#!/usr/bin/env python3
"""Test that file_lock + atomic_write actually prevent concurrent-write damage.

Spawns a child process that holds the lock for 2 seconds. The parent then
tries to acquire the same lock with a 0.5s timeout — it should LockTimeout.

Then both processes write to the same target file under the lock; the
final content must be one of the two complete writes (no interleaving).

Usage:
  python3 tests/test_concurrency.py

Exit 0 on success, 1 on failure.
"""

from __future__ import annotations

import multiprocessing
import pathlib
import sys
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import _lib as lib  # noqa: E402


def _hold_lock(root_str: str, duration: float, target_path: str, payload: str) -> None:
    root = pathlib.Path(root_str)
    with lib.file_lock(root, timeout=5.0):
        # Mid-write delay simulates a slow write
        lib.atomic_write(pathlib.Path(target_path), payload)
        time.sleep(duration)


def main() -> int:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        target = root / "shared.txt"

        # 1. LockTimeout
        ctx = multiprocessing.get_context("spawn")
        p = ctx.Process(target=_hold_lock, args=(str(root), 2.0, str(target), "child-payload"))
        p.start()
        time.sleep(0.3)  # let child grab the lock
        try:
            with lib.file_lock(root, timeout=0.5):
                failures.append("parent acquired lock while child held it (should have timed out)")
        except lib.LockTimeout:
            pass  # expected
        p.join()

        # 2. After child finishes, parent should be able to write atomically
        try:
            with lib.file_lock(root, timeout=2.0):
                lib.atomic_write(target, "parent-payload")
        except lib.LockTimeout as e:
            failures.append(f"parent could not acquire lock after child exit: {e}")

        # 3. Final content is one complete write
        final = target.read_text(encoding="utf-8")
        if final not in ("child-payload", "parent-payload"):
            failures.append(f"file has interleaved content: {final!r}")
        if final != "parent-payload":
            failures.append(f"parent's later write didn't win: {final!r}")

        # 4. atomic_write leaves no .tmp files behind
        leftovers = list(root.glob(".tmp-*"))
        if leftovers:
            failures.append(f"atomic_write left temp files: {leftovers}")

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — file_lock blocks contention and atomic_write doesn't tear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
