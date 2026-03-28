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

## Open TODOs

- **Pitch order** (game.py ~line 1215): Player should choose pitch-to-bottom order per rules. Currently randomized. Low priority for AI play but matters for pitch-stacking strategies.
- **Deferred equipment**: Dragonscaler Flight Path (instant activation), Mask of Deceit (Agent of Chaos mechanic), Stalker's Steps (not in CSV).
- **Card ability TODOs**: Several cards have partial implementations with TODOs noted in code (instant activations, cost reductions, play restrictions). See builder memory for details.

## Process Notes

- Skeptic CI workflows intentionally disabled (`if: false`) due to API token cost. Skeptic runs manually via agent spawns.
- Auto-merge doesn't check for approval — acceptable since skeptic runs pre-PR.
- Always rebase onto latest main between skeptic approval and PR creation (prevents merge conflicts).
- All PRs should include "Skeptic: CLEAN after N rounds" or "Skeptic: N/A" in the test plan.
