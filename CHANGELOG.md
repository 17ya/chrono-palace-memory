# Changelog

All notable changes to chrono-palace-memory are documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-13

First public release.

### Added — architecture

- Five-layer cognitive memory model: Chrono / Semantic / Entity / Palace / Reflection
- Frontmatter schema with `name`, `type`, `confidence`, `importance`, `evidence`, `status`, `created_at`
- Supersede chains (never silent overwrite)
- Memory data stored in `~/.memory/`, repo holds only skill code (clean code/data split)
- Memory language tracks the user's conversation language; frontmatter field names stay English

### Added — tools (`tools/`)

- `validate.py` — frontmatter + link + index validator (exit code based)
- `search.py` — semantic search with auto-selected backend
  - Neural (`sentence-transformers` + SQLite cache) if available
  - TF-IDF cosine over a Latin+CJK mixed-language tokenizer otherwise
- `aggregate-daily.py` / `aggregate-monthly.py` / `aggregate-yearly.py` — read-only draft generation across the time hierarchy
- `expire-sessions.py` — TTL enforcement (30-day session expiry, blocked if not promoted)
- `find-conflicts.py` — pre-write conflict detection
- `forget.py` — soft delete with audit log (`status: redacted`, body blanked, `~/.memory/.audit-redactions.log`)
- `daily-status.py` — millisecond-scale health check (for SessionStart hooks / cron)
- `migrate.py` — schema migration runner with idempotency tracking (`~/.memory/.migrations-applied`)
- `embed.py` — local neural embedding cache builder (privacy: no network calls after model download)
- `sync.py` — git-based multi-machine sync (pull-rebase + commit + push, holds the write lock)
- `_lib.py` — shared primitives: frontmatter parser, mixed-language tokenizer, TF-IDF math, `file_lock()`, `atomic_write()`

### Added — Claude Code integration (`commands/`)

- 11 slash commands wrapping every tool (`/memory-search`, `/memory-validate`, `/memory-aggregate`, `/memory-aggregate-monthly`, `/memory-aggregate-yearly`, `/memory-expire`, `/memory-conflicts`, `/memory-forget`, `/memory-status`, `/memory-migrate`, `/memory-embed`, `/memory-sync`)

### Added — concurrency

- `_lib.file_lock(root)` advisory lock via `fcntl.flock` (POSIX) / `msvcrt.locking` (Windows)
- `_lib.atomic_write(path, content)` — temp-write + fsync + rename
- All write tools (`forget`, `migrate`, `expire`, `sync`) acquire the lock for their full read-modify-write window

### Added — tests + CI

- `tests/fixtures/healthy/` + `tests/fixtures/broken/` — minimal memory stores for validator tests
- `tests/test_validate.sh` — validator works against fixtures
- `tests/test_tfidf.py` — semantic-scoring regression guard
- `tests/test_concurrency.py` — file_lock + atomic_write guard (spawns a process to verify contention behavior)
- `.github/workflows/validate.yml` — runs all of the above plus tool-help smoke tests and markdown-link-check

### Added — docs

- `SKILL.md` — main skill entry (in Chinese, per the language strategy)
- `README.md` — for humans / agents installing the skill
- `CONTRIBUTING.md` — contribution rules, out-of-scope clarification
- `references/` — retrieval, lifecycle, writing-rules, tools, sync
- `templates/` — frontmatter scaffolds for all 7 memory types + the MEMORY.md index seed
- `LICENSE` — MIT
- `requirements-optional.txt` — sentence-transformers (only for neural search)

### Design notes

- **Privacy**: memory data is private; all embedding happens locally; sync uses a user-configured private remote
- **Graceful degradation**: optional features (neural search) silently fall back to the stdlib path when dependencies are missing
- **Schema discipline**: every memory file is validated by a schema; agent rationalizations (auto-flatten files, silent overwrite, grep instead of search) are explicitly forbidden in SKILL.md based on TDD-style subagent tests

### Known limitations (deliberately out of scope; see CONTRIBUTING.md)

- No encryption at rest — use filesystem-level encryption (FileVault / dm-crypt)
- No multi-user sharing — memory is per-user by design
- No real-time multi-machine sync — `sync.py` is pull-rebase, not server-backed
- No GUI

[0.1.0]: https://example.com/your-repo/releases/tag/v0.1.0
