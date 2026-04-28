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

Empty at project start. Populated through self-play.
