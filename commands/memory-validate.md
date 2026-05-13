---
description: Validate the chrono-palace memory store (frontmatter, links, indexes)
---

Run `~/.claude/skills/chrono-palace-memory/tools/validate.py` and report the result.

- If exit code 0: just say "memory store is healthy" and show error/warning counts.
- If exit code 1: list every error, then propose specific fixes (do not auto-fix without confirmation — these are user data).
- If a warning recurs (e.g. dangling wikilinks), propose either fixing the dangling references or updating the skill schema.
