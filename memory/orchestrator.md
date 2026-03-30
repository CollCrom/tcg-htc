# Orchestrator Memory

Persistent learnings across sessions. Update this as you go.

## Session Learnings

### 2026-03-27: Phase 4 + Phase 5 Complete

- **Oscilio dropped, Cindra is the new target.** Blue Cindra vs Arakni Marionette is the matchup. Red Cindra kept as reference.
- **Skeptic gate must be enforced by orchestrator.** Builder spawn prompts must always say "do NOT create a PR." Orchestrator runs skeptic loop, orchestrator creates PR.
- **definition.keywords bypass is a recurring bug.** Any time new keyword checks are added, verify they go through `effect_engine.get_modified_keywords()` not `card.definition.keywords`.
- **game.py was split into managers** (PR #29). ActionBuilder, KeywordEngine, CostManager extracted.
- **Phase 5 complete.** Ability registry, hero abilities, 48 card abilities (assassin + ninja), equipment abilities, full game integration tests. 334 tests passing. Both decks run end-to-end.
- **Forum dropped.** Agents don't use it in practice — communication is synchronous via spawn prompts and skeptic reviews. Can re-add later for async work.

### 2026-03-28: Pre-Phase 6 Cleanup + Deferred Items Complete

- **Switched card data to Fabrary dataset** (PR #47). 4,562 cards (up from 4,217). Refresh script: `python3 -m htc.cards`.
- **Keyword parsing fix**: `card_keywords` in Fabrary means "keywords mentioned on card", not inherent. `_is_keyword_inherent()` parses functional_text to distinguish. Squash merges can lose commits — verify after merge.
- **Equipment activation infrastructure** (PR #49). Equipment instants and attack reactions now offered in action builder. Fixes previously dead-code abilities (Flick Knives, Tide Flippers, etc).
- **All deferred equipment done**: Dragonscaler Flight Path (instant, cost reduction, bonus weapon attacks), Mask of Deceit (Agent of Chaos transformation), Stalker's Steps, Enflame the Firebrand.
- **Agent of Chaos system**: 6 demi-heroes, hero transformation, return-to-brood, once-per-turn enforcement, registry cleanup.
- **Banish zone + play-from-banish** (PR #50). Trap-Door on-become search/banish, Under the Trap-Door instant-discard, graveyard redirect, defense reactions from banish.
- **Graphene Chelicera cost reduction** for Orb-Weaver.
- **459 tests passing** on main after all merges.

## Open TODOs

- No major deferred items remaining. All equipment, agents, and card abilities are implemented.
- Minor: Orb-Weaver Chelicerae cost reduction done. Trap-Door play-from-banish done.
- Phase 6 (permanents, tokens, Runechant, arcane from tokens) is next.
- Phase 7 (Talishar verification for Cindra vs Arakni) follows.

## Process Notes

- Skeptic CI workflows intentionally disabled (`if: false`) due to API token cost. Skeptic runs manually via agent spawns.
- Auto-merge doesn't check for approval — acceptable since skeptic runs pre-PR.
- Always rebase onto latest main between skeptic approval and PR creation (prevents merge conflicts).
- All PRs should include "Skeptic: CLEAN after N rounds" or "Skeptic: N/A" in the test plan.
