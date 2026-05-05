# Arakni — Fundamentals

Rules-and-text-grounded facts about playing (or playing against) Arakni, Marionette. Things that follow from card text and the comprehensive rules, not from meta or matchup-specific tactics.

## Marionette → Agent of Chaos transform timing

Marionette transforms at **end of turn**, on the first turn an opposing hero is marked. Practical consequence: a single opposing source that *applies* Mark on hit (e.g. Hunter's Klaive) triggers the transform that same turn end — repeated chains are not required.

- Mark persists across turns (rule 9.3.2b) and is removed only by being hit by an opposing source (rule 9.3.3) or by the marked permanent ceasing to exist. Application-on-hit and removal-on-hit are simultaneous parts of the hit event, so a Mark-applying hit by Arakni satisfies the end-of-turn check before the next turn boundary.
- Cards that *interact with* Mark (e.g. Whittle from Bone's "When this attacks a marked hero, equip a Graphene Chelicera") do **not** apply Mark themselves and do **not** consume it — Mark is removed only via the rules-9.3.3 hit pathway. So a Whittle attack against an unmarked defender does nothing for the transform clock.
- Decision-time corollary (Arakni pilot): your transform-enabling action is the *first Mark-applying hit*, not just any attack. Sequencing a Mark-on-hit weapon (Klaive) before non-Mark filler maximizes the chance of ending the turn with the opponent marked.
- Decision-time corollary (vs Arakni): every turn you take a Mark-applying hit, expect Marionette to transform that end of turn. Plan defense around denying the *first* such hit, not around stripping Mark later (Mark-removal effects are scarce).

**The specific Agent form is RNG-selected, not deterministic.** Engine picks via `state.rng.choice(player.demi_heroes)` (`engine/cards/abilities/heroes.py:392`). Match 002 picked Tarantula on the first transform; match 004 picked Trap-Door on T2-end and then Redback on T4-end (after a silent return-to-brood and re-Mark cycle). Practical consequence: the opponent cannot plan around a specific Agent — must be ready for all four (Trap-Door, Redback, Tarantula, plus any others). Repeated Mark applications across multiple turns can chain through ALL of Arakni's demi-heroes via the return-to-brood loop.

Sources: match `cindra-blue-vs-arakni-002` (T1 unmarked Whittle attack: no transform; T3 Klaive hit applied Mark and triggered `BECOME_AGENT` → Tarantula at end of turn). Match `cindra-blue-vs-arakni-004` (T2 Klaive flick+swing → Trap-Door at T2 end; re-Mark T4 → Redback at T4 end after return-to-brood). Engine implementation: `engine/cards/abilities/assassin.py:_whittle_from_bone_on_attack`, `engine/cards/abilities/heroes.py:392`. Rules: comprehensive-rules 9.3.2b, 9.3.3.

## Decision rule: when Flick Knives is destroyed, treat in-hand Mark-appliers as re-engagement plays, not hold-cards

Arakni Marionette's offense is gated on opposing-Mark: Klaive's flick chain (Flick Knives activator), Marionette/Redback stealth attacks, etc. all require Mark on the opponent. Flick Knives is the primary "weapon-flick applies Mark" channel; once it's destroyed (typically by Blade Break — see `open-questions.md` LC-004), the only remaining Mark-application path is in-hand cards: **Mark of the Black Widow (Red, 0p)** and the stealth-discounted attacks. Holding these "for a bigger turn" while passing the action phase is value-negative — without an opposing-Mark Arakni's stealth attacks are illegal and the turn produces nothing.

- Decision-time corollary: if Flick Knives is dead and you draw / hold Mark of the Black Widow, play it the same turn you can chain a stealth attack into the Mark, even at low value. A 0-cost Mark + a single stealth swing recovers the offense loop; a passed turn does not.
- Limit of evidence: this rule is grounded in match 004's pattern (8 of 17 Arakni turns post-T5 were full passes after Flick Knives died T5; Mark of the Black Widow never surfaced in PLAY_CARD events though 3 copies were in deck). The lesson is `INFERRED` and may consolidate with the broader Blade-Break trade lesson — if you find yourself adding to it, check `open-questions.md` LC-006/LC-004 first to disambiguate.

Source: match `cindra-blue-vs-arakni-004` (T6/T8/T10/T14/T16/T18/T20/T22 all Arakni full-passes after Flick Knives destroyed T5). [INFERRED — single match; flagged as possibly the same lesson as the Blade-Break trade rule. See `open-questions.md` LC-004 and LC-006.]
