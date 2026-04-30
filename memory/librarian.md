# Librarian memory

Patterns about *how* to maintain `playbook/`. Game knowledge itself goes in the playbook, not here.

## State of the library at session start

- 2026-04-29 (first session): Playbook was scaffolded but empty. `playbook/README.md` documented an aspirational layout (`fundamentals/`, `heroes/{hero}/{overview.md, matchups/, lines.md}`, `general/`, `open-questions.md`, `proposals/`) but only the directories existed; no content files. `open-questions.md` was a header + format template only. First match (`cindra-blue-vs-arakni-002`) integrated this session.

## Routing decisions and why

- **CONFIRMED + rule-grounded → straight into hero `fundamentals.md`.** LC-004 (Marionette transform timing) was a CONFIRMED claim with comprehensive-rules citations (9.3.2b, 9.3.3) and a direct engine implementation reference. One match was sufficient because the claim follows from rules, not from statistical pattern. Filed at `playbook/heroes/arakni/fundamentals.md`. The README's planned per-hero layout (`overview.md`, `matchups/`, `lines.md`) didn't list `fundamentals.md` — I added it because rule-derived hero facts don't fit `overview` (strategy) or `lines` (decision sequences) and don't belong under `matchups/` (matchup-agnostic). Worth flagging to schema-critic if more rule-derived hero facts accrue.
- **INFERRED with no prior corroboration → `open-questions.md`.** Even when the lesson looked obviously true (LC-001, LC-002), the role file is explicit: one match is one match. Parked all three (LC-001/002/003) with match id, plausible mechanism, and a "what would settle it" hook so the next analyst/librarian knows what to look for.
- **Engine-bug findings and "data quality" notes → not propagated to playbook.** These are meta about the toolchain or about the analyst's job, not actionable at decision time. They live in the lessons file and (for engine bugs) in the iteration checkpoint until resolved.

## Format conventions adopted

- **Single-match claims** in fundamentals files: end with `Source: match {id}` plus engine/rules citations when available. Keeps the audit trail without bloating prose.
- **open-questions.md entries** use the README's documented template (one-line hypothesis, First seen / Mechanism / What would settle it / Status). Worth keeping consistent so future librarians can grep and update Status fields cleanly.
- **Decision-time framing.** I rewrote LC-001's claim from "tempo swing favors Arakni" (analyst's framing) to "Arakni pilot: sequence Mark-on-hit weapons first; vs Arakni: deny the *first* Mark-applying hit." Players don't read playbook to learn what *did* happen; they read it to know what to *do*.

## Things that were tricky

- **Where to file LC-004.** README's hero layout listed `overview.md`, `matchups/`, `lines.md` — none of which fit a transform-timing rule fact. Chose `fundamentals.md` (matching the top-level `fundamentals/` naming pattern). If schema-critic wants this normalized, fine — but I didn't write a proposal note for one file.
- **Cindra mirror for LC-001.** The lessons file suggested a mirrored note in both heroes' matchup files. Since LC-001 went to `open-questions.md` (not promoted), no mirror is needed yet. When/if it promotes, remember the mirror — Cindra player needs "vs Arakni" guidance, Arakni player needs "vs Cindra Blue" guidance, and they're not the same prose.
- **Tempting to copy "Decisive moments" verbatim into matchup files.** Resisted — they're narrative, not decision rules. The LC-004 entry already captures the actionable piece. Decisive-moment narratives can stay in the replay folder.

## Drift signals (not yet acted on)

- README's `heroes/{hero}/` layout doesn't enumerate `fundamentals.md`. Now that one exists, schema-critic may want to either (a) add it to the README's hero-folder template or (b) suggest moving rule-derived hero facts to the top-level `fundamentals/` directory, namespaced by hero. No proposal written yet — wait for ≥2 hero `fundamentals.md` files to see if the pattern sticks.
