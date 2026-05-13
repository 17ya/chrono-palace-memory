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


def _ensure_command_group(groups: list[Any], template: dict[str, Any], command: str) -> None:
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_hooks = group.get("hooks")
        if not isinstance(group_hooks, list):
            continue
        if any(isinstance(h, dict) and h.get("command") == command for h in group_hooks):
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
    if args.target in {"claude", "both"}:
        install_claude(args.claude_settings.expanduser(), command)
        installed.append(str(args.claude_settings.expanduser()))
    if args.target in {"codex", "both"}:
        install_codex(args.codex_hooks.expanduser(), command)
        installed.append(str(args.codex_hooks.expanduser()))

    print("Installed chrono-palace-memory hooks:")
    for path in installed:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
