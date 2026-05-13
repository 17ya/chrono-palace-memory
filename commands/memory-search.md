---
description: Search the chrono-palace memory store by keyword + scoring formula
argument-hint: "<query>"
---

Run `~/.claude/skills/chrono-palace-memory/tools/search.py "$ARGUMENTS"` and present the top hits.

For each hit, after listing path + score:
1. If user's intent is clear and the top hit is a strong match (score ≥ 0.8), read the file with the Read tool and synthesize a direct answer.
2. If multiple hits look relevant, ask the user which thread to pursue.
3. If no hit scores ≥ 0.3, say so explicitly rather than guessing.

Do not invent results that aren't in the search output.
