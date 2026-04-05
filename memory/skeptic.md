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

### feat/phase6-token-abilities — Phase 6 Token Abilities (2026-03-30)
- **Round 1 verdict: REQUEST CHANGES** — 1 critical issue.
- **Critical**: `game.py` tracked Draconic card plays for Fealty end-phase condition using `card.definition.supertypes` instead of `self.effect_engine.get_modified_supertypes()`. Cards granted Draconic by Fealty's instant ability would not be recognized as Draconic, breaking Fealty's end-phase survival condition.
- **Minor**: `_fealty_instant` set `effect.uses_remaining = 1` on a supertype grant, but `uses_remaining` only works for cost modifiers (consumed by `consume_limited_cost_effects`). The closure-based `consumed` flag already handled single-use correctly, so `uses_remaining` was dead/misleading.
- **Round 2 verdict: APPROVE** — Both fixes verified correct.
  - Critical fix: `game.py` line 804 now uses `self.effect_engine.get_modified_supertypes(self.state, card)` for Draconic tracking. Correct.
  - Minor fix: Dead `uses_remaining = 1` replaced with explanatory comment. Correct.
  - `git diff main..HEAD -- '*.py' | grep 'definition.supertypes'` returns zero hits — no new `definition.supertypes` references introduced by this branch.
  - Pre-existing `definition.supertypes` references (ninja.py, equipment.py, keyword_engine.py, generic.py, assassin.py) are unchanged and documented in prior review.
  - `_is_draconic_attack` in equipment.py uses `definition.supertypes` but is dead code (defined, never called).
  - 658 tests all passing.

#### Remaining Deferred Items (known, not blocking)
- Token abilities: ALL 7 tokens now have abilities implemented (Phase 6 complete).
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

### feat/pregame-equipment-selection — Pre-Game Equipment Selection (2026-03-30)
- **Round 1 verdict: APPROVE** — No critical issues. No minor issues.
- **Rule 4.1.4**: "Each player selects arena-cards from their card-pool for equipment zones." Implementation correctly groups equipment by slot, auto-selects uncontested slots, and presents CHOOSE_EQUIPMENT decision for contested slots.
- **Slot grouping**: Uses existing `_equipment_slot()` method (HEAD/CHEST/ARMS/LEGS subtypes). Stable iteration via enum order.
- **Decision flow**: `min_selections=1, max_selections=1` per contested slot. Action IDs use `equip_{name}` pattern. Fallback to first option on invalid response.
- **Backward compatibility**: `_build_player_state` accepts `selected_equipment: list[str] | None = None`. Existing callers and `make_game_shell` unaffected.
- **RandomPlayer**: Updated to handle CHOOSE_EQUIPMENT in the single-option branch. Correct.
- **Test coverage**: 9 new tests covering auto-select, multi-option, specific choices, player state integration, RandomPlayer, empty pool, action ID format, Cindra decklist, per-player independence.
- 878 tests all passing.

### refactor/dry-pass (round 2) — DRY Refactor (2026-03-30)
- **Round 1 verdict: REQUEST CHANGES** — 1 critical issue (4 guard downgrades).
- **Critical**: 4 functions changed from `@require_active_attack` to `@require_chain_link`, losing the `link.active_attack is None` guard. All 4 access `link.active_attack` in their body and will crash with `AttributeError` if `active_attack` is `None`:
  1. `_overcrowded_on_attack` (assassin.py line 1152)
  2. `_devotion_never_dies_on_hit` (ninja.py line 633)
  3. `_enlightened_strike_on_attack` (ninja.py line 784)
  4. `_enflame_the_firebrand_on_attack` (ninja.py line 1005)
  All 4 must use `@require_active_attack` to match the original behavior.
- **Minor (non-blocking)**: `_ScarTissueMarkOnHit` had `isinstance(state, GameState)` defensive check; the shared `MarkOnHitTrigger` drops it. In practice `_state` is always `GameState` (passed as `ctx.state`). The ninja `_MarkOnHitTrigger` also lacked this check. Consistent with ninja version, acceptable.
- **Correct**: All other extractions verified 1:1 with original behavior:
  - `require_active_attack` / `require_chain_link` decorators match the original guard patterns for all other call sites.
  - `choose_dagger` / `deal_dagger_damage` / `destroy_arsenal` helpers preserve exact behavior (event emission, logging, dagger selection).
  - `MarkOnHitTrigger` shared class correctly parameterized by `card_name`.
  - `_draconic_devotion_handler` factory preserves Demonstrate Devotion / Display Loyalty behavior exactly.
  - `BanishPlayability` NamedTuple is backward-compatible with tuple unpacking.
  - Expiry constants replace string literals consistently.
  - `_all_zone_lists()` / `_expire_playable()` / `_redirect_to_banish()` helpers preserve exact behavior.
  - Validation `_check_legendary_copies` inner function preserves logic.
  - Test refactoring (`make_ability_context`, `setup_draconic_chain`, parametrized hero tests) preserve all assertions.
- 598 tests passing.

### fix/skeptic-audit-findings — Skeptic Audit Fixes (2026-03-30)
- **Round 1 verdict: APPROVE** — No critical issues. 2 minor issues, 2 missing tests.
- **5 changes reviewed**: Spreading Flames (effect engine for supertypes), Blood Runs Deep (intrinsic cost modifier), Leave No Witnesses (Contract + Silver token), Amulet of Echoes (permanent instant activation), Fyendal's Spring Tunic (player agency).
- **Spreading Flames**: Closure correctly captures `effect_engine` from `ctx.effect_engine`. Uses `effect_engine.get_modified_supertypes(state, lnk.active_attack)` instead of `getattr(_resolved_supertypes, definition.supertypes)`. Correct — effect-granted Draconic (e.g. Enflame tier 3) is now visible to the filter.
- **Blood Runs Deep**: Intrinsic cost modifier registered via `register_ninja_cost_modifiers(effect_engine)`. Modifier iterates chain links, counts Draconic via `effect_engine.get_modified_supertypes()`, subtracts count from cost. `get_modified_cost` applies `max(0, result)` after intrinsic modifiers — cost floor is correct. Card data shows cost=2, test helper defaults to cost=3 — acceptable for testing.
- **Leave No Witnesses Contract**: On-hit collects banished cards, checks `card.definition.color == Color.RED`, creates Silver token for controller. Correct for on-hit scope. Silver token `functional_text` is wrong: code says "Action - Destroy Silver: Gain {r}" but actual Silver token text is "Action - {r}{r}{r}, destroy Silver: Draw a card. Go again". Non-blocking since token abilities are inert (Phase 6 deferred).
- **Amulet of Echoes**: New `permanent_instant_effect` timing added to AbilityRegistry. `_add_permanent_instant_options` iterates player permanents with registered handlers. Precondition checks `state.players[opponent_index].turn_counters.has_duplicate_card_name()`. `card_names_played` tracked in `_play_card` and cleared by `TurnCounters.reset()` (via `__init__` re-invocation with `field(default_factory=list)`). Handler destroys amulet, forces opponent to discard 2 (with choice). All correct.
- **Fyendal's Spring Tunic**: Auto-spend removed from `SpringTunicTrigger.create_triggered_event()`. New `equipment_instant_effect` handler removes 3 energy counters and grants 1 resource. Precondition checks `energy >= 3`. Resource cost is 0 (counter removal is the cost). Trigger `condition()` returns `False` at 3+ counters (won't add beyond 3). All correct per card text.
- **Infrastructure**: `_is_permanent_instant_activation` + `_activate_permanent_instant` in game.py correctly route activate actions through the new permanent instant path. Decision routing in `_handle_action_phase_decision` checks equipment first, then permanent instant, then weapon. Correct priority.
- **Minor**: Silver token `functional_text` does not match actual card text (see above). Non-blocking — token abilities are Phase 6 deferred.
- **Minor**: Contract implementation is scoped to on-hit banishes only. The Contract keyword in FaB is a global trigger ("whenever you banish an opponent's red card by any means"). Other cards that banish opponent cards (e.g. Trap-Door, Under the Trap-Door) would not trigger the contract. Acceptable simplification for 1v1 with current card pool — Leave No Witnesses' own on-hit is the primary banish source.
- **Missing test**: No test for `card_names_played` being cleared at turn reset (TurnCounters.reset()). The `__init__` re-invocation pattern is correct but a regression test would catch if new fields with default_factory are added incorrectly.
- **Missing test**: No end-to-end test for permanent instant activation through `_handle_action_phase_decision` (all tests call `_activate_permanent_instant` directly). The routing in game.py line 727 (`_is_permanent_instant_activation` check) is untested.
- 624 tests all passing. 26 new tests across 5 categories.

### fix/final-skeptic-cleanup — Consumed-Closure Fixes + Overpower (2026-03-30)
- **Round 2 verdict: REQUEST CHANGES** — 1 critical issue found in Part B sweep.
- **Part A (3 prior fixes verified correct)**:
  - **Dagger attack bonus** (assassin.py `_grant_next_dagger_attack_bonus`): `applied_to: set[int]` pattern correctly records first matching instance_id, returns True idempotently for same card, returns False for new cards. Multiple evaluation safe. Correct.
  - **Fealty Draconic grant** (tokens.py `_fealty_instant`): `granted_id: list[int | None]` pattern correctly locks to first matching instance_id, checks `card.instance_id == granted_id[0]` for all subsequent evaluations. Multiple evaluation safe. Correct.
  - **Overpower arsenal restriction** (game.py `_defend_step`): Arsenal Ambush action cards now checked against `action_cards_defended >= 1` and incremented if `is_action`. Correct per rule 8.3.9 — no "from hand" qualifier.
  - All 3 fixes have comprehensive test coverage (516 new lines in test_consumed_closure_fixes.py, updated test in test_post_phase5_audit.py).
  - No remaining `consumed = [False]` patterns in codebase (verified via grep).
- **Part B (full sweep, new findings)**:
  - **Critical**: Orb-Weaver Spinneret (`assassin.py` lines 754-771) — card text says "Your **next** attack with stealth this turn gets +N{p}" but `stealth_attack_filter` matches ALL stealth attacks on the combat chain, not just the first. No single-use tracking (no `applied_to`/`granted_id` pattern, no `uses_remaining`). Multiple stealth attacks after Orb-Weaver Spinneret all get the bonus instead of just the first. Same class of bug as the original consumed-closure issue.
  - **Trigger cleanup**: No leaks. One-shot triggers auto-remove via `_check_triggers`. Permanent triggers (hero abilities, equipment) correctly persist. `EventBus.clear_expired()` exists as infrastructure but isn't needed with current trigger lifetimes. `EventBus.clear()` available for full reset. No turn-scoped non-one-shot triggers exist to leak.
  - **Combat chain close sequence**: Correct ordering — COMBAT_CHAIN_CLOSES event -> process triggers -> equipment degradation -> banish redirect -> close_chain -> cleanup END_OF_COMBAT effects.
  - **Resource/pitch handling**: Resource points reset at action phase start (line 573-574) and end phase (line 1830-1831). Pitch-to-pay correctly loops until sufficient resources. `pay_resource_cost` correctly deducts. No edge cases found.
  - **Action builder**: Correct offering of hand + arsenal + banish cards for actions. Reactions correctly limited (attack reactions to attacker, defense reactions to defender). Equipment instants, permanent instants, instant-discard all offered. No illegal actions offered.
- 669 tests all passing.

### Retroactive Audit: PRs #76-83 (shipped without skeptic review, 2026-03-30)
- **Scope**: 10 gameplay changes across 7 files. 888 tests passing. No prior skeptic review.
- **Verdict: REQUEST CHANGES** — 2 critical issues, 1 minor issue.

#### Critical Issues

1. **Warmonger's Diplomacy: controller restriction never applies (PR #76)**
   Card text: "each hero chooses war or peace. [restriction] next turn."
   Both players' restrictions are stored immediately on `PlayerState.diplomacy_restriction`.
   Restriction is cleared in `_run_end_phase()` via `tp.diplomacy_restriction = None` (only clears turn player).
   For the **opponent**: set on controller's turn, active during opponent's turn, cleared at end of opponent's turn. **Correct.**
   For the **controller**: set on controller's turn, cleared at end of controller's OWN turn (same turn it was set), never active during controller's NEXT turn. **Bug — controller restriction is a no-op.**
   File: `src/htc/engine/game.py` line 1867 (clearing), `src/htc/cards/abilities/ninja.py` line 218 (setting).
   Fix: Track which turn each player's restriction should expire. Could use a `diplomacy_restriction_turn` counter, or defer setting the controller's restriction until their next turn starts.

2. **Shelter from the Storm: expires on wrong player's end-of-turn (PR #76)**
   Card text: "The next 3 times you would be dealt damage **this turn**, prevent 1 of that damage."
   Expiry handler: `if event.target_player == controller` on END_OF_TURN.
   Shelter is a defense reaction — played on the **opponent's** turn. END_OF_TURN fires with `target_player = turn_player_index` (the opponent). The check `event.target_player == controller` does NOT match during the opponent's end phase. The prevention persists into the controller's own turn and expires at end of THAT turn.
   File: `src/htc/cards/abilities/generic.py` lines 326-331.
   Fix: Change `event.target_player == controller` to match the turn player at the time the card was played (i.e., track `current_turn_player` at play time and expire when that player's turn ends), OR simply expire at the next END_OF_TURN regardless of target_player.

#### Minor Issues

3. **Return-to-brood `skip_first` causes one-turn-late reversion (PR #79/82)**
   `_return_to_brood` handler is registered AFTER handlers have already run for the current END_OF_TURN event (registered during trigger processing in `_check_triggers`). The handler can never fire on the event that caused its registration. `skip_first` therefore skips the NEXT matching end phase (Arakni's next turn), causing return-to-brood to happen one Arakni-turn too late.
   Sequence: Transform at Turn X end phase -> handler registered -> Turn X+2 (Arakni's next turn) skip_first consumed -> Turn X+4 (Arakni's turn after that) return-to-brood fires.
   Should be: Transform at Turn X -> return at Turn X+2.
   File: `src/htc/engine/game.py` lines 499-520.
   Fix: Remove `skip_first` logic entirely. The handler is already safe from firing during the current event.
   **Severity downgrade consideration**: This may be minor rather than critical depending on whether the `_process_pending_triggers` call after `emit()` in `_run_end_phase` could re-enter event processing. If so, skip_first might be needed but should skip differently. Marking as minor pending confirmation of execution order.

#### Correct

- **Attack reaction target validation (PR #76)**: Correctly validates dagger, stealth, Ninja, Assassin, and off-chain dagger requirements for hand-played reactions. Proxy source check for dagger weapons is correct. `_can_play_attack_reaction` placement in `build_reaction_decision` is correct.
- **Weapon proxy exclusion (PR #76)**: `attack.is_proxy` checks correctly added for Tide Flippers, Blacktek Whisperers, Take Up the Mantle, Ancestral Empowerment. Weapon attacks (proxies) should not match "attack action card" requirements.
- **Arakni end-phase transformation trigger (PR #76)**: `ArakniEndPhaseTranformTrigger` correctly checks: own end phase, opponent is marked, demi-heroes available. `one_shot=False` correct (persists all game). Direct call to `_become_agent_of_chaos` rather than returning a triggered event is unorthodox but functional.
- **Demi-heroes loading (PR #77)**: Auto-inclusion of 6 Agent of Chaos demi-heroes for Arakni, Marionette in both loader and test parser. Correct.
- **Return-to-brood mechanism (PR #79)**: `_become_agent_of_chaos` saves `original_hero`, registers return-to-brood handler. Handler reverts hero and sets `returned_to_brood_this_turn`. Core mechanism is correct (timing issue aside).
- **No re-transform after return-to-brood (PR #82)**: `returned_to_brood_this_turn` flag checked in `ArakniEndPhaseTranformTrigger.condition()`. Cleared by `TurnCounters.reset()` at turn start. Correct — prevents infinite transform/revert loop.
- **Weapon slot limit for Graphene Chelicera (PR #80)**: `_count_weapon_hand_slots` correctly counts 1H=1, 2H=2. Max 2 hand slots. Returns False if full. Correct.
- **Codex of Frailty/Inertia player choice (PR #81)**: When hand has >1 card, presents CHOOSE_MODE decision with all hand cards. Fallback to first card on invalid response. Correct — player should choose which card to discard.
- **Weapon attack log shows modified power (PR #83)**: `effect_engine.get_modified_power(state, proxy)` instead of `weapon.base_power`. Correct (displays actual damage, not base).

#### Missing Tests

- No test verifying controller's own Warmonger's Diplomacy restriction persists to their next turn.
- No test verifying Shelter from the Storm expires when played as a defense reaction (opponent's turn ends).
- No test verifying return-to-brood fires exactly one Arakni-turn after transformation.
- No test verifying Graphene Chelicera creation fails when 2H weapon equipped.
- No test for Codex discard choice when hand has exactly 2 cards (boundary).

### fix/todo-cleanup — TODO Cleanup (24 items) (2026-04-04)
- **Round 1 verdict: REQUEST CHANGES** — 1 critical issue, 2 minor issues.
- **Round 2 verdict: APPROVE** — Critical fix verified correct.
  - `_LeaveNoWitnessesContractTrigger` now stores `_event_bus_getter` and `_effect_engine_getter` callables (lines 1071-1072).
  - `create_triggered_event` resolves both getters with null-safe checks and passes to `_create_silver_token` (lines 1089-1091).
  - Trigger instantiation in `_leave_no_witnesses_on_attack` captures `ctx.events` and `ctx.effect_engine` via default-arg lambdas (lines 1118-1119), consistent with existing `_state_getter` pattern.
  - No new issues introduced. 959 tests all passing.

#### Critical Issues

1. **Contract trigger creates Silver tokens without event bus** (assassin.py `_LeaveNoWitnessesContractTrigger.create_triggered_event`):
   The Contract trigger calls `_create_silver_token(state, self.controller_index)` without passing `event_bus` or `effect_engine`. This means:
   - No `CREATE_TOKEN` event is emitted for Contract-created Silver tokens
   - No continuous effects are registered for the Silver token (if any were needed)
   - Any triggers listening for CREATE_TOKEN (which this branch adds `_process_pending_triggers()` calls for) will not fire
   The old code in on_hit passed `event_bus=ctx.events, effect_engine=ctx.effect_engine`.
   Fix: Store event_bus/effect_engine references in the trigger class (via getters), or restructure so Contract token creation flows through the game engine's event system.

#### Minor Issues (non-blocking)

1. **New `definition.keywords` bypass in Orb-Weaver instant** (agents.py line 152):
   `Keyword.STEALTH in card.definition.keywords` should use effect engine. Currently no effects grant Stealth, so no wrong outcomes, but violates the established pattern. Consistent with pre-existing Spinneret code (assassin.py line 796) which has the same bypass.

2. **Contract trigger accumulation (ambiguous — needs user clarification)**: The trigger is registered on_attack and persists forever (`one_shot=False`). If Leave No Witnesses attacks 3 times (3 copies), 3 independent Contract triggers accumulate. Each banish of a red card creates 3 Silver tokens. This may be correct if each card copy has its own independent Contract, or wrong if Contract is a single global ability. FaB expert should confirm whether multiple copies of the same Contract should stack.

#### Correct

- **Frailty arsenal-only fix** (tokens.py): Frailty functional_text says "Your attack action cards **played from arsenal** and weapon attacks have -1{p}." The `played_from_zone == Zone.ARSENAL` check is correct per card text. `played_from_zone` tracking in game.py is set at the right point in `_play_card`. Tests cover both arsenal (debuffed) and hand (not debuffed) paths.
- **`played_from_zone` tracking** (instance.py + game.py): New field on CardInstance, set after zone detection but before stack addition. Uses existing `played_from_arsenal`/`played_from_banish` booleans. Correct.
- **`_state_getter` callable standardization**: All 7 trigger classes migrated from `_state: object` to `_state_getter: callable`. Each uses `_get_state()` helper with null/callable guard. Correct.
- **`Layer.has_go_again` removal** (game_state.py + stack.py + game.py): Dead field removed. Go Again is resolved dynamically via effect engine at resolution time (line 1709-1713). Weapon proxies inherit Go Again keyword via proxy creation. Correct.
- **`_is_draconic_attack` dead code removal** (equipment.py): Function was defined but never called (noted in prior reviews). Removed cleanly.
- **Phantasm supertype fix** (keyword_engine.py line 165): Now uses `self.effect_engine.get_modified_supertypes(state, card)` instead of `card.definition.supertypes`. Fixes previously noted minor issue.
- **`_is_assassin_attack` effect engine** (assassin.py): Now takes optional `ctx` parameter. Shred call site passes ctx. Backward-compatible fallback for callers without ctx. Correct.
- **Ancestral Empowerment supertype fix** (generic.py line 422): Now uses `ctx.effect_engine.get_modified_supertypes(ctx.state, attack)` instead of `attack.definition.supertypes`. Fixes previously noted minor issue.
- **Authority of Ataya `_effective_definition`** (ninja.py line 479): Target filter now uses `c._effective_definition.is_defense_reaction` instead of `c.definition.is_defense_reaction`. Correct for copy effect support.
- **Hunter's Klaive deduplication** (equipment.py): Removed separate `_hunters_klaive_on_hit` handler. Mark is already handled by the Mark keyword handler in game.py (`_handle_hit_mark_keyword`). This eliminates duplicate mark logging. Correct.
- **Stale docstring fix** (card_db.py): Docstring for `_is_keyword_inherent` updated to note "with" is not conditional. Matches code behavior after prior fix.
- **`get_modified_subtypes` infrastructure** (continuous.py + effects.py): Follows same pattern as `get_modified_supertypes` — `resolve_subtypes` in StagingResolver, `get_modified_subtypes` in EffectEngine. Uses `ModStage.TYPES` (stage 4). `subtypes_to_add` field on ContinuousEffect. Correct.
- **`_process_pending_triggers()` after DRAW_CARD** (game.py line 1998): Added inside `_draw_cards` loop. Tests verify triggers fire per draw.
- **`_process_pending_triggers()` after CREATE_TOKEN** (game.py line 483): Added after Fealty token creation. Test verifies trigger fires.
- **Graphene Chelicera 2H weapon guard**: Tests cover 2H (fails), 1x 1H (succeeds), 2x 1H (fails).
- **Orb-Weaver hero instant** (agents.py): `hero_instant_effect` timing added to AbilityRegistry. Handler creates Graphene Chelicera + +3 power to next Stealth attack. `make_once_filter` ensures single-use. Duration END_OF_TURN. Correct per card text.

#### Missing Tests

- No test verifying Contract does NOT create multiple Silver tokens per banish when Leave No Witnesses has attacked multiple times (the accumulation bug).
- No test verifying Silver token creation from Contract emits CREATE_TOKEN event.
- No end-to-end test for Orb-Weaver hero instant through game flow (ActionBuilder offering, discard cost, execution).

#### Test Coverage

- 14 new tests in `test_todo_cleanup.py` covering items 18-24.
- Updated tests in `test_token_abilities.py` (Frailty), `test_skeptic_audit_fixes.py` (Contract), `test_full_game.py` (Hunter's Klaive), `test_weapon_attacks.py` (Go Again), `test_post_phase5_audit.py` (state_getter).
- 959 tests all passing.

### fix/stealth-effective-definition — Stealth keyword check in target_filters (2026-04-04)
- **Round 1 verdict: APPROVE** — No critical issues. No minor issues.
- **Scope**: 2-line change in `agents.py` (line 152) and `assassin.py` (line 795). Both Orb-Weaver Stealth target_filters changed from `card.definition.keywords` to `card._effective_definition.keywords`.
- **Why not full effect engine**: `get_modified_keywords()` sets/deletes `_resolved_supertypes` on the card, which conflicts when the target_filter is evaluated during `_resolve_numeric_property` (power resolution). Re-entrancy would corrupt the `_resolved_supertypes` temporary attribute. Confirmed by code inspection (effects.py lines 121-134 vs 205-224).
- **Why `_effective_definition`**: Handles copy effects (Take Up the Mantle `definition_override`). No effects currently grant Stealth, so equivalent to full effect engine for all current cards.
- **Pattern note**: This is the same approach used by `get_modified_keywords()` itself (line 124), `get_modified_supertypes()` (line 108), and other effect engine methods — they all read from `_effective_definition` as their base value.
- **Remaining `definition.keywords` Stealth check**: `assassin.py` line 314 (Take Up the Mantle graveyard search) still uses `definition.keywords`. Acceptable — graveyard cards have no active continuous effects, so `definition` is correct there.
- 959 tests all passing.

### refactor/dry-pass-3 — DRY Refactor Pass 3 (2026-04-04)
- **Round 1 verdict: APPROVE** — Pure refactor, zero behavior changes. No critical or minor issues.
- **Scope**: 6 extractions across 8 files (_helpers.py, assassin.py, equipment.py, generic.py, heroes.py, ninja.py, tokens.py, abilities.py).
- **`get_player_name(state, player_index)`**: Replaces 10+ inline `hero.definition.name.split(",")[0]` patterns. All call sites verified 1:1 with original, including null-state guards in Cindra/Arakni triggers and `TokenEndPhaseTrigger._player_name`. New `_pname_from_player_state` in equipment.py correctly handles `register_equipment_triggers` which receives `PlayerState` (not `GameState`).
- **`move_card(card, from_list, to_list, new_zone)`**: Replaces 10 sites of 3-line remove/set-zone/append pattern. All call sites verified — no adjacent side effects skipped (each site's surrounding code preserved unchanged).
- **`is_dagger_attack()`**: Unified from assassin.py and equipment.py. Both originals were logically identical (only difference: type annotation `CardInstance | None` vs bare `attack`). Unified version uses the more explicit annotation. All 5 call sites in assassin.py and 1 in equipment.py correctly updated.
- **`make_instance_id_filter(target_id)`**: Replaces 12 `lambda c, _id=X: c.instance_id == _id` patterns. Default-arg binding (`_id=target_id`) correctly preserved in the factory, preventing late-binding bugs. All call sites pass `instance_id` eagerly (not a deferred expression).
- **`choose_card()` generalization**: `choose_dagger()` now delegates to `choose_card()` with `id_prefix="dagger"`. The `id_prefix` is used in `action_id` formatting and response parsing (`replace(f"{id_prefix}_", "")`). Behavior preserved exactly — same auto-pick for single candidate, same Decision/ActionOption construction, same fallback on parse failure.
- **`grant_power_bonus()` for Tarantula Toxin mode1**: Original 5-line `make_power_modifier` + `add_continuous_effect` replaced with existing `grant_power_bonus` helper (which does exactly those 2 calls). Parameters verified identical (bonus, controller, source, END_OF_COMBAT duration, target filter).
- **No circular imports**: Verified by import test.
- **959 tests all passing.**

### Full Codebase Review (Gate Review, 2026-04-04)
- **Scope**: All source files in `src/htc/` — 959 tests passing, 200 stress tests passing.
- **Verdict: APPROVE** — No critical issues. 5 minor issues (3 pre-existing, 2 newly identified). No regressions.

#### Prior Critical Issues — All Resolved

1. **Warmonger's Diplomacy controller restriction (PR #76 retroactive audit)**: FIXED. Uses `diplomacy_restriction_expires_turn` with turn-number-based expiry. Controller expires at `turn_number + 2`, opponent at `turn_number + 1`. Clearing logic in `_run_end_phase` at line 1903-1909 checks `self.state.turn_number >= tp.diplomacy_restriction_expires_turn`. Correct.
2. **Shelter from the Storm wrong-player expiry (PR #76 retroactive audit)**: FIXED. Expires on first END_OF_TURN regardless of target_player (lines 340-347). `expired = [False]` flag ensures single-fire.
3. **Return-to-brood timing (PR #79/82 retroactive audit)**: FIXED. `skip_first` removed. Handler registered after END_OF_TURN iteration, filters by `event.target_player == player_index`. Fires on controller's next end phase. Comment at line 520-526 correctly explains.
4. **Orb-Weaver Spinneret "next attack" multi-hit (Part B sweep)**: FIXED. Now uses `make_once_filter` (line 773) which records first matching instance_id.
5. **`_is_draconic()` called without ctx**: ALL call sites now pass `ctx` (lines 286, 306, 341, 406, 648). Effect engine path used for all Draconic checks.
6. **Phantasm supertype check**: FIXED. Now uses `self.effect_engine.get_modified_supertypes()` (keyword_engine.py line 165).
7. **`_is_assassin_attack()` definition bypass**: FIXED. Now takes optional `ctx` parameter with effect engine fallback.
8. **Ancestral Empowerment supertype check**: FIXED. Now uses `ctx.effect_engine.get_modified_supertypes()`.

#### Minor Issues (non-blocking)

1. **Warmonger's Diplomacy controller restriction immediate activation**: Controller's restriction is set during their own turn and is immediately active for the rest of that turn. Card text says "next turn" — restriction should not apply to the current turn. In practice, Warmonger's Diplomacy has Go Again, so the controller could have remaining actions this turn that are incorrectly restricted. Fix: track a `restriction_starts_turn` field alongside `expires_turn`, or defer setting controller's restriction until their next turn start.
   File: `src/htc/cards/abilities/ninja.py` line 221, `src/htc/engine/action_builder.py` line 266.

2. **Arcane damage DEAL_DAMAGE missing `_process_pending_triggers()`** (game.py line 1017-1028): Arcane damage emits DEAL_DAMAGE but does not call `_process_pending_triggers()` afterward. No current triggers would fire on arcane DEAL_DAMAGE specifically, but if future cards trigger on any DEAL_DAMAGE, arcane damage would be missed.
   File: `src/htc/engine/game.py` line 1028.

3. **Weapon proxy supertypes use `definition.supertypes`** (game.py line 1342): Proxy inherits `weapon.definition.supertypes` instead of `get_modified_supertypes()`. No current effects grant supertypes to weapons, so no wrong outcomes.

4. **`definition.subtypes` throughout** (pre-existing, accepted): `get_modified_subtypes` infrastructure exists but is unused. All subtype checks read `definition.subtypes` directly. Consistent; no subtype-granting effects exist.

5. **Art of the Dragon: Scale defense check** (ninja.py line 500): Uses `chosen.definition.defense` instead of `effect_engine.get_modified_defense()`. The counter system is the only modification source for equipment defense currently, and it's accounted for manually. Would miss continuous-effect defense modifiers if any existed.

#### Verified Correct (key mechanics confirmed)

- **Effect engine staging**: Power, defense, cost, keywords, supertypes all resolve through `StagingResolver` with proper `_resolved_supertypes` pre-resolution for target_filter lambdas. Cleanup in `finally` blocks.
- **Trigger processing coverage**: `_process_pending_triggers()` called after: CREATE_TOKEN, BECOME_AGENT, START_OF_TURN, PLAY_CARD, ATTACK_DECLARED, DEFEND_DECLARED, DEAL_DAMAGE (combat), HIT, COMBAT_CHAIN_CLOSES, END_OF_TURN, DRAW_CARD. 12 of 14 emit sites covered (missing: BANISH, arcane DEAL_DAMAGE).
- **Combat chain close sequence**: COMBAT_CHAIN_CLOSES event -> triggers -> equipment degradation -> banish redirect -> close_chain -> cleanup. Correct.
- **Go Again resolution**: Dynamically queried at resolution time via effect engine (line 1709-1713). Not snapshotted. Correct per rule 7.6.2.
- **Banish playability**: 3-tuple `(instance_id, expiry, redirect_to_banish)`. Correct per-card redirect behavior.
- **Defense reactions from banish**: Offered in `build_reaction_decision()` for defender only. Correct.
- **Cost reduction counters**: `uses_remaining` consumed after cost payment. Floor clamp `max(0, result)`. Correct.
- **`make_once_filter` pattern**: Used by Orb-Weaver Spinneret, Orb-Weaver hero instant, Fealty Draconic grant, dagger attack bonus. Records first matching instance_id, idempotent on repeat evaluation. No consumed-closure bugs remain.
- **Return-to-brood**: Fires on controller's next end phase. `returned_to_brood_this_turn` prevents re-transform. Correct.
- **Shelter from the Storm**: Expires on first END_OF_TURN. 3-use prevention. Correct.
- **Warmonger's Diplomacy expiry**: Turn-number-based. Controller and opponent expire independently. Correct (minor: immediate activation noted above).
- **959 tests passing** in ~15 seconds. 200 stress tests passing in ~10 seconds.

#### Remaining Deferred Items (known, documented, not blocking)

- Contract trigger accumulation ambiguity (multiple Leave No Witnesses copies).
- Silver token `functional_text` does not match actual card text.
- Orb-Weaver creates Graphene Chelicera as weapon, not proper equipment token.
- BANISH event has no `_process_pending_triggers()` call (no current triggers on BANISH).
- START_OF_ACTION_PHASE event has no `_process_pending_triggers()` call (no current triggers).

### fix/skeptic-gate-minors — 5 Minor Issue Fixes (2026-04-04)
- **Round 1 verdict: APPROVE** — No critical issues. No minor issues. All 5 fixes correct.
- **Scope**: 5 minor issues from the full codebase gate review, across 10 source files + 1 test file.
- **Fix 1 (Warmonger's Diplomacy deferred restriction)**: New `diplomacy_restriction_active_turn` field on PlayerState. Controller's restriction activates at turn N+2, opponent's at N+1. Both `can_play_card` and `_can_activate_weapon` gate on `turn_number >= active_turn`. Turn math verified correct. 2 new tests.
- **Fix 2 (Arcane DEAL_DAMAGE trigger processing)**: `_process_pending_triggers()` added after arcane damage event emission. Forward-looking; no current triggers affected.
- **Fix 3 (Weapon proxy supertypes)**: Proxy creation now uses `get_modified_supertypes()` instead of `definition.supertypes`. Consistent with keyword handling.
- **Fix 4 (definition.subtypes routed through effect engine)**: Two patterns used correctly: `get_modified_subtypes()` in ability handlers/action_builder, `_effective_definition.subtypes` in target_filters (avoiding re-entrancy). All triggered effects gain `_effect_engine` field with null-safe guards. No circular imports.
- **Fix 5 (Art of Dragon: Scale defense)**: Uses `get_modified_defense()` which already includes counter values. No double-counting.
- **961 tests all passing.**

#### Remaining Deferred Items (updated — 5 items resolved)

- ~~Warmonger's Diplomacy controller immediate-activation~~ — FIXED (fix/skeptic-gate-minors).
- ~~Arcane damage missing trigger processing~~ — FIXED (fix/skeptic-gate-minors).
- ~~Weapon proxy supertypes from definition~~ — FIXED (fix/skeptic-gate-minors).
- ~~No `get_modified_subtypes` usage~~ — FIXED (fix/skeptic-gate-minors). Now used throughout ability files and action_builder.
- ~~Art of Dragon: Scale uses `definition.defense`~~ — FIXED (fix/skeptic-gate-minors).
- Contract trigger accumulation ambiguity (multiple Leave No Witnesses copies).
- Silver token `functional_text` does not match actual card text.
- Orb-Weaver creates Graphene Chelicera as weapon, not proper equipment token.
- BANISH event has no `_process_pending_triggers()` call (no current triggers on BANISH).
- START_OF_ACTION_PHASE event has no `_process_pending_triggers()` call (no current triggers).

### feat/scenario-test-viewer — Board State Snapshot Capture (2026-04-04)
- **Round 1 verdict: APPROVE** — No engine code changes. Pure tooling + test instrumentation.
- 5 files changed: `conftest.py` fixture, `scenario_recorder.py`, `scenario_viewer.py`, 2 instrumented test files, `.gitignore`.
- Zero changes to `htc/` engine code.
- ScenarioRecorder correctly wraps `capture_snapshot()` from `tools/snapshot.py`, passes `effect_engine`.
- Fixture is opt-in (parameter injection). 40 non-instrumented tests unaffected.
- `write()` runs in teardown after test body — no test pollution possible.
- Viewer handles missing snapshots gracefully (empty dict/list fallbacks).
- 961 tests all passing.

### feat/instrument-all-scenarios — Flick Knives Engine Fixes + Scenario Tooling (2026-04-04)
- **Round 1 verdict: APPROVE** — No critical issues. 1 minor issue (non-blocking).

#### Engine Changes Reviewed

1. **`link.hit = True` when Flick dagger deals damage** (equipment.py line 244):
   - Card text says "the dagger has hit" — this is a hit event. Strategy articles confirm: "dagger hit counts as chain-link hitting, preserves hit streak."
   - `link.hit` only read by `MaskOfMomentumTrigger.condition()` (line 155). No other consumers. No unintended side effects.
   - Both write sites (game.py:1657 main damage, equipment.py:244 Flick) are additive. No conflict.
   - **Correct.**

2. **Dispatching dagger's `on_hit` handler** (equipment.py lines 259-276):
   - Strategy article confirms: "Can be flicked by Flick Knives for bonus 2 damage (1 from flick + 1 from on-hit re-trigger)."
   - Lookup by `dagger.name`, new AbilityContext with `source_card=dagger`. Guards: `ability_registry is not None`, `on_hit_handler is not None`.
   - **Correct.**

3. **Graphene Chelicera no on_hit**: No registered handler. `lookup` returns `None`. Only Flick damage fires. **Correct.**

4. **`ability_registry` on `AbilityContext`** (abilities.py line 61): Optional field, default `None`. Single factory in game.py passes it. Test helper backward-compatible. No circular deps. **Correct.**

5. **HIT event side effects from Flick**: Mark removal (rules 9.3.3) and Mark keyword application both fire correctly on Flick's HIT event. **Correct — no unintended side effects.**

#### Minor Issues (non-blocking)

1. **Redundant inline import** (equipment.py line 262): `from htc.engine.abilities import AbilityContext as _AC` inside `_flick_knives`, but `AbilityContext` is already imported at module level. Style nit.

#### Test Coverage
- 7 new tests in `test_scenario_flick_interactions.py`. Rewritten `test_scenario_flick_mask.py` (engine-driven).
- 967 tests all passing.

## Talishar Discrepancies

*(None found yet)*
