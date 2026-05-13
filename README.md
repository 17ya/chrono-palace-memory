# chrono-palace-memory

A long-term memory system for AI coding agents (designed for Claude Code, applicable to any agent that can read/write local files).

Replaces flat auto-memory with a **five-layer cognitive architecture**: Chrono / Semantic / Entity / Palace / Reflection. Each layer has a single job — no mixing.

> Skill 主入口 [SKILL.md](SKILL.md) 使用中文撰写。Memory content 用户用什么语言交流就用什么语言写入；frontmatter 字段名保持英文。

---

## Why

Most agent memory systems are flat: one folder of markdown files, optionally an index. They work until they don't:

- "What did we decide about X last month?" → no time-based retrieval
- "User said A, but now they say B" → silent overwrite, history lost
- "Which project does this preference belong to?" → no entity grouping
- "Has the user mentioned this 3 times or 30?" → no evidence count
- "Am I about to recommend something stale?" → no recency vs. stability distinction

**Chrono-Palace** fixes these by splitting memory into five interlinked but independent layers.

## The five layers

```
┌──────────────────────────────────────────────────┐
│ Reflection   patterns the agent has abstracted   │
├──────────────────────────────────────────────────┤
│ Palace       long-term topic rooms (cognitive)   │
├──────────────────────────────────────────────────┤
│ Entity       stable objects (user/project/...)   │
├──────────────────────────────────────────────────┤
│ Semantic     keyword / vector index (search)     │
├──────────────────────────────────────────────────┤
│ Chrono       year/month/day/session (evidence)   │
└──────────────────────────────────────────────────┘
```

- **Chrono** stores raw evidence. 30-day TTL on sessions.
- **Semantic** lets you find things by keyword without scanning the tree.
- **Entity** holds *what is currently known* about each object.
- **Palace** is the agent's cognitive map — long-term rooms by topic.
- **Reflection** is the agent's meta-learning, gated by ≥3 evidence.

Upper layers must always link back to evidence in lower layers.

## Repository layout

```
.
├── SKILL.md                      # Main skill entry (Claude reads this first)
├── README.md                     # You are here
├── LICENSE                       # MIT
├── CONTRIBUTING.md
├── .gitignore
├── requirements-optional.txt     # sentence-transformers (only for neural search)
├── references/                   # Looked up by the agent during operations
│   ├── retrieval.md              #  - retrieval (4-route + scoring + neural/tfidf)
│   ├── lifecycle.md              #  - TTL, decay, supersede chains
│   ├── writing-rules.md          #  - 5-step write checklist
│   └── tools.md                  #  - tool reference manual
├── templates/                    # Frontmatter scaffolds
│   ├── MEMORY.md  session.md  daily.md
│   ├── monthly.md yearly.md
│   ├── palace-room.md entity.md reflection.md
├── tools/                        # stdlib-only Python helpers (neural is optional)
│   ├── _lib.py                   #   frontmatter + tokenizer + TF-IDF primitives
│   ├── validate.py search.py daily-status.py
│   ├── aggregate-daily.py aggregate-monthly.py aggregate-yearly.py
│   ├── expire-sessions.py find-conflicts.py forget.py
│   ├── memory-hook.py install-hooks.py
│   ├── embed.py                  #   neural-embedding cache (optional)
│   ├── migrate.py                #   schema migration runner
│   └── migrations/               #   dated, idempotent migration scripts
├── commands/                     # Claude Code slash commands
│   └── memory-*.md
├── tests/
│   ├── fixtures/{healthy,broken}/
│   ├── test_validate.sh
│   └── test_tfidf.py
└── .github/workflows/validate.yml
```

**Actual memory data lives in `~/.memory/`**, never inside this repo. `~/.memory/` is gitignored by design.

## Install

There is no install script. Hand this repository to Claude (or your agent of choice) and say *"please install this skill"*. The agent will read this README and perform the steps below.

Restart Claude Code. The skill becomes discoverable in any session.

### Uninstall

```bash
# Remove the symlink (or the cloned skill folder)
rm -rf ~/.claude/skills/chrono-palace-memory

# Memory data in ~/.memory/ is untouched. Delete it explicitly if you want to wipe history.
```

### Optional: sync across machines

Memory stays on your machine by default. To share state across laptops / desktops, make `~/.memory/` a private git repo:

```bash
python3 tools/sync.py --init
git -C ~/.memory remote add origin <private-url>     # GitHub private repo / self-hosted git
git -C ~/.memory push -u origin main

# then on every machine, just:
python3 tools/sync.py     # pull-rebase + commit + push, holds the write lock
```

The init step writes a `.gitignore` excluding machine-local state (locks, embedding cache, audit logs). Conflict resolution uses the same supersede-chain pattern as the rest of the skill. See [references/sync.md](references/sync.md).

**Use a private remote.** Memory contains your conversations and identity.

### Optional: neural-embedding search

By default, semantic search uses a stdlib TF-IDF cosine — works fine for small / medium stores. For better recall on large stores or fuzzy queries, install neural embeddings:

```bash
pip install -r requirements-optional.txt
python3 tools/embed.py            # downloads ~120MB model on first run; subsequent runs are incremental
```

Once the cache exists, `tools/search.py` automatically uses neural cosine. Force a backend with `--backend {neural,tfidf}`. Privacy: all embedding runs locally — memory content never leaves the machine.

### Optional: lifecycle hooks

Ask your agent to install lifecycle hooks after it installs this skill:

```bash
python3 tools/install-hooks.py --target both
```

The installer merges existing config instead of replacing it:

- Claude Code: `~/.claude/settings.json`
- Codex: `~/.codex/hooks.json`

Installed hooks call `tools/memory-hook.py`:

- `SessionStart` injects `~/.memory/MEMORY.md` as context.
- `PostToolUse` marks the current turn dirty only after `Edit`, `Write`, or `Bash`.
- `Stop` asks the agent to consider writing a session memory only when the turn is dirty or the transcript crosses the line threshold.

Tune the threshold:

```bash
python3 tools/install-hooks.py --target both --threshold-lines 160
```

Hook output is JSON, so it works with Claude Code and Codex lifecycle-hook parsers. If your Codex build disables hooks, enable Codex lifecycle hooks first, then rerun the installer.

### Optional: cron status

For headless / server installs, run nightly to flag unpromoted sessions:

```
# crontab -e
15 23 * * * python3 ~/.claude/skills/chrono-palace-memory/tools/daily-status.py >> ~/.memory/.status.log 2>&1
```

Cron status is read-only. Actually promoting / expiring still requires explicit `/memory-aggregate`, `/memory-expire --apply` etc.

## How it gets used

When Claude Code or Codex starts a session with hooks installed, the memory index is injected as context. As soon as the conversation involves memory operations (writing observations, recalling past decisions, etc.), the agent invokes the skill and follows the rules in [SKILL.md](SKILL.md). At `Stop`, the hook only interrupts when a memory writeback is likely useful.

The skill enforces:
- Every memory file has YAML frontmatter with `confidence`, `importance`, `evidence`, `status`, `created_at`
- Upper-layer memories must cite lower-layer evidence
- Conflicts use `superseded` chains, never silent overwrite
- Sessions expire in 30 days but their contents are promoted to daily before deletion
- `MEMORY.md` is an *index*, not a store
- Memory content uses the language the user converses in (frontmatter stays English)

## Use without Claude Code

The architecture is just markdown + frontmatter conventions. Any agent that can read/write local files can adopt it — the skill is platform-agnostic. Only the path `~/.claude/skills/` in the install steps is Claude Code specific.

## Contributing

Issues and PRs welcome. The schema is intentionally small — propose new frontmatter fields only with a concrete use case.

## License

MIT — see [LICENSE](LICENSE).
