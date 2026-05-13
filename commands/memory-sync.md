---
description: Sync ~/.memory across machines via a private git remote
argument-hint: "[--init | --status | --dry-run]"
---

Run `~/.claude/skills/chrono-palace-memory/tools/sync.py $ARGUMENTS`.

First-time setup (if the user hasn't synced before):
1. `tools/sync.py --init` — initializes `~/.memory` as a git repo with appropriate gitignore (lock files, caches, audit logs stay local).
2. Tell the user to add a **private** remote:
   ```
   git -C ~/.memory remote add origin <private-url>
   git -C ~/.memory push -u origin main
   ```
   Stress that **the remote must be private** — memory contains conversations and user identity.

Regular use:
- `tools/sync.py` — pull (rebase), commit local changes, push. Holds the memory-store lock during sync so no other tool can write concurrently.
- `tools/sync.py --status` — show what's local vs remote without making changes.

Conflict handling:
- The sync uses rebase, so merge conflicts surface as standard git conflicts in the user's `~/.memory/`.
- If a conflict occurs in a memory file (likely two machines wrote the same daily/session), guide the user through:
  1. `git -C ~/.memory status` to see conflicted files
  2. Open and resolve preserving both perspectives (use the supersede chain pattern)
  3. `git -C ~/.memory add <file> && git -C ~/.memory rebase --continue`
  4. Re-run `memory-sync`

**Privacy reminder**: never push to a public repo.
