---
description: Apply pending schema migrations to ~/.memory
argument-hint: "[--list | --only <slug> | --apply]"
---

Run `~/.claude/skills/chrono-palace-memory/tools/migrate.py $ARGUMENTS`.

Workflow:
1. **First run with `--list`** to show what's applied vs pending.
2. **Then run without flags** for a dry-run preview.
3. **Review the diff** the dry-run reports — migrations touch user data, never trust without inspection.
4. **Apply** with `--apply` when the diff looks right.
5. After apply, run `tools/validate.py` to confirm the store still validates against the new schema.

Migrations are recorded in `~/.memory/.migrations-applied` (one slug per line). Already-applied migrations are skipped.

If a migration crashes mid-flight: it will NOT be recorded as applied, and the partially-changed files remain. Re-running is safe because migrations are required to be idempotent — but inspect with `validate.py` first.
