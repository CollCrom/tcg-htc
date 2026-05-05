# Cindra — Fundamentals

Rules-and-text-grounded facts about playing (or playing against) Cindra. Things that follow from card text and the comprehensive rules, not from meta or matchup-specific tactics.

## Fealty triggers on Cindra's *own* attack hitting a marked opponent — not on Cindra being marked

Cindra's hero text (CindraRetributionTrigger, `engine/cards/abilities/heroes.py:226`) creates a Fealty token only when **Cindra is the attacker AND the target was marked at attack-declared time** (`attacker_index == self.controller_index AND target_was_marked`). Being marked yourself does nothing.

- Decision-time corollary (Cindra pilot, deck-construction warning): the Cindra Blue list ships with very few Mark-on-the-opponent tools — essentially **Mark with Magma** and **Exposed** as a pump+mark. That makes the Fealty cascade gameplan rare in practice against decks that pressure Cindra (they spend the Mark slots on you, not the reverse). Treat Fealty creation as a deliberate one-shot setup turn (arsenal a Mark-applier, then attack a marked target the next turn), not a reliable engine.
- Decision-time corollary (vs Cindra Blue): you do not have to fear Fealty cascades just because you're applying Mark to Cindra — that mark direction does not feed Cindra's trigger. The Fealty risk arises only on turns where Cindra successfully puts Mark on *you* and follows up with a hit.
- Mechanism implication: a typical race turn where Cindra attacks an unmarked Arakni produces no Fealty token. Draconic conversions that depend on Fealty/Aura tokens (`engine/cards/abilities/heroes.py:324`) are therefore also gated on Cindra having previously applied Mark — meaning early-game Draconic-rider plays (e.g. AotD: Scale's Draconic-only on-hit text) are typically dormant until Cindra has set up at least one Mark hit.

Sources:
- Match `cindra-blue-vs-arakni-002` — Cindra was marked repeatedly by Arakni (Klaive); no Fealty token observed. (LC-003, originally HYPOTHESIS.)
- Match `cindra-blue-vs-arakni-004` — 16 turns elapsed before Cindra applied opposing Mark for the first time (T17 Exposed → Demonstrate Devotion HIT with `target_was_marked: true`); exactly one Fealty-eligible hit in the entire 23-turn match. Cindra was marked twice (T2, T4) with zero Fealty triggers from those events. Match was decided by other means (race + Blade Break trade) before Fealty mattered.

Engine implementation: `engine/cards/abilities/heroes.py:226` (CindraRetributionTrigger). Note: Fealty creation does NOT emit a discrete event in events.jsonl as of match 004 — the trigger only logs to `log.info`, so the only ground-truth signal is a Cindra HIT with `target_was_marked: true`.
