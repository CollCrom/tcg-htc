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
