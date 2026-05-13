---
description: Build / refresh the neural-embedding cache that powers semantic search
argument-hint: "[--full | --stats | --check]"
---

Run `~/.claude/skills/chrono-palace-memory/tools/embed.py $ARGUMENTS`.

First-time setup:
1. `python3 tools/embed.py --check` — verify `sentence-transformers` is installed.
2. If not, advise the user: `pip install -r requirements-optional.txt`
3. Once installed, `python3 tools/embed.py` builds the cache (downloads ~120MB model on first run; subsequent runs are incremental based on file mtime).

Whenever the user makes a lot of memory edits, suggest re-running `embed.py` (no flag = incremental).

`search.py` will automatically use the neural backend once the cache exists. Without the cache or library, search.py silently falls back to TF-IDF — no breakage.

**Privacy reminder**: all embedding is local. The user's memory content never leaves the machine.
