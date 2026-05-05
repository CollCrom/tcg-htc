# Notes for schema-critic

Drift signals the librarian observed but didn't act on. The librarian's role is to *integrate* lessons, not to restructure the playbook — substantive structural changes are schema-critic's domain. Each entry below is a "you might want to look at this when you next run" pointer, not a directive.

---

## `heroes/{hero}/fundamentals.md` is now established but not in the README's hero layout

- First flagged: librarian session 2026-04-29 (after match 002).
- Re-confirmed: librarian session 2026-04-29 (after match 004) — `playbook/heroes/cindra/fundamentals.md` was created using the same convention as `playbook/heroes/arakni/fundamentals.md`.
- Observation: the README's documented per-hero layout enumerates `overview.md`, `matchups/`, `lines.md`. None of those fit rule-derived hero facts (e.g. trigger conditions, transform timing). Both hero folders now have a `fundamentals.md` file by ad-hoc convention.
- Two paths schema-critic might consider:
  1. Add `fundamentals.md` to the hero-folder template in the README (lowest-effort, locks the de facto convention).
  2. Move rule-derived hero facts to the top-level `fundamentals/` directory, namespaced by hero (e.g. `fundamentals/arakni/marionette-transform.md`). Cleaner separation between rule-facts and strategic content, but more refactor cost.
- Trigger for review: ≥2 hero `fundamentals.md` files exist, both with substantive content. The pattern is no longer single-instance.

## `playbook/matchups/` directory does not exist but LC-004 wants to live there

- First flagged: librarian session after match 004 (open-questions.md → LC-004).
- Observation: the lessons file's revised LC-004 has a "suggested home: `playbook/matchups/cindra-blue-vs-arakni.md`" pointer, but the README's documented layout puts matchup files under `heroes/{hero}/matchups/{opponent}.md` — which forces duplication (one file under arakni's matchups, one under cindra's, both saying basically the same thing).
- Two paths schema-critic might consider:
  1. Create a top-level `matchups/{hero1}-vs-{hero2}.md` directory for shared matchup notes, with the per-hero `matchups/` folders linking to them. Solves the duplication.
  2. Keep duplication but enforce a "from {pilot}'s perspective" framing in each per-hero file. Higher maintenance but localizes guidance to the reader's seat.
- Trigger for review: when LC-004 (or any future matchup-specific lesson) is ready for promotion. Currently still in `open-questions.md`.
