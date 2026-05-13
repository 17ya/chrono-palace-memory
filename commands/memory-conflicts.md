---
description: Detect potential conflicts before writing a new memory
argument-hint: "--topic <slug> | --against <file>"
---

Run `~/.claude/skills/chrono-palace-memory/tools/find-conflicts.py $ARGUMENTS`.

For each candidate the tool reports:
1. Read the candidate file with the Read tool.
2. Classify the relationship: duplicate (merge), supersede (new fact replaces old), refinement (extend old), or false-positive (unrelated despite name collision).
3. **Never silently overwrite.** Use the `superseded` / `supersedes` chain per references/lifecycle.md.

If exit code is 0, just say "no conflict candidates — safe to write."
