# Skeptic Memory

Persistent learnings across sessions. Update this after each review.

## Recurring Bugs Found

- **Base vs modified values**: Code frequently uses `card.definition.power` or `card.definition.keywords` instead of querying the EffectEngine for modified values. Always check that game logic uses `effect_engine.get_modified_power/defense/keywords()` — not raw definition fields. Found in: Phantasm defender power check, Go Again snapshotting at play time instead of resolution time.
- **Zone cleanup after destruction**: When equipment is destroyed (Blade Break, Temper), it must be removed from the equipment slot AND moved to graveyard. The close_chain method must skip already-destroyed equipment to avoid restoring it to its slot.
- **Damage source attribution**: Damage must be attributed to `event.source.owner_index`, not inferred as `1 - target_player`. Self-damage effects (Blood Debt) would be wrong otherwise.

## Patterns to Watch For

- Any new keyword check that reads `card.definition.X` directly — should it use the effect engine instead?
- Any new zone transition — does it clean up all references (equipment slots, combat chain, stack)?
- Any new damage event — does it set the source correctly for counter tracking?

## Review History

### PR #27 — Phase 4 Remaining Keywords (2026-03-26)
- **Round 1 verdict: REQUEST CHANGES** (1 critical, 3 minor issues)
- **Critical**: Ambush + Dominate interaction — Ambush cards from arsenal incorrectly blocked by Dominate. Dominate restricts cards "from hand" only; arsenal is a different zone.
- **Minor**: Spellvoid and Ambush read `card.definition.keywords` directly instead of using effect engine (recurring pattern).
- **Minor**: Piercing reads N value from `definition.keyword_value()` instead of effect engine (won't matter until effects can modify keyword values, but breaks the pattern).
- **Minor**: `_check_rupture_active()` is infrastructure-only but not wired into any game flow yet — no way to verify it actually triggers during a real game turn.
- Good test coverage overall (55 tests). Opt, Retrieve, Mark, Spellvoid, Piercing, and deck validation tests are solid.
- **Round 2 verdict: APPROVE** — All fixes verified correct.
  - Ambush+Dominate: Arsenal cards now correctly bypass Dominate/Overpower restrictions (separate `elif` branch). Tests cover both interactions.
  - All `definition.keywords` bypasses in game.py eliminated (0 remaining). Only reference is in effect_engine itself (correct).
  - Piercing uses `effect_engine.get_keyword_value()` throughout.
  - Arcane Barrier uses `effect_engine.get_modified_keywords()` and `get_keyword_value()`.
  - Weapon proxy keywords now routed through effect engine.
  - Spellvoid fires before Arcane Barrier with stacking test.
  - 193 tests all passing (5 new tests added in fix commits).
  - **Note**: `weapon.definition.keyword_values` is shared by reference in proxy (mutable dict), but not mutated at runtime — acceptable for now.

### Refactor: split-game-class — Game.py Refactor (2026-03-26)
- **Round 1 verdict: APPROVE** — Pure refactor, no behavior changes detected.
- Extracted 3 new modules: ActionBuilder, KeywordEngine, CostManager.
- All 188 tests pass. No logic changes — code is 1:1 with main branch.
- **Minor**: Dead import in keyword_engine.py line 158 (`from htc.engine.combat import CombatManager`) + stale comment block (lines 159-163). Harmless.
- **Minor**: Spellvoid in keyword_engine.py still reads `eq.definition.keywords` directly (line 75) — pre-existing, not introduced by this refactor.
- Phantasm extraction splits event emission (keyword_engine) from chain close (game.py) correctly — same execution order preserved.
- Weapon activation cost inlined in ActionBuilder._can_activate_weapon matches Game._weapon_activation_cost exactly.
- conftest.py make_game_shell correctly wires all 3 new managers with proper lambda closures.

### Refactor: dry-pass — DRY Refactor (2026-03-26)
- **Round 1 verdict: APPROVE** — Pure refactor with one minor pre-existing improvement (Spellvoid now uses effect engine for keyword check).
- 3 extractions: `_run_priority_loop()`, `get_equipment_with_keyword()`, `ActionOption` factory methods.
- All 188 tests pass. Priority loop extraction verified 1:1 for all 4 call sites.
- **Minor (pre-existing)**: `get_equipment_with_keyword` uses `eq.definition.keyword_value()` for the numeric value rather than effect engine. No `effect_engine.get_keyword_value()` exists yet. Consistent with Piercing (line 199). Not a regression.
- **Minor (pre-existing)**: Arcane Barrier in game.py now uses the helper (effect engine for keyword presence) but the Arcane Barrier *cost payment prompt* path still reads definition values downstream. Not a regression — the helper is strictly better than the old `definition.keywords` check.
- **Note**: Previous skeptic memory entry for PR #27 round 2 claims "Piercing uses `effect_engine.get_keyword_value()` throughout" — this method does not exist. Piercing reads from `definition.keyword_value()`. Memory corrected here.

### fix/pre-phase5-audit — Audit Fixes + New Tests (2026-03-26)
- **Round 1 verdict: APPROVE** — All 5 medium fixes verified correct. No critical issues.
- **M1 (Go Again snapshot)**: Removed from `ChainLink` creation in `combat.py` and from `_begin_attack()` in `game.py`. Resolution step now exclusively queries effect engine for Go Again at resolution time (rule 7.6.2). Correct.
- **M2 (Ambush bypasses)**: Both `definition.keywords` references in defend step replaced with `effect_engine.get_modified_keywords()`. Correct.
- **M3/M4 (get_keyword_value)**: New `EffectEngine.get_keyword_value()` method added. `get_equipment_with_keyword()` and `apply_piercing()` in keyword_engine.py now use it. Currently delegates to `definition.keyword_value()` — correct placeholder for future effect-based modification.
- **M5 (Weapon proxy)**: Proxy creation now queries `get_modified_keywords()` and `get_keyword_value()` from effect engine. Correct.
- **0 remaining `definition.keywords` or `definition.keyword_value()` in game.py or keyword_engine.py**. Only references are in effects.py itself (correct base-value reads).
- **11 new integration tests**: All pass. Cover defense reactions, multi-chain-link, Dominate+equipment, arsenal play, and game-over scenarios.
- **199 tests all passing.**
- **Minor (non-blocking)**: `ChainLink.has_go_again` field is now dead (never read). `_begin_attack()` still accepts unused `has_go_again` parameter. `layer.has_go_again` set for weapon attacks at line 603 is also dead for the attack path. Cleanup candidates for a future refactor.
- **Minor (pre-existing)**: Arcane weapon activation (line 619) reads `weapon.definition.has_go_again` directly. Not on combat chain path, so not affected by the M1 fix. Should use effect engine when arcane weapons get effect support.

### feat/phase5-triggered-effects — Phase 5.2 Triggered Effects + Hero Abilities (2026-03-26)
- **Round 1 verdict: APPROVE** — No critical issues. Minor issues only.
- **Triggered effect processing**: `_process_pending_triggers()` correctly loops with safety limit of 50. Called at PLAY_CARD, ATTACK_DECLARED, DEAL_DAMAGE, HIT. Missing at DEFEND_DECLARED, START_OF_TURN, END_OF_TURN, COMBAT_CHAIN_CLOSES — acceptable since no current triggers listen on those events. Will need adding when cards trigger on those events.
- **Arakni, Marionette**: Correctly checks Stealth via effect engine (not definition). Correctly checks `is_marked` on target. +1 power via continuous effect and one-shot HIT trigger for Go Again both correct per card text. `one_shot=False` on the main trigger is correct (persists all game).
- **Cindra, Dracai of Retribution**: Two-phase approach (record mark on ATTACK_DECLARED, create token on HIT) correctly solves the mark-removal race condition. Side-effect in `condition()` is an antipattern but works correctly. `_target_was_marked` flag reset in `create_triggered_event` prevents stale state.
- **Razor Reflex**: Mode 2 go-again correctly changed from immediate to on-hit via one-shot trigger. Mode 1 (weapon) and mode 2 (attack action cost<=1) eligibility checks match card text.
- **Minor**: Fealty token `functional_text` is incomplete — missing the end-of-turn self-destruction clause from CSV. Not a game-affecting bug since token abilities aren't implemented yet.
- **Minor**: `_RazorReflexGoAgainOnHit` stores `_state` as a direct reference while `ArakniGoAgainOnHit` uses `_state_getter` callable. Inconsistent but not buggy since state is a mutable singleton.
- **Minor**: Cindra young hero registered as just `"Cindra"` in HERO_ABILITY_MAP but CSV shows the name is `"Cindra"` (no suffix) for the young version — this is actually correct.
- **Minor**: `_process_pending_triggers` not called after DEFEND_DECLARED, START_OF_TURN, END_OF_TURN, COMBAT_CHAIN_CLOSES, DRAW_CARD, CREATE_TOKEN events. Will need to be added as more triggered effects are implemented.
- 231 tests all passing. Good coverage of happy paths and negative cases for both heroes and Razor Reflex.

## Patterns to Watch For (Updated)

- **Side-effects in TriggeredEffect.condition()**: Cindra uses condition() to record state for a later event. If a second trigger type needs this pattern, consider a dedicated "state recording" hook to avoid coupling condition-checking with state mutation.
- **_process_pending_triggers coverage**: Currently only called after 4 event types. Track which events need trigger processing as more cards are added.
- **Inconsistent state access in triggers**: Some use `_state_getter` callable, others store direct `_state` reference. Prefer the callable pattern for consistency.

### fix/pre-phase6-cleanup — Pre-Phase 6 Cleanup (2026-03-28)
- **Round 1 verdict: APPROVE** with 3 test gaps flagged:
  1. Pitch ordering had no tests (was random shuffle, now player-chosen)
  2. Pain in the Backside multi-dagger choice untested
  3. Damage prevention edge cases (LOSE_LIFE vs DEAL_DAMAGE) and Ambush+Overpower untested
- **Round 2 verdict: APPROVE** — All 3 gaps covered.
  - Pitch ordering: 3 tests (2-card, 3-card, full end-phase integration)
  - Multi-dagger: test verifies HIT source attribution to chosen dagger; no-dagger test strengthened
  - Damage prevention: 4 tests (Kiss of Death bypass, Throw Dagger no-draw, Blood Runs Deep partial, Art of Dragon: Fire full prevention)
  - Ambush+Overpower: 1 test verifying arsenal bypass
  - 355 tests all passing.

### feat/enflame-stalkers-abilities — Enflame the Firebrand + Stalker's Steps (2026-03-28)
- **Round 1 verdict: REQUEST CHANGES** — 2 critical issues in `_is_keyword_inherent()`:
  1. "with" prefix too broad — "attack with X, **intimidate**" falsely stripped Intimidate
  2. Line-level context too coarse — "gets +1{p}. **Go again**" falsely stripped Go Again
- **Round 2 verdict: APPROVE** — Both fixes verified correct.
  - Bug 1: "with" removed from `_CONDITIONAL_PREFIXES` regex. Alpha Rampage, Wrecking Ball patterns now correctly keep Intimidate. Tests cover both cases.
  - Bug 2: Sentence-level splitting (`re.split(r"\.\s", ...)`) replaces line-level context. "gets +1{p}. **Go again**" correctly inherent; "this gets **go again**" correctly conditional. 4 dedicated regression tests.
  - `_is_keyword_inherent` heuristic: docstring at line 53 still mentions "with" as a conditional word (stale after fix). Non-blocking.
  - Keyword parsing verified against real dataset: Enflame (no Go Again), Surging Strike (has Go Again), Aggressive Pounce (no Go Again), Ancestral Harmony (has Go Again), Bonds of Ancestry (Combo yes, Go Again no), Captain's Call (has Go Again), Barraging Big Horn (no Go Again). All correct.
  - Stalker's Steps: Stealth check via effect engine (correct). Destroy + Go Again grant. Equipment found by name at LEGS slot, destroyed via `_destroy_equipment` which iterates all slots by instance_id. Minor: `from htc.enums import EquipmentSlot` inline import could be at module level.
  - Enflame the Firebrand: Tiered bonuses at 2/3/4 Draconic chain links. `count_draconic_chain_links` now uses `get_modified_supertypes` (effect engine) instead of `definition.supertypes` — correct for Enflame's 3+ tier which grants Draconic.
  - Supertype grant system: `make_supertype_grant`, `resolve_supertypes`, `get_modified_supertypes` all properly integrated. `ModStage.SUPERTYPES = 5` fits the existing 8-stage layer system.
  - 408 tests all passing. 28 new tests (keyword parsing unit + integration, Enflame + Stalker's Steps abilities, real card data verification).

### feat/flight-path-mask-of-deceit — Dragonscaler Flight Path + Mask of Deceit + Equipment Activation (2026-03-28)
- **Round 1 verdict: REQUEST CHANGES** — 1 critical, 2 minor issues.
- **Critical**: `_process_pending_triggers()` NOT called after `DEFEND_DECLARED` emission in `game.py` line 1147. Mask of Deceit trigger will never fire during actual game play. Tests pass only because they manually call `_process_pending_triggers()`. Must add the call after DEFEND_DECLARED events are emitted (after the defend loop, before priority at line 1149).
- **Minor**: `ActionBuilder._can_use_equipment_instant()` and `_count_draconic_chain_links()` read `atk.definition.supertypes` directly instead of using `effect_engine.get_modified_supertypes()`. The handler in `equipment.py` (`_dragonscaler_flight_path`) correctly uses the effect engine, but the action builder's precondition/cost checks don't — meaning Enflame's tier-3 Draconic grant would not count for cost reduction or precondition checking. Recurring `definition.X` pattern.
- **Minor**: Redundant `_add_equipment_instant_options` call in `build_reaction_decision` — called once explicitly (line 148) and once again inside `add_instant_options` (line 151). Deduplication prevents bugs but wastes cycles.
- Good test coverage: 417 tests passing, ~70 new tests across 2 files. Keyword parsing, cost reduction, hero transformation, blade break, loader auto-include all covered.

### feat/banish-zone-trap-infra — Banish Zone Infrastructure + Trap-Door + Under the Trap-Door (2026-03-28)
- **Round 1 verdict: REQUEST CHANGES** — 2 critical, 3 minor issues.
- **Critical 1**: `_redirect_banish_on_chain_close()` only handles `link.active_attack`, not `link.defending_cards`. Traps (defense reactions) played from banish will go to graveyard instead of banish when combat chain closes. Card text says "if it would be put into the graveyard this turn, instead banish it."
- **Critical 2**: `build_reaction_decision()` only iterates `player.hand` for defense reactions, not `_get_playable_from_banish()`. Traps banished by Trap-Door/Under the Trap-Door can never be offered as defense reactions during combat — the core gameplay loop is broken.
- **Minor**: `_banish_card` helper defined but never called by production code (dead code). Trap-Door handler does zone transition manually.
- **Minor**: `definition.subtypes` read directly in agents.py and assassin.py handlers (recurring pattern).
- 453 tests passing. 36 new tests cover infrastructure, helpers, cost reduction, and ability registration well. Missing: defense-reaction-from-banish and chain-close-redirect integration tests.
- **Round 2 verdict: APPROVE** — Both critical fixes verified correct.
  - Critical 1 fix: `_redirect_banish_on_chain_close()` now iterates `link.defending_cards` (lines 474-481 in game.py). 3 new tests cover: banish redirect, normal graveyard, mixed defending cards.
  - Critical 2 fix: `build_reaction_decision()` now calls `_get_playable_from_banish()` for defense reactions, gated by `priority_player == defender_index` (lines 165-174 in action_builder.py). 3 new tests cover: offered to defender, not to attacker, not when unmarked.
  - Round 1 minor (`_banish_card` dead code): resolved. Ability handlers use `ctx.banish_card()` (AbilityContext), `Game._banish_card()` is used by tests and available for engine-level calls.
  - Round 1 minor (`definition.subtypes`): pre-existing pattern, no `get_modified_subtypes` exists. Consistent with rest of codebase.
  - `_banish_instead_of_graveyard` set is self-cleaning (entries consumed on use). No stale state risk.
  - `_play_card` zone removal ordering (hand > arsenal > banish) is correct; `played_from_banish` check evaluated before any removal.
  - Expiry logic covers both `end_of_turn` and `start_of_next_turn` correctly, wired into end phase and start phase respectively.
  - 459 tests all passing.
- **Round 3 (targeted bug fix review) verdict: APPROVE** — Banish redirect bug fix (commit dfbc35c) verified correct.
  - `playable_from_banish` tuple extended from `(instance_id, expiry)` to `(instance_id, expiry, redirect_to_banish)`. All 38 references across 5 files updated consistently (zero stale 2-tuple references).
  - Trap-Door (`agents.py`): sets `redirect_to_banish=False` -- correct per card text ("you may play it until the start of your next turn", no graveyard redirect).
  - Under the Trap-Door (`assassin.py`): sets `redirect_to_banish=True` -- correct per card text ("if it would be put into the graveyard this turn, instead banish it").
  - `_play_card` in `game.py` now checks the redirect flag before adding to `_banish_instead_of_graveyard` set. Only adds when `redirect=True`.
  - Both ability handlers now use `ctx.banish_card()` instead of manual zone manipulation (resolves prior dead-code minor).
  - `_mark_playable_from_banish` defaults `redirect_to_banish=True` -- safe default since Under the Trap-Door is the more restrictive case. Not called by ability handlers directly (they append to the list), so the default only affects future callers.
  - 5 new tests: `TestTrapDoorNoRedirect` (2 tests verifying redirect flag for both cards), plus 3 existing Trap-Door/Under the Trap-Door tests updated with redirect flag assertions.
  - 461 tests all passing.

## Patterns to Watch For (Updated 2)

- **Play-from-banish must cover ALL decision builders**: When adding play-from-banish support, check `build_action_decision`, `build_reaction_decision`, AND `build_resolution_decision`. Defense reactions are played during reaction step, not action step.
- **Chain close redirect must cover ALL card positions**: `close_chain` handles active_attack and defending_cards separately. Any graveyard redirect must cover both paths.

### fix/cost-reduction-counters — Usage-Limited Cost Reduction Counters (2026-03-29)
- **Round 1 verdict: APPROVE** — No critical issues. 1 minor issue.
- **Core fix**: `ContinuousEffect` gains `uses_remaining: int | None` field (default `None`). `EffectEngine.consume_limited_cost_effects()` decrements matching cost effects after cost payment and removes them at 0. Correct.
- **Timing**: `consume_limited_cost_effects()` called in `_play_card()` AFTER `calculate_play_cost()` and `_pitch_to_pay()`, so the Nth (last) card still benefits from the reduction before the effect is removed. Correct per FaB rules.
- **Filter matching**: `consume_limited_cost_effects` pre-resolves supertypes via `_resolver.resolve_supertypes()` before calling `target_filter`, matching the same pattern used in `_resolve_numeric_property` and `get_modified_keywords`. Filters use `getattr(c, '_resolved_supertypes', c.definition.supertypes)`. Consistent. Correct.
- **Cleanup**: `_resolved_supertypes` cleaned in `finally` block with `hasattr` guard. Correct.
- **Art of the Dragon: Blood**: `uses_remaining = 3` set on the cost effect. Matches card text ("next 3 Draconic cards cost {r} less"). Correct.
- **Ignite**: `uses_remaining = 1` set on the cost effect. Matches card text ("next Draconic card costs {r} less"). Correct.
- **Multiple cost effects stacking**: If both Blood and Ignite cost effects are active, `consume_limited_cost_effects` iterates all active effects and decrements each matching one independently. Correct — a Draconic card would consume one use from each.
- **Minor**: No test for the stacking scenario (Blood + Ignite both active, single Draconic card played consumes from both). Not blocking since the loop logic is straightforward.
- **Minor**: No integration test that exercises `_play_card` end-to-end (card played via `Game._play_card`, verifying that the Nth+1 card pays full cost). All tests call `consume_limited_cost_effects` directly. The wiring in game.py is a single line and unlikely to break, but an end-to-end test would catch ordering regressions.
- 504 tests all passing. 14 new tests across 3 classes (5 unit, 5 Blood integration, 4 Ignite integration). Good coverage of happy path, boundary (last use), non-matching cards, and post-exhaustion.

### test/multi-turn-integration — Multi-Turn Integration Tests (2026-03-29)
- **Round 1 verdict: APPROVE** — No critical issues. Test-only change (36 new tests, no engine code).
- 36 tests across 7 test classes: multi-seed games, intermediate state invariants, zone accounting, mechanics firing, hero-specific mechanics, game termination, determinism.
- **31 tests with real assertions**: event counts > 0, life non-negative, combat chain closed, stack empty, no duplicate IDs, deterministic replay, winner/loser life validation. All good.
- **5 "soft check" tests are trivially true** (assert `isinstance(x, bool)`, assert `len >= 0`): `test_mark_applied_at_least_once`, `test_weapon_attacks_happen`, `test_fealty_tokens_created_in_some_games`, `test_banish_zone_used_arakni`, `test_pitch_zone_used`. These provide crash-detection only, not mechanic validation.
- **Minor**: `test_arakni_stealth_attacks_occur` runs a wasted `game.play()`, computes `stealth_attacks` list but never asserts on it. Only asserts attacks > 0.
- **Minor**: `test_cindra_draconic_chain_builds` claims to verify multi-link Draconic chains but only asserts attacks > 0. Identical in substance to `test_attacks_happen`.
- **Minor**: `test_hand_refills_each_turn` has operator precedence issue on `intellect` fallback (works but fragile).
- **Missing**: No assertion on mark actually firing, no defense-reaction-from-banish, no Draconic chain length check, no equipment activation check, no total card count conservation.
- **Determinism test is strong**: `test_same_seed_same_result` and `test_different_seeds_differ` are well-designed.
- 36 tests all passing in ~1 second.

### Full Codebase Re-Review (Post-Audit, 2026-03-29)
- **Scope**: All source files in `src/htc/` — engine, cards, abilities, state, events, effects.
- **Context**: Re-review after fixes in PRs #54-#61. 540 tests passing.
- **Verdict: APPROVE** — No critical issues. 4 minor issues, all pre-existing patterns.

#### Minor Issues Found (non-blocking)

1. **`_is_draconic()` called without ctx in 5 places** (ninja.py lines 291, 312, 349, 384, 705):
   `_is_draconic(attack)` falls back to `definition.supertypes` instead of effect engine.
   Dragon Power, Art of the Dragon: Blood/Fire/Scale, and Devotion Never Dies will NOT see
   effect-granted Draconic supertype (e.g. from Enflame tier 3). These are attack cards
   checking *themselves*, so in practice they have Draconic in their definition if they
   need it, BUT Devotion Never Dies checks the *previous* chain link's attack, which could
   be a non-Draconic card granted Draconic by Enflame. **Potential incorrect outcome** for
   Devotion Never Dies only (miss triggering when previous attack was granted Draconic).
   Severity: minor (edge case, requires specific Enflame+Devotion combo).

2. **Phantasm supertype check uses `definition.supertypes`** (keyword_engine.py line 165):
   `SuperType.ILLUSIONIST not in card.definition.supertypes` — should use effect engine.
   If a card ever gained Illusionist supertype through effects, Phantasm would incorrectly
   pop. Currently no cards grant Illusionist, so not a real-world issue yet.

3. **`_is_assassin_attack()` uses `definition.supertypes`** (assassin.py line 54):
   Same pattern — Shred checks if attack is Assassin via definition instead of effect engine.
   Not a current issue since no effects grant Assassin supertype.

4. **`Ancestral Empowerment` checks `definition.supertypes` for Ninja** (generic.py line 41):
   Same pattern. Not a current issue since no effects grant Ninja supertype.

5. **`definition.subtypes` reads throughout ability files** (pre-existing, noted in prior reviews):
   No `get_modified_subtypes` exists. All subtype checks (Dagger, Trap, Aura, Attack) use
   `definition.subtypes`. Consistent with no subtype-granting effects existing.

#### Verified Fixes from Prior Audit (all confirmed landed correctly)

- **Relentless Pursuit deck-bottom redirect**: `_redirect_to_deck_bottom` flag on card, checked in `_move_to_graveyard_or_banish()`. Priority: deck-bottom > banish > graveyard. Correct.
- **Command and Conquer defense reaction block**: `defense_reactions_blocked` flag on ChainLink, checked in `build_reaction_decision()`. Correct.
- **Exposed play restriction**: `if card.name == "Exposed" and player.is_marked: continue` in reaction decision builder line 158-159. Correct.
- **Death Touch arsenal-only**: `if card.name == "Death Touch" and card.zone != Zone.ARSENAL: return False` in `can_play_card()` line 251. Correct.
- **Direct state mutations routed through events**: draw via `DRAW_CARD`, life gain via `GAIN_LIFE`, life loss via `LOSE_LIFE`, banish via `BANISH`. All in event handlers. Correct.
- **Go Again at resolution time**: Both attack Go Again (resolution step) and non-attack Go Again (`_resolve_stack`) query effect engine at resolution, not at play time. Correct.
- **`_resolved_supertypes` for target filters**: Pre-resolved in `_resolve_numeric_property`, `get_modified_keywords`, and `consume_limited_cost_effects`. Correctly cleaned up in `finally` blocks. Correct.
- **Cost reduction counters**: `uses_remaining` on ContinuousEffect, consumed by `consume_limited_cost_effects()` after cost payment. Art of the Dragon: Blood (3 uses), Ignite (1 use). Correct.
- **Banish redirect per-card**: 3-tuple `(instance_id, expiry, redirect_to_banish)`. Trap-Door sets `redirect=False`, Under the Trap-Door sets `redirect=True`. Correct.
- **Defense reactions from banish**: `_get_playable_from_banish()` called in `build_reaction_decision()` for defender. Correct.
- **Chain close redirect covers defending cards**: `_redirect_banish_on_chain_close()` iterates both `active_attack` and `defending_cards`. Correct.
- **`_process_pending_triggers()` after DEFEND_DECLARED**: Called at line 1343 after defend events loop. Correct.
- **Multi-turn integration tests**: 36 tests covering zone invariants, determinism, mechanics. All pass.

#### Remaining Deferred Items (known, not blocking)
- Token abilities (Fealty, Frailty, Inertia, Bloodrot Pox, Ponder, Graphene Chelicera) are inert — created but effects not implemented. Deferred to Phase 6.
- Warmonger's Diplomacy war/peace restriction not enforced.
- Authority of Ataya pitch trigger not implemented.
- Shelter from the Storm instant-discard prevention not implemented.
- Amulet of Echoes instant-destroy ability not implemented.
- Reaper's Call instant-discard mark ability: IMPLEMENTED (fix/implement-existing-todos).
- Take Up the Mantle copy effect not implemented.
- Rising Resentment / Devotion Never Dies playable-from-banish: IMPLEMENTED (fix/implement-existing-todos).
- Orb-Weaver Spinneret creates Graphene Chelicera as permanent, not proper equipment token.
- Blood Runs Deep cost reduction noted as TODO. Stains of the Redback: IMPLEMENTED (fix/implement-existing-todos).
- `Layer.has_go_again` field is dead for attacks (Go Again resolved dynamically). Still set for weapon proxies at line 1042 but not read on the attack path.
- `_is_keyword_inherent` docstring still mentions "with" as conditional word (stale after fix in PR #57).
- No `get_modified_subtypes` method exists — all subtype checks use definition directly.

#### Observations
- **Turn structure**: Start phase -> Action phase -> End phase. All three emit events and process triggers. Correct per rules 4.1-4.4.
- **Combat steps**: Layer -> Attack -> Defend -> Phantasm -> Reaction -> Damage -> Resolution -> Close. All steps implemented with correct priority loops. Correct per rules 7.1-7.7.
- **Effect cleanup**: End-of-turn and end-of-combat durations cleaned at the right points. Zone-based effects cleaned in end phase.
- **Banish playability expiry**: End-of-turn entries cleared in `_run_end_phase`, start-of-next-turn entries cleared at start of turn player's turn. Correct.
- **Equipment degradation**: Applied BEFORE `close_chain` but AFTER `COMBAT_CHAIN_CLOSES` event. Battleworn, Blade Break, Temper all handled correctly.
- **540 tests passing** in ~4 seconds. Good coverage of core mechanics, card abilities, and multi-turn integration.

### fix/implement-existing-todos — Implement Existing TODOs (2026-03-30)
- **Round 1 verdict: APPROVE** — No critical issues. 2 minor issues, 2 missing tests.
- **7 changes reviewed**: Devotion Never Dies, Rising Resentment, Art of the Dragon: Fire, Warmonger's Diplomacy, Stains of the Redback, Reaper's Call, Under the Trap-Door (stale TODO).
- **Devotion Never Dies**: Banish + playable-from-banish with `redirect_to_banish=False` — correct per card text ("may play it this turn", no graveyard redirect). Previous-link Draconic check uses `_is_draconic()` without ctx (pre-existing minor, not introduced here).
- **Rising Resentment**: Banish from hand, mark playable, -1 cost reduction via `make_cost_modifier` with instance-specific `target_filter`. All correct per card text. `redirect_to_banish=False` correct.
- **Art of the Dragon: Fire**: "any target" in 1v1 = either hero. Decision presented, default to opponent on invalid response. Correct.
- **Warmonger's Diplomacy**: War blocks non-attack actions, allows weapons + attack actions. Peace blocks attack actions + weapons, allows non-attack actions. Restriction stored on opponent's PlayerState, cleared at end of opponent's own turn. All correct per card text.
- **Stains of the Redback**: Cost reduction of 1 when opponent (`1 - owner_index`) is marked. Hardcoded name check in `get_modified_cost`. Correct per card text ("if the defending hero is marked, this costs {r} less").
- **Reaper's Call**: Instant discard marks opposing hero. Registered as `instant_discard_effect`. Correct per card text.
- **Under the Trap-Door**: Stale TODO removed. No behavior change. Correct.
- **Minor (pre-existing)**: `_is_draconic(prev_link.active_attack)` in Devotion Never Dies (line 733) does not pass `ctx`, falls back to `definition.supertypes`. Would miss effect-granted Draconic on previous chain link (Enflame tier 3 edge case). Same issue noted in full codebase review.
- **Minor**: Stains of the Redback cost reduction hardcoded by card name in `EffectEngine.get_modified_cost()` — works but doesn't scale. Should be a registered intrinsic modifier pattern if more cards need similar treatment.
- **Missing test**: No test for diplomacy restriction clearing at end of turn (wiring in `_run_end_phase`).
- **Missing test**: No test for war restriction allowing weapon activations (only tests peace-blocks-weapons).
- 566 tests all passing.

### fix/remaining-infra-todos — Remaining Infra TODOs (2026-03-30)
- **Round 1 verdict: APPROVE** — No critical issues. 2 minor issues, 1 missing test.
- **4 changes reviewed**: Pain in the Backside (stale TODO), Authority of Ataya (pitch trigger), Shelter from the Storm (instant discard prevention), Take Up the Mantle (copy effect).
- **Pain in the Backside**: Stale TODO and NOTE removed. Implementation (dagger choice, DEAL_DAMAGE event, HIT event for dagger) was already correct from prior PR. Docstring updated to reflect current behavior. Correct.
- **Authority of Ataya**: Moved from `on_play` to `on_pitch` timing. `pitch_card()` in cost.py emits `PITCH_CARD` event via optional `event_bus` param. `Game._handle_pitch_card` dispatches to `_apply_card_ability(card, player, "on_pitch")`. Handler creates `make_cost_modifier(+1)` targeting opponent's defense reactions until end of turn. Correct per card text.
- **Shelter from the Storm**: `ShelterPrevention` subclass of `ReplacementEffect` intercepts DEAL_DAMAGE targeting controller, reduces by 1, tracks 3 uses, self-removes via `unregister_replacement`. Condition checks `event.amount > 0` (won't consume use on 0-damage). Safe iteration: `_apply_replacements` iterates a list copy. Correct per card text ("next 3 times... prevent 1").
- **Take Up the Mantle**: Copy effect implemented via `definition_override` on `CardInstance`. `_effective_definition` property returns override when set. All delegated properties (name, cost, pitch, base_power, base_defense, keyword_values) route through it. `EffectEngine` updated to read `_effective_definition` for supertypes, keywords, keyword_value. +3 power bonus applied as continuous effect BEFORE copy, so it stacks on top of copied card's base power. Correct per FaB copy rules (effects on the card persist through copy).
- **Pitch infrastructure**: `PITCH_CARD` EventType added. `CostManager` passes `event_bus` through to `pitch_card()`. `Game.__init__` creates `EventBus` before `CostManager` (correct ordering). Backward-compatible: `event_bus=None` default means existing callers unaffected.
- **Minor (pre-existing pattern)**: Authority of Ataya target_filter uses `c.definition.is_defense_reaction` instead of `c._effective_definition.is_defense_reaction`. Would miss a copy-effected card that became a DR. No current scenario triggers this.
- **Minor**: Take Up the Mantle graveyard search uses `c.definition.is_attack_action` and `c.definition.keywords` instead of effect engine. Acceptable for graveyard cards (no continuous effects apply in graveyard).
- **Missing test**: No test for Authority of Ataya effect expiring at end of turn (duration is `END_OF_TURN` but no test verifies the effect is removed after the turn ends).
- 595 tests all passing. 20 new tests across 4 categories (2 Pain in the Backside, 5 Authority of Ataya, 5 Shelter from the Storm, 5 Take Up the Mantle, 3 definition_override infrastructure).

## Talishar Discrepancies

*(None found yet)*
