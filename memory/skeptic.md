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

## Talishar Discrepancies

*(None found yet)*
