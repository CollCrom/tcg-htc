# Test Generator Memory

Persistent learnings across sessions. Update this as you go.

## Session Learnings

### 2026-03-30: First batch of scenario tests (43 tests, 5 files)

- `make_game_shell()` creates a minimal Game but does NOT process pending triggers automatically. Triggered effects that return a `GameEvent` (like Mask of Momentum's DRAW_CARD) create pending triggers via `events.get_pending_triggers()`. To verify triggers fired, check `game.events.get_pending_triggers()` rather than expecting side effects (e.g. hand size change).
- `register_equipment_triggers()` needs `game=game` kwarg for Mask of Deceit (it calls `_become_agent_of_chaos`).
- `register_token_triggers()` takes `state` directly (not `state_getter`).
- HIT events emitted inside ability handlers (like Flick Knives) don't fire handlers registered at the test level — the EventBus handler iteration doesn't pick up handlers registered for nested event types during the same emit call. Use DEAL_DAMAGE handler or check pending triggers instead.
- For ActionBuilder target filter tests, call `_can_play_attack_reaction()` for hand-played reactions and `_can_use_equipment_reaction()` for equipment reactions directly — no need to build full action lists.

## Patterns for Test Construction

- **Equipment setup**: Set hero first, then assign equipment to `player.equipment[EquipmentSlot.X]`, then call `register_equipment_triggers()` with the player_state.
- **Combat chain**: Call `game.combat_mgr.open_chain(state)`, then `add_chain_link(state, attack, target_index)`. Set `link.hit = True` for prior links, `link.attack_source = weapon` for proxy attacks.
- **Token setup**: Create token, add to `player.permanents`, call `register_token_triggers()`.
- **Turn counter flags**: Set `player.turn_counters.fealty_created_this_turn` etc. directly for end-phase condition tests.
- **Agent of Chaos**: Set `player.demi_heroes = [list]` and register equipment triggers. Mock `game._ask` for choice tests.

## Scenarios That Caught Bugs

- No engine bugs found in this batch — all 43 tests pass. This validates that the core interactions work correctly:
  - Mask of Momentum consecutive hit tracking
  - Blood Splattered Vest stain counter + resource + self-destruct
  - Fealty activation Draconic grant (once-only filter)
  - Fealty end-phase survival conditions
  - Agent of Chaos transformation + return-to-brood lifecycle
  - Attack reaction target validation (dagger, stealth, Ninja, power checks)
  - Flick Knives dagger destruction and availability checks

## Test Files Created

- `tests/scenarios/test_scenario_flick_mask.py` — 6 tests (Flick + Mask + BSV)
- `tests/scenarios/test_scenario_fealty_economy.py` — 9 tests (Fealty lifecycle)
- `tests/scenarios/test_scenario_agent_of_chaos.py` — 8 tests (transformation + return-to-brood)
- `tests/scenarios/test_scenario_dagger_management.py` — 7 tests (dagger slots + Flick)
- `tests/scenarios/test_scenario_reaction_targets.py` — 13 tests (target validation)
