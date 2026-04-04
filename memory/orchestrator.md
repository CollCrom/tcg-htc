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

### 2026-03-30: TODO Cleanup + DRY Refactor + Full Audit + Phase 6 (PRs #63-#68)

- **Actionable TODOs fixed** (PR #63): Playable-from-banish (Devotion Never Dies, Rising Resentment), instant discard (Reaper's Call), Warmonger's Diplomacy enforcement, Stains of the Redback cost reduction, Art of the Dragon: Fire target choice.
- **Skeptic followups** (PR #64): `_is_draconic()` now uses effect engine for all 5 callers. Stains cost reduction moved to extensible `register_intrinsic_cost_modifier()` pattern.
- **New infrastructure TODOs** (PR #65): Pitch trigger system (Authority of Ataya), damage prevention via ReplacementEffect (Shelter from the Storm), card copy via `definition_override` (Take Up the Mantle).
- **DRY refactor** (PR #66): -488 lines. Guard decorators (`@require_active_attack`/`@require_chain_link`), shared helpers (choose_dagger, deal_dagger_damage, destroy_arsenal, MarkOnHitTrigger), BanishPlayability namedtuple, test fixture consolidation.
- **Full audit fixes** (PR #67): Spreading Flames dynamic filter uses effect engine, Blood Runs Deep cost reduction implemented, Contract keyword (Leave No Witnesses + Silver tokens), Amulet of Echoes permanent instant activation, Spring Tunic player agency restored.
- **Phase 6 complete** (PR #68): All 7 token abilities implemented — Fealty (instant + conditional end-phase), Frailty (continuous -1 power + end-phase destroy), Inertia (end-phase deck bottom), Bloodrot Pox (end-phase pay-or-damage), Ponder (end-phase draw), Silver (action activation), Graphene Chelicera (weapon token). New `permanent_action_effect` timing. 658 tests passing.
- **Recurring pattern**: `definition.supertypes` / `definition.keywords` bypasses continue to be the #1 bug class. Every new feature needs skeptic verification on this.

### 2026-03-30 (cont): Skeptic loop + DRY pass 2 + Phase 7 start (PRs #69-#74)

- **Consumed-closure bug class** (PR #69): `target_filter` closures with `consumed = [False]` side effects were consumed by display/cost queries before the actual effect resolution. Affected: dagger attack bonus (3 cards), Fealty Draconic grant, Orb-Weaver stealth bonus. Fixed with idempotent `applied_to: set[int]` / `granted_id` patterns. Extracted `make_once_filter()` helper.
- **Overpower fix** (PR #69): Arsenal Ambush action cards now correctly counted against Overpower restriction (no "from hand" qualifier).
- **DRY pass 2** (PR #70): -182 lines. `make_once_filter` helper, `TokenEndPhaseTrigger` base class, `_build_ability_context` extraction, test fixture consolidation.
- **Phase 7 stress tests** (PR #71): 200 full games (100 seeds × 2 player orders). Found Devotion Never Dies stale chain reference bug. 869 tests, 0 crashes.
- **Pre-game equipment selection** (PR #72): Players choose equipment per slot before game starts. `CHOOSE_EQUIPMENT` decision type.
- **Equipment reaction preconditions** (PR #73): Tide Flippers, Blacktek Whisperers, Stalker's Steps, Flick Knives now check target eligibility before being offered. Destruction reordered to be activation cost (before effect).
- **Once-per-turn vs tap separation** (PR #74): New `activated_this_turn` field on CardInstance. Weapons use this instead of `is_tapped` for once-per-turn. Matters for weapons with tap cost (Shield Beater) and untap effects.

### 2026-03-31 — 2026-04-01: Log review + gameplay fixes

- **Attack reaction target validation**: Hand-played attack reactions now check target requirements (dagger, stealth, Ninja, Assassin, off-chain dagger) before being offered. Found via log review — To the Point was played on non-dagger attacks.
- **FaB turn numbering**: Logs now use FaB convention — turn 0 is opening turn, both players share same turn number after that.
- **Log improvements**: Player names in all log lines (attacks, defends, hits, blocks, reactions, equipment). Hands shown at start of each turn. Pitching logged. Arsenal actions logged. Spring Tunic shows owner name.
- **Log review is high-value**: User reviewing game logs found Tide Flippers, Flick Knives, and To the Point bugs that 888 tests missed. Log review should be a standard phase after stress tests.

### 2026-03-31 — 2026-04-02: Log review + gameplay fixes + retroactive audit (PRs #75-84)

- **Player names in all logs** (PR #75): `player_name()` helper on AbilityContext, swept 70+ log messages.
- **Gameplay fixes from log review** (PR #76): Attack reaction target validation, weapon proxy exclusion, Warmonger's both players, Shelter end-of-turn expiry, Arakni end-phase transformation.
- **Demi-heroes loading** (PR #77): Test parser wasn't auto-including Agent of Chaos demi-heroes.
- **HTML game log viewer** (PR #78): `tools/log_to_html.py` — collapsible turns, life bars, icons.
- **Return-to-brood** (PR #79): Demi-heroes revert at controller's next end phase.
- **Weapon slot limit** (PR #80): Graphene Chelicera can't equip with full weapon slots.
- **Codex discard choice** (PR #81): Player chooses which card to discard (was auto-discarding hand[0]).
- **No re-transform after brood** (PR #82): `returned_to_brood_this_turn` flag prevents infinite transform loop.
- **Weapon log modified power** (PR #83): Shows proxy power after effects (Frailty -1 visible).
- **Retroactive skeptic audit** (PR #84): Caught 3 bugs in PRs #76-83:
  - Warmonger's Diplomacy: controller restriction never applied (cleared same turn). Fixed with `diplomacy_restriction_expires_turn`.
  - Shelter from the Storm: never expired (target_player check wrong). Fixed by removing the check.
  - Return-to-brood: `skip_first` caused one-turn-late reversion. Removed redundant flag.
- **Test Generator agent** created: 43 scenario tests across 5 files, all passing.
- **Strategy reference docs** saved: Arakni masterclass, Redline Cindra, Blue Cindra post-BNR.
- **CRITICAL LESSON**: Skeptic must ALWAYS run before PRs. "Skeptic: N/A" is never acceptable. PRs #76-83 shipped without review and had 2 critical bugs.

### 2026-04-02 — 2026-04-04: Board viewer + more gameplay fixes (PR #84 cont.)

- **Board state viewer** built (`tools/board_viewer.py`, `tools/snapshot.py`, `tools/demo_scenario.py`): Interactive HTML with keyboard nav, card components in all zones, combat chain with defenders, life bars, marked/diplomacy badges, banished zone, equipment activation highlighting.
- **Mark keyword handler**: Daggers with Mark (Klaive) now mark on ANY hit — not just proxy attacks. Fixes Pain in the Backside on-hit dagger not marking.
- **Mask of Deceit timing**: DEFEND_DECLARED events now fire AFTER all defenders committed, not mid-loop. Transformation happens after full defense.
- **Weapon slot limit at setup**: Max 2 hand slots enforced during `_build_player_state`.
- **Weapon count parsing**: "2x" prefix now duplicates weapons correctly.
- **Shelter/Pain log improvements**: Show damage source, remaining uses, dagger name.
- **Warmonger's Diplomacy UI**: WAR/PEACE badges in board viewer.
- **Banished zone**: Visible in board viewer with face-up/face-down indicators.
- 944 tests, skeptic approved.

## Open TODOs

- **NEXT SESSION: Wire board viewer into scenario tests.** The 43 scenario tests need to run through the board viewer so the user can visually step through each interaction and verify correctness. Currently the viewer only works on the demo game — need to instrument scenario tests to capture snapshots and generate viewable HTML.
- After that: build smarter AI player using strategy articles (ref/strategy-*.md).
- PR #85 is open and needs to merge first. Check CI.
- Minor: duplicate Hunter's Klaive on_hit log (keyword handler + registry both fire for proxy attacks). Harmless but noisy.
- Minor: Frailty -1 power applies to all attack actions, not just those played from arsenal (no `played_from_zone` tracking exists).
- Minor: Contract keyword scoped to on-hit banishes only (should be global trigger for any banish of opponent's red card).
- Minor: `Layer.has_go_again` is dead code, cleanup candidate.

## Process Notes

- Skeptic CI workflows intentionally disabled (`if: false`) due to API token cost. Skeptic runs manually via agent spawns.
- Auto-merge handles squash + branch delete — don't ask about merging.
- Always start from clean main (`git checkout main && git pull`) before creating branches.
- Always rebase onto latest main between skeptic approval and PR creation.
- Build PRs sequentially, not in parallel worktrees (Python import issues).
