---
description: Report (or apply) TTL expiration for session memories
argument-hint: "[--apply]"
---

Run `~/.claude/skills/chrono-palace-memory/tools/expire-sessions.py $ARGUMENTS`.

Default mode is dry-run — it only reports.

If there are blocked sessions (expired but no `promoted_to:`), do NOT run with `--apply`. Instead:
1. List the blocked session paths.
2. For each, run `aggregate-daily.py` for that session's date if a daily for that date doesn't exist yet, or manually promote the facts.
3. Update the session's `promoted_to:` field.
4. Re-run expire-sessions; only after all blocks are clear should you suggest `--apply`.

Never delete expired sessions outright — the script archives them under `sessions/_expired/` for audit.
