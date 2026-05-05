# Proposal: No structural change — playbook is too small and has no consumer yet

## Observation

Two drift signals from the librarian (`playbook/proposals/notes-for-schema-critic.md`):

1. Both `heroes/{hero}/` folders now contain `fundamentals.md`, which the README's per-hero layout doesn't list.
2. LC-004 (Blade-Break trade pattern) is genuinely cross-perspective and the README's `heroes/{hero}/matchups/{opponent}.md` placement forces duplication.

Both are real. Neither is currently load-bearing. Three reasons:

**The playbook has no decision-time reader.** Per `playbook/player_spawn_prompt.md` lines 31-36 and 102-106, the operator deliberately keeps the player sub-agent's on-spawn reading to `match_protocol.md` + the deck file. Strategy docs were tried once, blew the budget, and the game stalled at T22. So the test the role file gives me — "is the structure surfacing the right knowledge to the player at decision time?" — is currently vacuous: nothing in the playbook reaches the player. The only readers are the librarian (writing) and the schema-critic (auditing). Both can navigate ad-hoc filenames trivially.

**Total content fits on one screen.** Two `fundamentals.md` files (~26 lines each), one `open-questions.md` (3 entries), one README. Empty: `fundamentals/`, `general/`, every `matchups/`, every `overview.md`, every `lines.md`. Restructuring 4 files of content to fit a layout sized for 40 is premature optimization.

**The "drift" is mostly the README being aspirational.** The README's per-hero layout (`overview.md`, `matchups/`, `lines.md`) was written before any lessons existed. `fundamentals.md` emerged because rule-derived hero facts arrived first and didn't fit the strategic-content slots — which is fine; it's the layout being wrong about what arrives first, not the content being wrong. Same story with `matchups/`: the layout assumed per-hero matchup files would dominate, but the first matchup-relevant lesson (LC-004) is structurally mutual.

## Proposed change

**No change.** The librarian should continue routing using the de-facto convention:
- Hero-specific rules-grounded facts → `heroes/{hero}/fundamentals.md` (current practice; works).
- Mutual matchup lessons like LC-004 on promotion → `heroes/{hero}/matchups/{opponent}.md` with the same content from each perspective, OR a new top-level `matchups/{hero1}-vs-{hero2}.md` file decided at promotion time. Pick one when LC-004 actually promotes; don't pre-commit.

The README is mildly stale but documents an aspiration, not a contract. Leave it until something breaks.

## Why this serves player decision time

It doesn't directly — because nothing currently does, by operator choice. What it serves instead is **not burning librarian and schema-critic cycles on a structure decision before there's evidence to decide on**. The decision-time question is real but premature. When the operator decides players should read playbook content (or when an `auto_player.py` tool starts injecting playbook excerpts into per-decision context), the access pattern of the actual consumer will dictate the right structure. Picking now is guessing.

A concrete example of why guessing now is wrong: if the eventual consumer turns out to be a per-decision context injector that does fuzzy retrieval over playbook markdown, file boundaries matter much less than section headings and citation density — and we'd be optimizing the wrong axis. If the consumer turns out to be a hero-specific pre-match briefing, the per-hero folder is already correct and we don't need a top-level `matchups/`. We don't know which.

## Cost

Zero librarian work today. The cost is that the README will continue to slightly misrepresent reality, and the next schema-critic spawn will re-encounter the same two drift signals. Both are tolerable at this scale.

One small optional cleanup the librarian can do without a structural proposal: add a one-line note to `playbook/README.md` that `fundamentals.md` exists per-hero by current practice and that the documented per-hero layout is aspirational. That's a content edit, not a schema change, and it's the librarian's call.

## Anti-cases — what would change my mind

A future schema-critic should act on these drift signals when **any one** of the following becomes true:

1. **A consumer appears.** Player sub-agents start reading playbook files at spawn (or per-decision), or an automated retrieval layer is added. The moment there's a real reader with measurable cost-per-access, restructure for that reader.

2. **Duplication actually happens.** LC-004 promotes and the librarian writes the same content into two `matchups/` files (cindra's and arakni's) and they start drifting. That's the moment a top-level `matchups/{a}-vs-{b}.md` becomes load-bearing. Until LC-004 promotes, the duplication is hypothetical.

3. **`fundamentals.md` count crosses ~5 heroes** with substantive content. At that scale the README being silent on the file becomes a navigation problem for the librarian doing cross-hero edits, and the question of whether rule-facts should consolidate into a top-level `fundamentals/{hero}/` namespace becomes worth the refactor cost.

4. **A category emerges that the current layout actively fights.** The two best candidates from current data: (a) "deck-construction warnings" — both promoted hero fundamentals are bleeding into deck-list commentary (Cindra Blue's Mark-applier scarcity); if a third deck-construction-flavored lesson lands it may want its own home. (b) "engine-surfacing limitations" — the analyst keeps logging "trigger doesn't emit a discrete event" findings in lessons; if those become recurring playbook content rather than one-shot engine-developer notes, they need a home. Neither is urgent.

5. **The pitch-discipline lesson (LC-002) promotes.** It's slated for `playbook/general/pitch-discipline.md`, which would be the first inhabitant of `general/`. That's the right moment to ask whether `general/` should subdivide (resource discipline, defense priorities, race math) or stay flat. Today `general/` is empty so the question doesn't arise.

A scenario where "no change" makes things worse: if the librarian, given ambiguous routing, starts splitting one logical lesson across multiple files for safety (e.g. half of LC-004 in `arakni/matchups/cindra.md` and half in `cindra/matchups/arakni.md` because there's no canonical home), that fragmentation could be invisible until a future analyst tries to corroborate and can't find the prior claim. The mitigation is the librarian's existing discipline of recording "suggested home" in `lessons.md` and flagging ambiguous routes via `notes-for-schema-critic.md` — which is what triggered this review and is working as intended.
