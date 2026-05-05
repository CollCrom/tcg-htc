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

## Pitch discipline: don't pitch 3-pitch Blues for 1R weapon activations

- First seen: match `cindra-blue-vs-arakni-002` (LC-002, INFERRED)
- Corroboration attempt: match `cindra-blue-vs-arakni-004` — mixed evidence. One pilot violation (T7 Throw Dagger 3-pitch for Command & Conquer's 2-cost) and one explicit pilot adherence (T15 Cindra deferred Exposed: "save Exposed for a bigger attack to mark"). Pattern is present but not pilot-consistent across the data we have.
- Plausible mechanism: Pitched value does not carry to the next turn. Pitching a 3-pitch Blue for a 1R activation leaks 2R of pitched value. Decision rule candidate: when the only resource sink this turn is a 1R weapon activation, pitch the lowest-value card and bank the 3-pitch for a turn that spends ≥2R.
- What would settle it: a third match where the pitch order is varied AND the cost of a violation is traceable to a lost game (e.g. a turn where the saved 3-pitch would have enabled a kill or critical defense). Likely a `playbook/general/pitch-discipline.md` claim once corroborated. Alternative: matches where dumping a high-pitch Blue early (e.g. to thin for arsenal quality next turn) is correct, which would refine rather than confirm the rule.
- Status: open after 2 matches (002 violated, 004 mixed)

## vs Arakni Marionette: lead a high-power chain link early — their Blade-Break equipment trades itself away

- First seen: match `cindra-blue-vs-arakni-004` (LC-004, INFERRED; revised after correction pass 2026-04-29)
- Plausible mechanism: Arakni Marionette's defensive equipment (Mask of Deceit, Flick Knives, Fyendal's Spring Tunic) all carry **Blade Break**. Per rule 8.3.3 (`engine/rules/keyword_engine.py:237`), a Blade Break piece is destroyed when the combat chain it defended closes. Stacking three pieces against a single high-power chain link (e.g. AotD: Scale 5p, AotD: Blood 4p) trades all three permanent equipment slots in one swing — including the Mask that gates Marionette-form transforms and the Flick Knives that channels Klaive activations. T5 of match 004 lost all three pieces this way, and Arakni's offense never recovered (passed action phases on 8 of 17 subsequent turns).
- Corollary (Arakni side): defend with at most one Blade-Break piece per chain link, or take the damage on hero. The face-damage cost is recoverable; losing the Mask + Flick Knives bundle is not.
- What would settle it: a second Cindra-vs-Arakni match where Cindra leads with a high-power chain link AND Arakni defends with multiple Blade-Break pieces — does the same equipment-collapse-then-pass-out pattern emerge? Bonus: a match where Arakni declines to defend with Mask/Flick Knives and instead takes face damage, to see if their offense survives.
- Suggested home on promotion: `playbook/matchups/cindra-blue-vs-arakni.md` (new file — first matchup-specific entry).
- Status: open after 1 match. Mechanism is rules-grounded (not pattern-luck), so a second corroboration should suffice for promotion.

## Cindra-first vs Arakni is significantly better than Cindra-second

- First seen: match `cindra-blue-vs-arakni-004` (LC-005, HYPOTHESIS)
- Plausible mechanism: matches 002 (Arakni first) and 003 (Arakni first) both ended with Arakni ahead before stalling. Match 004 (Cindra first, seed 91) ended in a Cindra win with a 30-life margin. The proposed mechanism is that Cindra-first lets her land an opening Draconic chain or arsenal a Mark-applier before Arakni can equip-flick into the first Mark hit; Cindra-second means Arakni gets the first Mark on T1 and the Marionette transform clock starts at T1-end instead of T3-end.
- What would settle it: deliberately seed a Cindra-vs-Arakni match where Arakni goes first (e.g. seed search until first-player flips), holding the deck pair constant. Compare game shape (turns to lethal, life totals at fixed turn counts, count of Marionette transforms). N=1 vs N=1 isn't statistically meaningful, but the magnitude of the swing in match 004 vs 002/003 is suggestive — worth a controlled comparison.
- Status: open. Single complete match per seat order; matches 002 and 003 stalled before reaching terminal state, so this is genuinely speculative.

---

## Promoted out of this file

- **LC-001** (Mark→Marionette transform timing) — promoted to `playbook/heroes/arakni/fundamentals.md` after match-004 corroboration. The Agent form is RNG-selected (`heroes.py:392`) — this refinement is in the promoted entry.
- **LC-003** (Cindra Fealty triggers on Cindra's own attack hitting a marked opponent) — promoted to `playbook/heroes/cindra/fundamentals.md` after match-004 corroboration.
- **LC-006** (Arakni without Flick Knives or in-hand Mark-applier has no recovery) — promoted to `playbook/heroes/arakni/fundamentals.md` after match-004 single-match data, with a flag that it may consolidate with LC-004 on the next analysis.
