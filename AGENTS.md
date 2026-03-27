# TCG Hyperbolic Time Chamber

A Flesh and Blood TCG testing environment. Simulate games, analyze gameplay, and optimize decks — all at 10x speed.

## Purpose

Train and test FaB decks by simulating full games, analyzing play logs for better lines, and evaluating decklists for card and sideboard improvements.

## Tech Stack

- **Language:** Python
- **Domain:** Flesh and Blood TCG rules engine, game simulation, strategy analysis

## Key Files

- `CLAUDE.md` → Boots the orchestrator
- `AGENTS.md` → This file (project docs, architecture, roadmap)
- `PROTOCOL.md` → Agent startup, communication, and handoff rules
- `FORUM.md` → Cross-agent discussion threads
- `agents/orchestrator.md` → Coordinates work, spawns other agents
- `agents/builder.md` → Implements engine features, owns architecture
- `agents/skeptic.md` → Rules correctness reviewer

## Architecture

### Modules

- **`engine/`** — FaB rules engine (2945 lines)
  - `game.py` — Game loop, turn structure, combat chain, damage
  - `action_builder.py` — Decision building, legal action sets
  - `keyword_engine.py` — Keyword enforcement (Arcane Barrier, Phantasm, Stealth, etc.)
  - `cost_manager.py` — Resource/action point payment
  - `combat.py` — Combat chain management
  - `continuous.py` — Continuous effect staging (rules 6.2-6.3)
  - `effects.py` — Effect resolution and keyword queries
  - `events.py` — Game event bus and triggering
  - `cost.py` — Cost calculation helpers
  - `stack.py` — LIFO stack for plays
  - `actions.py` — Action type definitions

- **`state/`** — Game state (246 lines)
  - `game_state.py` — Root state, turn/phase tracking
  - `player_state.py` — Per-player state (hand, life, zones, equipment, mark)
  - `combat_state.py` — Combat chain links and chain state
  - `turn_counters.py` — Per-turn tracking (attacks played, damage dealt)

- **`cards/`** — Card definitions (334 lines)
  - `card.py` — CardDefinition (frozen, from CSV)
  - `instance.py` — CardInstance (mutable per-game state)
  - `card_db.py` — CardDatabase (4217 cards from FaB Cube CSV)

- **`decks/`** — Deck management (207 lines)
  - `deck_list.py` — DeckList structure
  - `loader.py` — Parse deck lists from card database
  - `validation.py` — Legendary/Specialization constraints

- **`player/`** — Player interfaces (66 lines)
  - `interface.py` — Abstract PlayerInterface
  - `random_player.py` — Random decision-making player

- **Analysis** (future) — Log parsing, line suggestions, deck optimization

## Reference Docs

| Doc | Purpose |
|-----|---------|
| `ref/comprehensive-rules.md` | Official FaB Comprehensive Rules (sections 1-9) |
| `ref/talishar-engine-analysis.md` | Talishar PHP engine architecture and patterns |
| `ref/talishar-card-definitions.md` | How Talishar defines card abilities |
| `ref/fab-cube-dataset.md` | FaB Cube card dataset schema and fields |
| `ref/elephant-method.md` | Elephant Method for sideboard-first deckbuilding |
| `ref/decklist-cindra-blue.md` | Target deck: Blue Cindra ("What if Redline was good") |
| `ref/decklist-arakni.md` | Target deck: Arakni Marionette (Calling Memphis 1st) |
| `ref/decklist-cindra.md` | Reference deck: Red Cindra (Calling Brisbane) |
| `ref/decklist-victor.md` | Reference deck: Victor Goldmane |

## Versioning

- **Scheme:** Semantic versioning (`MAJOR.MINOR.PATCH`)
- **Current:** `0.1.0` (pre-release, engine under active development)
- **Tags:** Tag on main after milestone merges: `git tag v0.X.0`
- **No formal releases yet** — will add GitHub releases when the engine is playable end-to-end

## Roadmap

1. **Game engine** — FaB rules engine, deck loading, game simulation *(current)*
2. **Log analysis** — Parse game logs, suggest alternative gameplay lines
3. **Deck analysis** — Evaluate decklists, suggest cards and sideboard configurations

## Agents

| Role | Purpose |
|------|---------|
| Orchestrator | Coordinates work, talks to user, spawns builder/skeptic |
| Builder | Owns implementation — engine, testing, analysis features |
| Skeptic | Reviews engine code for rules correctness against comprehensive rules + Talishar, identifies missing test coverage |
