---
description: Quick status of the memory store (yesterday's daily, unpromoted sessions, expired blocks)
---

Run `~/.claude/skills/chrono-palace-memory/tools/daily-status.py` and present the output.

If there are ISSUES (exit code 1):
1. Yesterday's sessions without a daily → run `/memory-aggregate <yesterday-date>`
2. Expired sessions blocked → for each one, ensure facts are promoted to daily/palace/entity first, then propose `/memory-expire --apply`
3. MEMORY.md missing → copy `templates/MEMORY.md` to `~/.memory/MEMORY.md` (after confirming with the user)

If only reminders (exit code 0), mention them but don't block.

This command is also suitable for SessionStart hooks (see README).
