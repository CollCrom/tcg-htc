# Arakni — Fundamentals

Rules-and-text-grounded facts about playing (or playing against) Arakni, Marionette. Things that follow from card text and the comprehensive rules, not from meta or matchup-specific tactics.

## Marionette → Agent of Chaos transform timing

Marionette transforms at **end of turn**, on the first turn an opposing hero is marked. Practical consequence: a single opposing source that *applies* Mark on hit (e.g. Hunter's Klaive) triggers the transform that same turn end — repeated chains are not required.

- Mark persists across turns (rule 9.3.2b) and is removed only by being hit by an opposing source (rule 9.3.3) or by the marked permanent ceasing to exist. Application-on-hit and removal-on-hit are simultaneous parts of the hit event, so a Mark-applying hit by Arakni satisfies the end-of-turn check before the next turn boundary.
- Cards that *interact with* Mark (e.g. Whittle from Bone's "When this attacks a marked hero, equip a Graphene Chelicera") do **not** apply Mark themselves and do **not** consume it — Mark is removed only via the rules-9.3.3 hit pathway. So a Whittle attack against an unmarked defender does nothing for the transform clock.
- Decision-time corollary (Arakni pilot): your transform-enabling action is the *first Mark-applying hit*, not just any attack. Sequencing a Mark-on-hit weapon (Klaive) before non-Mark filler maximizes the chance of ending the turn with the opponent marked.
- Decision-time corollary (vs Arakni): every turn you take a Mark-applying hit, expect Marionette to transform that end of turn. Plan defense around denying the *first* such hit, not around stripping Mark later (Mark-removal effects are scarce).

Source: match `cindra-blue-vs-arakni-002` (T1 unmarked Whittle attack: no transform; T3 Klaive hit applied Mark and triggered `BECOME_AGENT` at end of turn). Engine implementation: `engine/cards/abilities/assassin.py:_whittle_from_bone_on_attack`. Rules: comprehensive-rules 9.3.2b, 9.3.3.
