#!/usr/bin/env python3
"""Regression tests for memory lifecycle hook heuristics.

Usage:
  python3 tests/test_memory_hook.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "tools" / "memory-hook.py"
sys.path.insert(0, str(REPO_ROOT / "tools"))


def load_hook_module():
    spec = importlib.util.spec_from_file_location("memory_hook", HOOK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load memory-hook.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["memory_hook"] = module
    spec.loader.exec_module(module)
    return module


def write_transcript(path: pathlib.Path, line_count: int) -> None:
    path.write_text(
        "".join(json.dumps({"message": f"line {i}"}) + "\n" for i in range(line_count)),
        encoding="utf-8",
    )


def main() -> int:
    hook = load_hook_module()
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / "memory"
        transcript = pathlib.Path(tmp) / "transcript.jsonl"

        session = {
            "session_id": "abc123",
            "hook_event_name": "SessionStart",
            "transcript_path": str(transcript),
        }
        write_transcript(transcript, 10)
        out = hook.handle_event(session, root=root, threshold_lines=50)
        if "MEMORY.md" not in out.text:
            failures.append("SessionStart should inject MEMORY.md status text")

        stop = {
            "session_id": "abc123",
            "hook_event_name": "Stop",
            "transcript_path": str(transcript),
            "stop_hook_active": False,
        }
        out = hook.handle_event(stop, root=root, threshold_lines=50)
        if out.decision:
            failures.append("Stop should not block when no dirty tool ran and threshold was not crossed")

        post_tool = {
            "session_id": "abc123",
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "transcript_path": str(transcript),
        }
        out = hook.handle_event(post_tool, root=root, threshold_lines=50)
        if out.decision:
            failures.append("PostToolUse marker should not block")

        out = hook.handle_event(stop, root=root, threshold_lines=50)
        if out.decision != "block" or "Edit" not in out.reason:
            failures.append(f"Stop should block after Edit; got decision={out.decision!r} reason={out.reason!r}")

        active_stop = dict(stop, stop_hook_active=True)
        out = hook.handle_event(active_stop, root=root, threshold_lines=50)
        if out.decision:
            failures.append("Stop should not block recursively when stop_hook_active is true")

        # After the recursive guard clears state, the same transcript should not block again.
        out = hook.handle_event(stop, root=root, threshold_lines=50)
        if out.decision:
            failures.append("Stop should not keep blocking after the recursive Stop guard cleared state")

        # Crossing the transcript threshold should block once, even without dirty tools.
        write_transcript(transcript, 51)
        out = hook.handle_event(stop, root=root, threshold_lines=50)
        if out.decision != "block" or "threshold" not in out.reason.lower():
            failures.append(f"Stop should block after threshold crossing; got {out.decision!r} {out.reason!r}")

        out = hook.handle_event(active_stop, root=root, threshold_lines=50)
        if out.decision:
            failures.append("Threshold-triggered continuation should also be recursion-safe")

    # Threshold clamp: out-of-range values must be coerced into a sane range
    # so a typo in the installer command doesn't disable the writeback prompt.
    if hook._clamp_threshold(0) != hook.MIN_THRESHOLD_LINES:
        failures.append("clamp(0) should return MIN_THRESHOLD_LINES")
    if hook._clamp_threshold(-1) != hook.MIN_THRESHOLD_LINES:
        failures.append("clamp(-1) should return MIN_THRESHOLD_LINES")
    if hook._clamp_threshold(999_999) != hook.MAX_THRESHOLD_LINES:
        failures.append("clamp(999_999) should return MAX_THRESHOLD_LINES")
    if hook._clamp_threshold(120) != 120:
        failures.append("clamp(120) should pass through unchanged")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("PASS - memory hook heuristics are dirty/threshold gated and recursion-safe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
