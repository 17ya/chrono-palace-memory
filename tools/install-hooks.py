#!/usr/bin/env python3
"""Install Chrono-Palace lifecycle hooks for Claude Code and Codex."""

from __future__ import annotations

import argparse
import json
import pathlib
import shlex
import sys
from typing import Any


EVENT_GROUPS = {
    "SessionStart": {"hooks": [{"type": "command"}]},
    "PostToolUse": {"matcher": "Edit|Write|Bash", "hooks": [{"type": "command"}]},
    "Stop": {"hooks": [{"type": "command"}]},
}


def merge_hooks_config(config: dict[str, Any], command: str) -> dict[str, Any]:
    merged = dict(config)
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        merged["hooks"] = hooks

    for event, template in EVENT_GROUPS.items():
        event_groups = hooks.setdefault(event, [])
        if not isinstance(event_groups, list):
            event_groups = []
            hooks[event] = event_groups
        _ensure_command_group(event_groups, template, command)

    return merged


def install_claude(settings_path: pathlib.Path, command: str) -> None:
    config = _read_json(settings_path)
    merged = merge_hooks_config(config, command)
    _write_json(settings_path, merged)


def install_codex(hooks_path: pathlib.Path, command: str) -> None:
    config = _read_json(hooks_path)
    merged = merge_hooks_config(config, command)
    _write_json(hooks_path, merged)


_HOOK_MARKER = "memory-hook.py"


def _is_memory_hook(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    cmd = entry.get("command")
    return isinstance(cmd, str) and _HOOK_MARKER in cmd


def _ensure_command_group(groups: list[Any], template: dict[str, Any], command: str) -> None:
    """Insert (or replace) the chrono-palace hook for this event group.

    Re-running the installer with a different `--threshold-lines` (or after the
    repo path has moved) must update the existing entry in place rather than
    appending a duplicate. We dedup on the `memory-hook.py` substring instead
    of full string equality so the command can change while the hook stays
    unique.
    """
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_hooks = group.get("hooks")
        if not isinstance(group_hooks, list):
            continue
        replaced = False
        for idx, hook in enumerate(group_hooks):
            if _is_memory_hook(hook):
                group_hooks[idx] = {"type": "command", "command": command}
                replaced = True
        if replaced:
            # Drop any leftover duplicates from prior buggy installs.
            seen = False
            kept: list[Any] = []
            for h in group_hooks:
                if _is_memory_hook(h):
                    if seen:
                        continue
                    seen = True
                kept.append(h)
            group["hooks"] = kept
            return

    group = {k: v for k, v in template.items() if k != "hooks"}
    group["hooks"] = [{"type": "command", "command": command}]
    groups.append(group)


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cannot parse JSON config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"config root must be a JSON object: {path}")
    return data


def _write_json(path: pathlib.Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _default_command(repo_root: pathlib.Path, threshold_lines: int) -> str:
    hook = repo_root / "tools" / "memory-hook.py"
    return f"python3 {shlex.quote(str(hook))} --threshold-lines {threshold_lines}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", choices=["claude", "codex", "both"], default="both")
    ap.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parent.parent,
        help="Path to the chrono-palace-memory repository or installed skill directory.",
    )
    ap.add_argument("--threshold-lines", type=int, default=120)
    ap.add_argument(
        "--claude-settings",
        type=pathlib.Path,
        default=pathlib.Path.home() / ".claude" / "settings.json",
    )
    ap.add_argument(
        "--codex-hooks",
        type=pathlib.Path,
        default=pathlib.Path.home() / ".codex" / "hooks.json",
    )
    args = ap.parse_args()

    command = _default_command(args.repo_root.expanduser().resolve(), args.threshold_lines)

    installed: list[str] = []
    skipped: list[tuple[str, str]] = []

    if args.target in {"claude", "both"}:
        claude_settings = args.claude_settings.expanduser()
        # Claude Code dir is created by the CLI on first run; install always
        # writes settings.json (creating ~/.claude/ if necessary) because that
        # is the documented happy path.
        install_claude(claude_settings, command)
        installed.append(str(claude_settings))

    if args.target in {"codex", "both"}:
        codex_hooks = args.codex_hooks.expanduser()
        codex_dir = codex_hooks.parent
        if args.target == "both" and not codex_dir.exists():
            # Don't fabricate a Codex install directory just because the user
            # accepted the `both` default. If they explicitly pass --target codex,
            # honor it and create the directory.
            skipped.append((str(codex_hooks), "Codex directory not found"))
        else:
            install_codex(codex_hooks, command)
            installed.append(str(codex_hooks))

    print("Installed chrono-palace-memory hooks:")
    for path in installed:
        print(f"  - {path}")
    for path, reason in skipped:
        print(f"  - skipped {path} ({reason}; pass --target codex to force)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
