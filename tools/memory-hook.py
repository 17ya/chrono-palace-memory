#!/usr/bin/env python3
"""Lifecycle hook helper for chrono-palace-memory.

This script is intentionally platform-neutral. Claude Code and Codex can both
feed hook-event JSON on stdin; the script records cheap per-session state and
uses Stop hooks to nudge the agent only when memory writeback is likely useful.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any

import _lib as lib


DEFAULT_THRESHOLD_LINES = 120
MIN_THRESHOLD_LINES = 40
MAX_THRESHOLD_LINES = 1000
DIRTY_TOOLS = {"Edit", "Write", "Bash"}


def _clamp_threshold(value: int) -> int:
    """Keep --threshold-lines in a sane range.

    Below MIN_THRESHOLD_LINES the Stop hook would block almost every turn;
    above MAX_THRESHOLD_LINES it would never fire. Both effectively disable
    the writeback prompt, so we clamp instead of erroring — installer
    invocations stay forgiving.
    """
    if value < MIN_THRESHOLD_LINES:
        return MIN_THRESHOLD_LINES
    if value > MAX_THRESHOLD_LINES:
        return MAX_THRESHOLD_LINES
    return value


@dataclass
class HookOutput:
    text: str = ""
    decision: str | None = None
    reason: str = ""

    def emit(self) -> None:
        if self.decision:
            print(
                json.dumps(
                    {
                        "decision": self.decision,
                        "reason": self.reason,
                    },
                    ensure_ascii=False,
                )
            )
        elif self.text:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": self.text,
                        }
                    },
                    ensure_ascii=False,
                )
            )


def handle_event(event: dict[str, Any], root: pathlib.Path, threshold_lines: int) -> HookOutput:
    event_name = str(event.get("hook_event_name") or event.get("event") or "").strip()
    if not event_name:
        event_name = _event_from_args_fallback(event)

    session_id = _safe_session_id(str(event.get("session_id") or "default"))
    transcript = _transcript_path(event)

    if event_name == "SessionStart":
        state = _load_state(root, session_id)
        state["last_line_count"] = _count_lines(transcript)
        _save_state(root, session_id, state)
        return HookOutput(text=_session_start_text(root))

    if event_name == "PostToolUse":
        tool = str(event.get("tool_name") or event.get("tool") or "")
        if tool in DIRTY_TOOLS:
            state = _load_state(root, session_id)
            dirty_tools = list(state.get("dirty_tools") or [])
            if tool not in dirty_tools:
                dirty_tools.append(tool)
            state["dirty"] = True
            state["dirty_tools"] = dirty_tools
            state["last_line_count"] = _count_lines(transcript)
            _save_state(root, session_id, state)
        return HookOutput()

    if event_name == "Stop":
        state = _load_state(root, session_id)
        current_lines = _count_lines(transcript)
        previous_lines = _coerce_int(state.get("last_line_count"))

        if bool(event.get("stop_hook_active")):
            _save_state(root, session_id, {"last_line_count": current_lines})
            return HookOutput()

        if previous_lines is None:
            state["last_line_count"] = current_lines
            _save_state(root, session_id, state)
            return HookOutput()

        dirty = bool(state.get("dirty"))
        crossed_threshold = previous_lines < threshold_lines <= current_lines
        if dirty or crossed_threshold:
            reason_parts: list[str] = []
            if dirty:
                tools = ", ".join(str(x) for x in state.get("dirty_tools") or [])
                reason_parts.append(f"dirty tool used this turn: {tools or 'unknown'}")
            if crossed_threshold:
                reason_parts.append(
                    f"transcript threshold crossed: {previous_lines} -> {current_lines} lines"
                )
            state["last_line_count"] = current_lines
            _save_state(root, session_id, state)
            return HookOutput(
                decision="block",
                reason=(
                    "Chrono-Palace memory check required before final response: "
                    + "; ".join(reason_parts)
                    + ". If durable facts, decisions, preferences, or project state were learned, "
                    "write a session memory under ~/.memory and update MEMORY.md; otherwise state that "
                    "nothing durable should be written, then finish."
                ),
            )

        state["last_line_count"] = current_lines
        _save_state(root, session_id, state)
        return HookOutput()

    return HookOutput()


def _session_start_text(root: pathlib.Path) -> str:
    memory_md = root / "MEMORY.md"
    if memory_md.exists():
        try:
            text = memory_md.read_text(encoding="utf-8")
        except OSError as exc:
            return f"chrono-palace memory: could not read MEMORY.md: {exc}"
        return (
            "chrono-palace memory index loaded from ~/.memory/MEMORY.md.\n"
            "Use it only when relevant; write session memory at Stop only after the hook asks.\n\n"
            + text
        )
    return (
        "chrono-palace memory: ~/.memory/MEMORY.md is missing. "
        "Initialize the memory store before writing memories."
    )


def _event_from_args_fallback(event: dict[str, Any]) -> str:
    # Some runtimes may pass lower-case event names through wrapper scripts.
    value = str(event.get("event_name") or "").strip().lower()
    mapping = {
        "session-start": "SessionStart",
        "sessionstart": "SessionStart",
        "post-tool-use": "PostToolUse",
        "posttooluse": "PostToolUse",
        "stop": "Stop",
    }
    return mapping.get(value, "")


def _transcript_path(event: dict[str, Any]) -> pathlib.Path | None:
    raw = event.get("transcript_path")
    if not isinstance(raw, str) or not raw:
        return None
    return pathlib.Path(raw).expanduser()


def _count_lines(path: pathlib.Path | None) -> int:
    if path is None or not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fp:
            return sum(1 for _ in fp)
    except OSError:
        return 0


def _state_path(root: pathlib.Path, session_id: str) -> pathlib.Path:
    return root / ".hooks" / f"{session_id}.json"


def _load_state(root: pathlib.Path, session_id: str) -> dict[str, Any]:
    path = _state_path(root, session_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(root: pathlib.Path, session_id: str, state: dict[str, Any]) -> None:
    path = _state_path(root, session_id)
    with lib.file_lock(root, timeout=2.0):
        lib.atomic_write(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def _safe_session_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "default"


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--threshold-lines", type=int, default=DEFAULT_THRESHOLD_LINES)
    args = ap.parse_args()

    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        event = {}
    threshold = _clamp_threshold(args.threshold_lines)
    output = handle_event(event, root=args.root, threshold_lines=threshold)
    output.emit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
