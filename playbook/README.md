# Playbook

Self-generated, curated knowledge about playing Flesh and Blood. Only the librarian writes here. Lesson flow: `replays/*/lessons.md` → librarian → here.

This structure is an initial hypothesis, not a fixed schema. The schema-critic role is responsible for periodically challenging whether it's still the right shape.

## Layout

```
fundamentals/      Rules-derived facts that don't change with meta or card pool.
                   Read these before your first match. Examples: turn structure,
                   combat sequencing, arsenal mechanics.

heroes/{hero}/     Per-hero knowledge.
  overview.md      Archetype, win condition, key turns to plan toward.
  matchups/        One file per opponent hero seen so far.
    {opponent}.md
  lines.md         Repeatable decision lines this hero relies on.

general/           Cross-hero patterns. Tempo vs. value, blocking priorities,
                   resource discipline, etc. Things that aren't tied to one hero
                   but aren't pure rules either.

open-questions.md  Hypotheses awaiting evidence. Lessons tagged HYPOTHESIS
                   by analysts go here, not into the per-hero playbook.

proposals/         schema-critic's structural change proposals.
                   Awaiting librarian/orchestrator response.
```

## Discipline

- **Cite matches.** Non-obvious claims should reference a match id (`{date}-{matchid}`), so future librarians can re-evaluate when the meta or card pool shifts.
- **Curate, don't accumulate.** A growing playbook isn't automatically a better playbook. Wrong claims get deleted; verbose claims get compressed.
- **Write for decision time.** Every entry should be something the player can find and apply mid-match prep. If it isn't, reframe it or move it to `open-questions.md`.

## Status

Populated through self-play. Current contents:

- `heroes/arakni/fundamentals.md` — Marionette transform timing (from `cindra-blue-vs-arakni-002`, refined by `cindra-blue-vs-arakni-004` to add the RNG-selected Agent form). Also: Flick Knives loss / re-engagement decision rule (from `cindra-blue-vs-arakni-004`).
- `heroes/cindra/fundamentals.md` — Fealty trigger fires on Cindra's *own* attack hitting a marked opponent, not on Cindra being marked (from `cindra-blue-vs-arakni-002` + `cindra-blue-vs-arakni-004`).
- `open-questions.md` — pending: pitch discipline (LC-002, mixed evidence across 2 matches), Blade-Break trade pattern (LC-004, single-match), Cindra-first-vs-second hypothesis (LC-005, single-match).
- `proposals/notes-for-schema-critic.md` — drift signals worth structural review.

Empty pending more matches: `fundamentals/`, `general/`, `heroes/*/matchups/`, `heroes/*/overview.md`, `heroes/*/lines.md`.
