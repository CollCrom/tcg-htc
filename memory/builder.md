# Builder Memory

Persistent learnings across sessions. Update this as you go.

## Decisions

- **CardDefinition (frozen) vs CardInstance (mutable)** — static card data from CSV is separated from per-game state (zone, counters, tapped, face_up). This keeps the CardDatabase as a shared read-only resource across games.
- **Decision/Response pattern** — the engine never does I/O. It builds a `Decision` with legal options and the player implementation returns a `PlayerResponse`. This makes AI simulation trivial (just implement `PlayerInterface.decide()`).
- **Single GameState tree** — all state in one object. Makes serialization, replay, and debugging straightforward.
- **Per-turn TurnCounters** — a typed dataclass tracking everything that happened this turn (attacks played, damage dealt, cards drawn, etc.). Resets each turn. Essential because many FaB cards check "if you've done X this turn."
- **Combat resolves inline** — for Phase 1, combat resolves immediately when an attack is played (no full stack/priority loop between combat steps yet). This simplification was necessary to get a working game loop quickly.
- **FaB Cube CSV as card data source** — 4,217 cards loaded from `data/cards.csv`. The `Types` field is a flat comma-separated list that we classify into CardType/SubType/SuperType using our enums. Keywords are parsed with number-stripping for things like "Ward 10" → Keyword.WARD.

## Gotchas

- **FaB Cube "Types" field is flat** — it mixes card types, subtypes, and supertypes in one comma-separated field. We built `classify_type_string()` to sort them into the right enum category. Some types in the CSV don't map to our enums (e.g. "Puffin", "Scurv", "Placeholder Card") — we silently skip these.
- **Numeric fields in CSV are strings** — cost, power, defense can be blank, "*", "X", or "XX". We parse with `_parse_int()` returning None for non-numeric values. Cards with X cost get `cost=None`.
- **Random player defense behavior matters a lot** — initial random player selected ALL legal defenders, which meant both players threw their entire hands every combat, ran out of cards, and the game stalled at turn 200. Fixed by capping random defense to 0-3 cards. This revealed that defender selection is a major gameplay lever.
- **Equipment defending is simplified** — currently equipment defends but doesn't return to its zone after combat (it stays on the chain then gets skipped during cleanup). Needs proper handling: equipment returns to its slot, non-equipment goes to graveyard.
- **Draw from deck uses `pop(0)`** — this is O(n). For production, consider `collections.deque` or reversing the deck so top = last element.

## Phase 4 Keyword Implementation Status (2026-03-26)

All 11 keywords for Cindra vs Arakni matchup implemented:
- **Mark** — `is_marked` on PlayerState, auto-removed on HIT by opponent (rules 9.3)
- **Stealth** — No engine rules meaning (keyword tag only, per rules 8.3)
- **Piercing N** — +N power when defended by equipment, via continuous effect
- **Ambush** — Arsenal cards with Ambush appear in defender options
- **Rupture** — Infrastructure check: `_check_rupture_active()` returns True at chain link >= 4
- **Spellvoid N** — One-shot arcane prevention, destroys equipment (before Arcane Barrier in pipeline)
- **Opt N** — `_perform_opt()` utility: look at top N, put any on bottom
- **Retrieve** — `_perform_retrieve()` utility: return card from graveyard with optional filter
- **Contract** — Keyword tag only (hero ability trigger is Phase 5)
- **Legendary** — Deck validation: max 1 copy (`decks/validation.py`)
- **Specialization** — Deck validation: hero name check heuristic (full parsing is Phase 5)

## Domain Notes

### FaB Rules — Key Engine Concepts (from comprehensive rules, 2026-03-19)

**Turn structure**: Start Phase → Action Phase (1 AP, priority loop) → End Phase (reset allies, arsenal, pitch cycles, untap, draw).

**Assets**: action points, resource points, life points, chi points. Chi can substitute for resource. Action points only available during your own action phase.

**Pitching**: move card from hand to pitch zone to gain resources (1/2/3 based on pitch value, red/yellow/blue).

**The stack**: LIFO. All players pass in succession → top layer resolves. Turn-player gains priority after each resolution.

**Combat chain**: opens when an attack is added to the stack. Steps: Layer → Attack → Defend → Reaction → Damage → Resolution → (continue or) Close.
- Active-attack's power vs. sum of defenders' defense. Hit = power > total defense. Damage = difference.
- Go again during Resolution Step = gain 1 action point = can attack again.
- Chain closes: all pass in Resolution Step, no valid targets, active-attack ceases to exist, or an effect closes it.

**Attack types**: attack-cards (card on chain), attack-proxies (weapon activations — inherit source properties except activated/resolution abilities), attack-layers (search-then-attack patterns).

**Defending**: hero's controller declares cards from hand + equipment. Equipment can defend. Defense reactions added during Reaction Step.

**Permanent vs. non-permanent deck-cards**: deck-cards are only permanent if they have a specific subtype (Affliction, Ally, Ash, Aura, Construct, Figment, Invocation, Item, Landmark). Most action cards are NOT permanents — they go to graveyard after resolving.

**Zone reset rule**: any object entering a zone outside the arena (and not the stack) becomes a new object with no relation to its previous existence.

**Tokens**: only exist in arena or as sub-cards; cease to exist if they leave arena.

**Counters**: modify properties of the object they're on. Diametrically opposing counters both remain (no cancellation).

**Continuous effects staging**: 8 stages for applying effects (copy → controller → name/color/text → types → supertypes → abilities → base numeric → numeric values). Timestamp order within stage.

## Pre-Phase 5 Audit (2026-03-26)

- **All keyword reads must go through EffectEngine** — never read `card.definition.keywords` or `card.definition.keyword_value()` directly in game logic. Use `effect_engine.get_modified_keywords()` and `effect_engine.get_keyword_value()`.
- **Go Again is purely dynamic at resolution** — removed early snapshots from `ChainLink` creation and `_begin_attack()`. Resolution step now uses effect engine exclusively. `ChainLink.has_go_again` field still exists (default False) but is unused for attacks; kept for potential future non-attack chain entries.
- **Weapon proxy inherits modified keywords** — `_create_attack_proxy()` now queries the effect engine for the weapon's modified keywords/values instead of copying raw definition data.
- **`EffectEngine.get_keyword_value()`** — new method added. Currently delegates to `card.definition.keyword_value()` but provides the hook point for future continuous effects that modify keyword N values (e.g. "your Arcane Barrier is increased by 1").
- **`_activate_attack_weapon` and `_activate_arcane_weapon` still use `weapon.definition.has_go_again`** for the stack layer — these are fine because attack go-again is resolved dynamically at resolution, and arcane weapons don't go through combat chain. But if we add effects that grant/remove go again from weapons, these would need updating too.

## Phase 5.1 — Ability Registry (2026-03-26)

- **AbilityRegistry** — `src/htc/engine/abilities.py`. Maps (timing, card_name) → handler. Timings: on_play, on_attack, on_hit, attack_reaction_effect, defense_reaction_effect. Lookup by NAME so color variants share handlers. Returns None for unregistered cards (graceful degradation).
- **AbilityContext** bundles state, source_card, controller_index, chain_link, effect_engine, events, ask, keyword_engine, combat_mgr. Handlers only need this one arg.
- **Generic abilities** in `src/htc/cards/abilities/generic.py`:
  - Ancestral Empowerment: +1 power to Ninja attack action + draw a card
  - Razor Reflex: modal — mode 1 (dagger/sword weapon +N power) or mode 2 (attack action cost<=1 gets +N power and go again). Note: real card says "when this hits, it gets go again" but we grant immediately (TODO: proper on_hit trigger).
  - Fate Foreseen: Opt 1 via keyword_engine.perform_opt
  - Sink Below: optional put card from hand on bottom of deck, if you do draw a card
  - Shelter from the Storm: deferred (requires damage prevention layer)
- **Game integration** — `_apply_card_ability()` helper builds AbilityContext and dispatches. Attack reactions apply effects before graveyard. Defense reactions apply effects after being added as defenders.
- **TurnCounters field** is `num_cards_drawn`, not `cards_drawn` — easy to get wrong.
- **Razor Reflex** in CSV is NOT "+2 power or go again" as commonly assumed — it's a Ninja-flavored modal card targeting dagger/sword weapons OR low-cost attack actions. Always read functional_text from CSV.
