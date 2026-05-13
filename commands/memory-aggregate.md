---
description: Generate a daily-memory draft from today's sessions (or a given date)
argument-hint: "[YYYY-MM-DD]"
---

Run `~/.claude/skills/chrono-palace-memory/tools/aggregate-daily.py $ARGUMENTS`.

Then act as the **reviewer**, not a passive consumer of the draft:
1. Dedupe overlapping facts across sessions.
2. Classify new observations: tentative (1×) / candidate (≥2×) / confirmed (≥3×). Only confirmed observations are eligible to be promoted to palace/preferences or palace/learned_patterns.
3. Run `find-conflicts.py --topic <topic>` for each notable topic in the draft. If conflicts exist, decide supersede vs. preserve before writing the daily.
4. Fill in `promoted_to:` on each source session **and** on the daily.
5. Update MEMORY.md to link the new daily entry.
6. Only then write the actual `daily/YYYY/MM/DD.md` file.

If the user asks for today's draft and `daily/<today>.md` already exists, ask before overwriting — daily files are append-only by convention.
