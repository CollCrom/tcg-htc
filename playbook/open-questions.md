# Open questions

Hypotheses awaiting evidence. Lessons tagged HYPOTHESIS by an analyst land here, not in the per-hero playbook. INFERRED lessons that don't yet have cross-match support also go here, with the match id, until a second match either confirms or disconfirms them.

Format:

```
## {one-line question or hypothesis}

- First seen: match {id}
- Plausible mechanism: ...
- What would settle it: ...
- Status: open / confirmed-as-of-{match} (then promote to playbook) / disconfirmed-as-of-{match} (then delete)
```

---

## Cindra Blue vs Arakni: each opposing Mark application accelerates Marionette → Agent of Chaos

- First seen: match `cindra-blue-vs-arakni-002` (LC-001, INFERRED)
- Plausible mechanism: Cindra Blue's listed deck (`ref/decks/decklist-cindra-blue.md`) has no Mark-removal cards, so once an Arakni source applies Mark on hit, Cindra stays marked through end of turn and Marionette's transform check fires. Arakni's deck has multiple Mark-on-hit sources (Hunter's Klaive, Mark of the Black Widow), so the transform clock is short.
- What would settle it: a second Cindra Blue vs Arakni match where (a) the first Mark hit lands at a different turn and the transform fires the same end of turn, and (b) re-application of Mark on a later turn is observed in the event stream (the L60–L66 segment of the original match shows `target_was_marked=true` at T5 but the re-application source between T3 and T5 was not surfaced). Bonus: a match where Cindra Blue defends the first Mark-applier off and the transform is delayed.
- Status: open

## Pitch discipline: don't pitch 3-pitch Blues for 1R weapon activations

- First seen: match `cindra-blue-vs-arakni-002` (LC-002, INFERRED)
- Plausible mechanism: Player A pitched a 3-pitch Blue twice (Exposed T2, Dragon Power T4) to pay a 1R Kunai activation, leaking 2R of pitched value each time. Pitched value does not carry to the next turn. Decision rule candidate: when the only resource sink this turn is a 1R weapon activation, pitch the lowest-value card and bank the 3-pitch for a turn that spends ≥2R.
- What would settle it: matches where the pitch order is varied. Confirm if low-pitch-first is a generally better heuristic, or if there are matchup-specific cases where dumping a high-pitch Blue early (e.g. to thin for arsenal quality next turn) is correct. Likely a `playbook/general/pitch-discipline.md` claim once corroborated.
- Status: open

## Cindra's Fealty plan is gated on Cindra applying Mark, not opponent's mark status on Cindra

- First seen: match `cindra-blue-vs-arakni-002` (LC-003, HYPOTHESIS)
- Plausible mechanism: Cindra's hero text triggers Fealty creation when Cindra hits a *marked hero* — the marked hero must be the target of Cindra's hit (i.e. the opponent), not Cindra herself. Against Arakni, Arakni's gameplan marks Cindra, so Cindra-side mark application is the bottleneck. Cindra Blue lists with few "I mark the opponent" tools (Mark with Magma, Exposed) may struggle to build Fealty cascades vs Mark-aggressive opponents who can survive long enough to flip the mark direction.
- What would settle it: another Cindra Blue match (any opponent) where Cindra successfully creates ≥1 Fealty token via the hero trigger; trace which mark-applying card enabled it, and whether the deck's mark-applier count is the limiting factor. Or: a match where Cindra arsenals a mark-applier and successfully activates Fealty — confirming the plan is workable but deck-list-sensitive.
- Status: open
