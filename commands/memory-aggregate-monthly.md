---
description: Generate a monthly-memory draft from the month's daily entries
argument-hint: "[YYYY-MM]"
---

Run `~/.claude/skills/chrono-palace-memory/tools/aggregate-monthly.py $ARGUMENTS`.

Act as the reviewer:
1. **Pattern promotion to reflection layer**: any pattern observed across ≥3 distinct days in the month is a candidate for `palace/learned_patterns.md` — verify the days are independent observations, not echoes of one event.
2. **Preferences**: tentative preferences mentioned multiple times across the month → upgrade their `status` in `palace/preferences.md` and increase `confidence`.
3. **Decisions**: list every decision confirmed *and* every decision reversed within the month. Reversed decisions keep both old (`superseded`) and new (`active`) with `reason:`.
4. **Compression hint**: after monthly is saved, the day-level details are partly redundant. Don't delete daily entries — but note in MEMORY.md that the monthly is the canonical summary for this period.
5. Update each source daily's `promoted_to:` if its content was promoted to palace via this monthly review.
6. Update MEMORY.md index.

Only write `monthly/YYYY/MM.md` after the above review steps.
