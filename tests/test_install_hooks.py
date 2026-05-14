#!/usr/bin/env python3
"""Regression tests for hook installer config merging."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTALLER_PATH = REPO_ROOT / "tools" / "install-hooks.py"


def load_installer_module():
    spec = importlib.util.spec_from_file_location("install_hooks", INSTALLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load install-hooks.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["install_hooks"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    installer = load_installer_module()
    failures: list[str] = []

    command = "python3 /repo/tools/memory-hook.py"
    config = {"hooks": {"PostToolUse": [{"matcher": "Other", "hooks": []}]}}
    merged = installer.merge_hooks_config(config, command)
    merged = installer.merge_hooks_config(merged, command)

    hooks = merged.get("hooks", {})
    for event in ("SessionStart", "PostToolUse", "Stop"):
        groups = hooks.get(event)
        if not groups:
            failures.append(f"{event} hook group missing")
            continue
        commands = [
            hook.get("command")
            for group in groups
            for hook in group.get("hooks", [])
            if hook.get("type") == "command"
        ]
        if commands.count(command) != 1:
            failures.append(f"{event} should contain exactly one memory hook command, got {commands}")

    post_groups = hooks.get("PostToolUse", [])
    if not any(group.get("matcher") == "Edit|Write|Bash" for group in post_groups):
        failures.append("PostToolUse matcher should be Edit|Write|Bash")

    if not any(group.get("matcher") == "Other" for group in post_groups):
        failures.append("installer should preserve existing PostToolUse hook groups")

    # Ensure the result is plain JSON serializable for Claude settings.json and Codex hooks.json.
    try:
        json.dumps(merged)
    except TypeError as exc:
        failures.append(f"merged config is not JSON serializable: {exc}")

    # Prefix-based dedup: re-running the installer with a *different*
    # --threshold-lines must replace the existing memory-hook entry, not append
    # a second one. Otherwise both old and new hooks fire on every event.
    cmd_v1 = "python3 /repo/tools/memory-hook.py --threshold-lines 120"
    cmd_v2 = "python3 /repo/tools/memory-hook.py --threshold-lines 200"
    rerun = installer.merge_hooks_config({}, cmd_v1)
    rerun = installer.merge_hooks_config(rerun, cmd_v2)
    for event in ("SessionStart", "PostToolUse", "Stop"):
        groups = rerun.get("hooks", {}).get(event, [])
        memory_hook_cmds = [
            h.get("command")
            for g in groups
            for h in g.get("hooks", [])
            if isinstance(h, dict)
            and isinstance(h.get("command"), str)
            and "memory-hook.py" in h.get("command", "")
        ]
        if memory_hook_cmds != [cmd_v2]:
            failures.append(
                f"{event}: rerun should replace memory-hook command, "
                f"got {memory_hook_cmds!r}"
            )

    # Pre-existing duplicate hook entries (from a buggy older installer) should
    # be collapsed to one entry on the next run.
    polluted = {
        "hooks": {
            "Stop": [
                {"hooks": [
                    {"type": "command", "command": "python3 /old/tools/memory-hook.py --threshold-lines 80"},
                    {"type": "command", "command": "python3 /old/tools/memory-hook.py --threshold-lines 90"},
                ]},
            ],
        },
    }
    cleaned = installer.merge_hooks_config(polluted, cmd_v2)
    stop_groups = cleaned["hooks"]["Stop"]
    memory_hook_cmds = [
        h.get("command")
        for g in stop_groups
        for h in g.get("hooks", [])
        if isinstance(h, dict)
        and isinstance(h.get("command"), str)
        and "memory-hook.py" in h.get("command", "")
    ]
    if memory_hook_cmds != [cmd_v2]:
        failures.append(
            f"polluted config should collapse to single hook, got {memory_hook_cmds!r}"
        )

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("PASS - hook installer merges Claude/Codex hook config idempotently")
    return 0


if __name__ == "__main__":
    sys.exit(main())
