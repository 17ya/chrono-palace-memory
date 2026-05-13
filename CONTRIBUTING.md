# Contributing to chrono-palace-memory

Thanks for the interest. This project is small on purpose — the schema and
the rule set are the contract that lets agents reliably read each other's
memory. Changes that broaden the contract need to clear a higher bar than
changes that tighten it.

## Ground rules

1. **Don't grow the schema casually.** Adding a frontmatter field affects
   every memory ever written. Propose new fields with a concrete use case
   that can't be solved with what's already there.
2. **Don't soften the discipline.** The "always cite evidence", "never
   overwrite", "MEMORY.md is index not store" rules exist because the
   alternative is silent rot. Loopholes will be closed in review.
3. **Don't add core dependencies.** `tools/` is stdlib-only for **required**
   features. *Optional* features (neural embeddings, server backends, etc.)
   may add dependencies, but must:
   - Be listed in `requirements-optional.txt`, not a hard requirement
   - Degrade gracefully when the dep is missing (see `search.py`'s
     auto-fallback to TF-IDF when `sentence-transformers` isn't installed)
   - Be documented as optional in README
4. **One PR, one concern.** Bug fix, doc tweak, new tool — each its own PR.

## Working tree layout (recap)

```
SKILL.md           # primary skill entry; consumed by the agent
README.md          # for humans
references/        # looked up by agent during operations
templates/         # frontmatter scaffolds
tools/             # python helpers, stdlib only
commands/          # slash-command definitions for Claude Code
tests/fixtures/    # healthy + broken memory stores for CI
.github/workflows/ # CI
```

## Local checks before opening a PR

```bash
# 1. Validator passes against fixtures
bash tests/test_validate.sh

# 2. Every tool at least loads
for t in tools/*.py; do python3 "$t" --help >/dev/null; done

# 3. Validator passes against your own ~/.memory (if you have one)
python3 tools/validate.py
```

CI runs the same checks plus markdown link-check.

## Adding a new tool

1. Reuse `tools/_lib.py` — don't reinvent frontmatter parsing.
2. Add `--help`, `--root`, sensible exit codes (0 / 1 / 2).
3. Default to read-only / dry-run. Require an explicit `--apply` for
   destructive operations.
4. Add a corresponding `commands/<name>.md` slash command.
5. Document it in `references/tools.md`.
6. Add a CI smoke step that runs the tool against `tests/fixtures/healthy/`.

## Adding a new frontmatter field

1. Open an issue describing the use case. Wait for discussion before coding.
2. Update `references/writing-rules.md` with the field's semantics, valid
   values, and when it's required vs. optional.
3. Update relevant templates.
4. Add a validation rule in `tools/validate.py`.
5. Add a fixture (healthy + broken variant if applicable).

## Changing the schema (renaming / removing fields)

This is a breaking change. PRs must include:

- A migration note in `references/lifecycle.md` (or a new `migration.md`)
- A short Python migration script in `tools/migrations/<date>-<slug>.py`
  that operates on `~/.memory/` (read-only by default, `--apply` to write)
- Updated fixtures

## Style

- Markdown: GFM. No trailing whitespace. ATX headers (`#`, not setext).
- Python: stdlib only. Type-hint everything. `from __future__ import annotations`.
- Frontmatter field names: English `snake_case`. Body and `description` values:
  whatever language the memory was written in.

## Out of scope (for now)

- **Encryption at rest** — filesystem-level concern (use FileVault / dm-crypt / EncFS). The skill does not encrypt files because that would prevent git-based multi-machine sync from working with most providers. If you need encryption, use a remote that supports it (e.g. a git server behind a VPN, or a transparently encrypted volume).
- **Multi-user / shared memory** — memory is per-user by design. Two humans sharing one `~/.memory/` would conflate identities and break the user-entity model. Each user keeps their own.
- **Real-time multi-machine sync** — `tools/sync.py` is pull-rebase based (manual or hook-triggered). Sub-second propagation requires a server-backed memory; not in scope here.
- **GUI** — markdown + grep is sufficient. Build one outside if you want.

If you want one of these, fork. Happy to link useful forks from the README.

## License

By contributing you agree your contribution is licensed under the project's
MIT license (see [LICENSE](LICENSE)).
