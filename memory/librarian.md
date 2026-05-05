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

---

# Second session — match `cindra-blue-vs-arakni-004` (2026-04-30)

## State of the library at session start

- One match (`002`) integrated: `heroes/arakni/fundamentals.md` (LC-001 = Marionette transform timing) + three open questions (LC-001/002/003).
- This match (`004`) was the **first complete match** the project has run. Match 002 stalled; match 003 stalled. Match 004 went 23 turns to a clean Cindra Blue win, 152 decisions across both seats via `tools/auto_player.py`.
- Lessons file had been through a correction pass (analyst's LC-004 was misattributed — Scale didn't destroy equipment, Blade Break did). Trusted the corrected version.

## Routing decisions and why

- **CORROBORATED single-match-rules-grounded → straight into `fundamentals.md`.** LC-003 (Cindra Fealty trigger direction) was rule-grounded *and* now had two-match support. Promoted to `playbook/heroes/cindra/fundamentals.md` (new file). Used the same convention as the existing `arakni/fundamentals.md`.
- **CORROBORATED-with-refinement → update existing entry, don't create a new one.** LC-001 (Marionette transform) already lived in `heroes/arakni/fundamentals.md` from session 1. Match 004 corroborated it AND added a refinement (the Agent form is RNG-selected, not deterministic). Edited the existing claim in-place with both match citations.
- **INFERRED single-match → mostly `open-questions.md`, with one judgment-call exception.** LC-006 (Flick Knives loss / re-engagement timing) is single-match but the mechanism is concrete and the decision rule is immediately actionable. Promoted to `arakni/fundamentals.md` with an explicit caveat ("INFERRED — single match; flagged as possibly the same lesson as the Blade-Break trade rule. See open-questions.md LC-004 and LC-006") rather than parking. Risk of "false promotion" is bounded by the explicit cross-reference.
- **STILL INFERRED with mixed evidence → keep parked, update the entry.** LC-002 (pitch discipline) had one violation and one adherence in match 004. Updated the open-questions entry with the new evidence rather than deleting and re-adding — preserves the audit trail.

## Things that were tricky

- **Avoided creating `playbook/matchups/`.** LC-004's suggested home is `playbook/matchups/cindra-blue-vs-arakni.md`, but the README's documented layout puts matchup files under `heroes/{hero}/matchups/{opponent}.md`. Rather than ad-hoc creating a new top-level directory, parked LC-004 in open-questions and flagged the conflict to schema-critic via `playbook/proposals/notes-for-schema-critic.md`.
- **Drift signal escalation.** Session 1 noted "wait for ≥2 hero `fundamentals.md` files." Session 2 created the second one — so wrote `playbook/proposals/notes-for-schema-critic.md` to formally surface the structural questions. Two drift signals now logged there.
- **Session timed out mid-work.** Both `fundamentals.md` files made it to disk before the API stream timed out. Orchestrator finished open-questions, README, schema-critic notes, this memory entry, and the iteration checkpoint inline. Future librarian sessions should check git status when starting — if a previous session left half-applied changes, verify what's done before re-doing it.

## Patterns to remember for session 3

- **Verdict-by-verdict integration is the right granularity.** The analyst tags each LC; the librarian routes each one. Don't look for a global "story" — each candidate gets its own routing decision.
- **The "promote anyway with caveat" exception** (LC-006 above) should stay rare. Default is "park unless rules-grounded AND multi-match." If you find yourself making the exception twice in one session, that's a signal something's wrong — either the analyst is over-tagging INFERRED, or you're under-resisting promotion pressure.
