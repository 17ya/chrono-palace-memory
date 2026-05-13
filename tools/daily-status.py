#!/usr/bin/env python3
"""Cheap-and-cheerful status report for the memory store.

Designed to be called by SessionStart hooks or cron — must be FAST
(milliseconds) and have ZERO side effects.

Reports:
- today's date
- yesterday's daily: written? promoted_to non-empty?
- today's session count
- count of sessions older than today with no `promoted_to`
- count of sessions past `expires_at`
- whether MEMORY.md exists

Output modes:
  --format text  (default; meant for hook stdout injection)
  --format json  (machine-readable)

Exit codes:
  0  — everything's fine OR there are reminders but nothing broken
  1  — actionable issue (expired sessions blocked, missing yesterday daily)

The exit code can be ignored by hooks (which usually just inject stdout).
It's there for cron / scripts that want to gate on "needs attention".
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import timedelta

import _lib as lib


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    root: pathlib.Path = args.root
    today = lib.today()
    yesterday = today - timedelta(days=1)

    state: dict[str, object] = {
        "root": str(root),
        "today": today.isoformat(),
        "memory_md_exists": (root / "MEMORY.md").exists(),
        "yesterday": {
            "date": yesterday.isoformat(),
            "daily_exists": False,
            "promoted": False,
            "session_count": 0,
            "unpromoted_sessions": [],
        },
        "today_sessions": 0,
        "expired_blocked": [],
        "issues": [],
        "reminders": [],
    }

    # Yesterday daily
    y_daily = root / "daily" / f"{yesterday.year:04d}" / f"{yesterday.month:02d}" / f"{yesterday.day:02d}.md"
    if y_daily.exists():
        state["yesterday"]["daily_exists"] = True  # type: ignore[index]
        mf = lib.load(y_daily)
        promoted = mf.frontmatter.get("promoted_to") or []
        state["yesterday"]["promoted"] = bool(promoted)  # type: ignore[index]
        if not promoted:
            state["reminders"].append(  # type: ignore[union-attr]
                f"daily/{yesterday.isoformat()} exists but `promoted_to:` is empty"
            )

    # Yesterday sessions
    y_sess_dir = root / "sessions" / f"{yesterday.year:04d}" / f"{yesterday.month:02d}" / f"{yesterday.day:02d}"
    if y_sess_dir.exists():
        sessions = sorted(y_sess_dir.glob("session_*.md"))
        state["yesterday"]["session_count"] = len(sessions)  # type: ignore[index]
        if sessions and not state["yesterday"]["daily_exists"]:  # type: ignore[index]
            state["issues"].append(  # type: ignore[union-attr]
                f"{len(sessions)} session(s) from {yesterday.isoformat()} but no daily — run aggregate-daily"
            )
        for p in sessions:
            mf = lib.load(p)
            if not (mf.frontmatter.get("promoted_to") or []):
                state["yesterday"]["unpromoted_sessions"].append(mf.rel_path)  # type: ignore[index]

    # Today's sessions (just count)
    t_sess_dir = root / "sessions" / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.day:02d}"
    if t_sess_dir.exists():
        state["today_sessions"] = len(list(t_sess_dir.glob("session_*.md")))

    # Expired-but-blocked sessions
    for mf in lib.walk(root):
        if mf.type != "session":
            continue
        if mf.expires_at and mf.expires_at <= today:
            promoted = mf.frontmatter.get("promoted_to") or []
            if not promoted:
                state["expired_blocked"].append(mf.rel_path)  # type: ignore[union-attr]
    if state["expired_blocked"]:
        state["issues"].append(  # type: ignore[union-attr]
            f"{len(state['expired_blocked'])} session(s) past expires_at but not promoted"
        )

    if not state["memory_md_exists"]:
        state["issues"].append("MEMORY.md is missing — the index is mandatory")  # type: ignore[union-attr]

    if args.format == "json":
        print(json.dumps(state, indent=2, ensure_ascii=False))
    else:
        lines = []
        lines.append(f"chrono-palace memory — {today}")
        lines.append(f"  MEMORY.md exists: {state['memory_md_exists']}")
        y = state["yesterday"]
        lines.append(
            f"  Yesterday ({y['date']}): daily={'yes' if y['daily_exists'] else 'NO'}, "  # type: ignore[index]
            f"sessions={y['session_count']}, promoted={'yes' if y['promoted'] else 'no'}"  # type: ignore[index]
        )
        lines.append(f"  Today sessions: {state['today_sessions']}")
        if state["issues"]:
            lines.append("")
            lines.append("ISSUES (action required):")
            for x in state["issues"]:  # type: ignore[union-attr]
                lines.append(f"  - {x}")
        if state["reminders"]:
            lines.append("")
            lines.append("Reminders:")
            for x in state["reminders"]:  # type: ignore[union-attr]
                lines.append(f"  - {x}")
        if state["expired_blocked"]:
            lines.append("")
            lines.append("Expired but unpromoted (must promote before --apply):")
            for p in state["expired_blocked"]:  # type: ignore[union-attr]
                lines.append(f"  - {p}")
        print("\n".join(lines))

    return 1 if state["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
