# Iteration checkpoint

## Matches processed

- **cindra-blue-vs-arakni-002** (processed 2026-04-29; corrected 2026-04-29; integrated 2026-04-29) - `replays/cindra-blue-vs-arakni-002/lessons.md`. Status: **integrated by librarian**. Match did not reach a terminal state (Player A stalled at T6 action phase); usable for play-pattern lessons but not for win/loss claims.
  - LC-004 (CONFIRMED) → `playbook/heroes/arakni/fundamentals.md` (Marionette transform timing).
  - LC-001 (INFERRED), LC-002 (INFERRED), LC-003 (HYPOTHESIS) → `playbook/open-questions.md`. Per role spec, single-match INFERRED claims do not promote until corroborated by a second match.
  - Engine-bug findings: **all resolved** (Klaive go-again = player error, T6 stall mitigated via `pending_age_seconds` exposure, Shelter prevention now emits `DAMAGE_PREVENTED` event). Not propagated to playbook.
  - Data-quality notes: kept in lessons file; not playbook material.
  - **Correction pass:** original T1 narrative had four errors (Whittle "applies Mark", Whittle "consumes Mark", power double-count, wrong "first decisive moment"); revised by analyst — Decisive Moments + LC-001 + LC-004 rewritten, meta-lesson appended to `memory/analyst.md`.

## Pending integration items

- (none)

## Drift signals for schema-critic

- `playbook/heroes/{hero}/` layout in `playbook/README.md` doesn't enumerate `fundamentals.md`, but the librarian created one (`heroes/arakni/fundamentals.md`) because rule-derived hero facts don't fit `overview.md` / `matchups/` / `lines.md`. Worth normalizing once there's a second instance.
