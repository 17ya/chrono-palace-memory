---
description: Redact memories on user request (soft delete with audit trail)
argument-hint: "--topic <term> | --name <slug> | --path <relpath>"
---

Run `~/.claude/skills/chrono-palace-memory/tools/forget.py $ARGUMENTS` (without `--apply` first to preview).

Steps:
1. **Show what would be redacted** (dry-run output). Read the user's selection carefully — `--topic` is fuzzy and may match more than expected.
2. **Confirm with the user** which exact files to redact. Never proceed on assumption.
3. **Ask for a reason** for the audit log — "user requested in conversation YYYY-MM-DD" is acceptable; more specific is better.
4. Run again with `--apply --reason "<reason>"`.
5. After redaction:
   - Update MEMORY.md to remove the entries from active indexes
   - Update `keyword_index.md` / `entity_index.md` if they reference the redacted files
   - Tell the user the file path is preserved but content is blank, and the audit log is at `~/.memory/.audit-redactions.log`

**Never use `rm`** on a memory file unless the user explicitly asks for *physical* deletion (rare; usually for legal compliance). In that case still ask twice.

Redacted files persist as audit trail. Search excludes them automatically.
