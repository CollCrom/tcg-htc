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

### 2026-03-29: Full Codebase Audit + Fixes (PRs #52-#61)

- **Trap-Door banish redirect bug** (PR #52). Only Under the Trap-Door should redirect to banish, not Trap-Door demi-hero. Extended `playable_from_banish` tuple to `(id, expiry, redirect_to_banish)`.
- **Git workflow docs** (PR #53). Codified: start from clean main, rebase before push, PRs auto-merge.
- **Relentless Pursuit deck-bottom redirect** (PR #54). Flag was set but engine never read it. Added check in `_move_to_graveyard_or_banish`.
- **Play restrictions** (PR #55, #58). Command and Conquer blocks defense reactions, Exposed blocked when marked, Death Touch arsenal-only (user corrected: not banish).
- **Direct state mutations** (PR #56). Routed draw, life gain, banish through event system across 7 ability handlers.
- **Go Again snapshot** (PR #57). Non-attack cards now query effect engine at resolution, matching attack card pattern.
- **Target filter context** (PR #59). Pre-resolves supertypes so cost/power filters see Enflame's Draconic grant.
- **Cost reduction counters** (PR #60). Art of the Dragon: Blood (3 uses), Ignite (1 use) via `uses_remaining` on ContinuousEffect.
- **Multi-turn integration tests** (PR #61). 36 tests running full Arakni vs Cindra games.
- **Full codebase re-review: CLEAN.** No critical issues. 540 tests passing.
- **Don't use parallel worktrees** for Python builds — causes import path confusion. Build PRs sequentially.

## Open TODOs

- Phase 6 (permanents, tokens, Runechant, arcane from tokens) is next. Token abilities (Fealty, Frailty, Inertia, Bloodrot Pox, Ponder) are deferred here.
- Phase 7 (Talishar verification for Cindra vs Arakni) follows.
- Minor: Devotion Never Dies `_is_draconic()` call doesn't use effect engine (Enflame edge case).
- Minor: Several card abilities partially implemented with TODOs (Warmonger's Diplomacy, Authority of Ataya, etc).
- Minor: `Layer.has_go_again` is dead code, cleanup candidate.

## Process Notes

- Skeptic CI workflows intentionally disabled (`if: false`) due to API token cost. Skeptic runs manually via agent spawns.
- Auto-merge handles squash + branch delete — don't ask about merging.
- Always start from clean main (`git checkout main && git pull`) before creating branches.
- Always rebase onto latest main between skeptic approval and PR creation.
- Build PRs sequentially, not in parallel worktrees (Python import issues).
- All PRs should include "Skeptic: CLEAN after N rounds" or "Skeptic: N/A" in the test plan.
