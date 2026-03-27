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

## Talishar Discrepancies

*(None found yet)*
