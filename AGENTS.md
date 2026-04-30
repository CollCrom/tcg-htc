# TCG Hyperbolic Time Chamber

A Flesh and Blood TCG testing environment. Simulate games, analyze gameplay, and optimize decks — all at 10x speed.

## Purpose

Train and test FaB decks by simulating full games, analyzing play logs for better lines, and evaluating decklists for card and sideboard improvements.

## Stack

- **Engine**: Python rules engine in `engine/`. Server-side legal-action enforcement. Per-player state snapshot API that redacts hidden zones.
- **Card data**: `data/cards.tsv` — TSV converted from the [Fabrary card dataset](https://github.com/fabrary/cards) (4,562 cards). Refresh via `python -m tools.refresh_cards`.
- **Rules**: `ref/rules/` (saved local copy of official rules).
- **Format**: **Classic Constructed** (60-card decks). Reference decks live in `ref/decks/` (Bravo, Cindra, Arakni, Victor).

The engine is the largest open implementation question.

## Key Files

- `AGENTS.md` → This file (project docs, architecture, roadmap)
- `agents/orchestrator.md` → Coordinates work, spawns other agents
- `tools/match_server.py` → HTTP server wrapping the engine; both seats served as `GET /pending?player=A|B` + `POST /action?player=A|B`. Wire payloads mirror the JSONL stdio protocol.
- `tools/agent_cli.py` → Tiny stdlib CLI (`wait`/`pending`/`act`/`status`) used by sub-agents to drive `match_server.py` from Bash.
- `tools/auto_player.py` → Per-decision Anthropic API driver for one seat. Cheaper alternative to spawning a Claude Code sub-agent per seat (constant per-decision cost vs. compounding transcript). Requires `pip install -e .[llm]` and `ANTHROPIC_API_KEY`.
- `playbook/match_protocol.md` → Wire-format briefing read by spawned **player** sub-agents.
- `playbook/two_agent_match.md` → Operator runbook for "two Claude sub-agents play a game" — start here.
- `playbook/player_spawn_prompt.md` → Parameterized template for the per-seat `Agent.prompt`.

## Architecture

### Modules

The whole package lives under `engine/` at the repo root (no `src/` layer). Submodules:

- **`engine/`** — top-level entry points and shared types
  - `enums.py` — Shared enums (`Phase`, `Zone`, `CardType`, `SubType`, `SuperType`, `Keyword`, `DecisionType`, `ActionType`, etc.)
  - `__main__.py` — `python -m engine` random-vs-random demo runner (developer smoke test)
  - `_demo_deck.py` — `BRAVO_DECK_TEXT` constant shared by demo runners and tests
  - `stdio.py` — CLI entry point (`python -m engine.stdio`) that runs a game with one seat driven over JSONL stdio and the other seat as a seeded `RandomPlayer`. **Single-seat path only**; for two external agents driving both seats use `tools/match_server.py`. Note: `engine.stdio` will crash on decks with multi-option equipment slots (latent `snapshot_for` bug — see `engine/state/snapshot.py`); `match_server.py` works around it.

- **`engine/rules/`** — FaB rules engine
  - `game.py` — Game loop, turn structure, combat chain, damage
  - `action_builder.py` — Decision building, legal action sets
  - `abilities.py` — `AbilityRegistry`, `AbilityContext`, ability handler dispatch
  - `keyword_engine.py` — Keyword enforcement (Arcane Barrier, Phantasm, Stealth, etc.)
  - `cost_manager.py` — Resource/action point payment
  - `combat.py` — Combat chain management
  - `continuous.py` — Continuous effect staging (rules 6.2-6.3)
  - `effects.py` — Effect resolution and keyword queries
  - `events.py` — Game event bus and triggering
  - `cost.py` — Cost calculation helpers
  - `stack.py` — LIFO stack for plays
  - `actions.py` — Action type definitions

- **`engine/state/`** — Game state
  - `game_state.py` — Root state, turn/phase tracking
  - `player_state.py` — Per-player state (hand, life, zones, equipment, mark, `hand_revealed_to` peek tracker)
  - `combat_state.py` — Combat chain links and chain state
  - `turn_counters.py` — Per-turn tracking (attacks played, damage dealt)
  - `snapshot.py` — `snapshot_for(state, viewer_index, effect_engine)` builds the per-player redacted view embedded in stdio decision messages

- **`engine/cards/`** — Card definitions
  - `card.py` — CardDefinition (frozen, from TSV)
  - `instance.py` — CardInstance (mutable per-game state)
  - `card_db.py` — CardDatabase (4562 cards from Fabrary dataset TSV)

- **`engine/cards/abilities/`** — Card-text rules implementations (~6,500 lines)
  - `generic.py` — Cards shared across decks (Sink Below, Pummel, Razor Reflex, etc.)
  - `assassin.py` — Assassin-class cards (Arakni Marionette deck)
  - `ninja.py` — Ninja-class cards
  - `equipment.py` — Equipment-bearing cards and weapon attacks
  - `heroes.py` — Hero abilities (Cindra, Arakni, etc.)
  - `agents.py` — Agent of Chaos cards (Mask of Deceit transformations)
  - `tokens.py` — Token cards (Frailty, Inertia, Ponder, Fealty, Silver, etc.)
  - `_helpers.py` — Shared helpers (`grant_power_bonus`, `create_token`, `MarkOnHitTrigger`, etc.)

- **`engine/decks/`** — Deck management
  - `deck_list.py` — DeckList structure (the type `Game` accepts as input)
  - `loader.py` — Parse deck lists from card database

- **`engine/player/`** — Player interfaces
  - `interface.py` — Abstract `PlayerInterface` Protocol
  - `random_player.py` — Random decision-making player (in-process opponent for `engine.stdio` and tests)
  - `stdio_player.py` — JSONL stdin/stdout `PlayerInterface` for external agents

- **Analysis** (future) — Log parsing, line suggestions, deck optimization

## Reference Docs

| Doc | Purpose |
|-----|---------|
| `ref/rules/comprehensive-rules.md` | Official FaB Comprehensive Rules (sections 1-9) |
| `ref/deckbuilding/elephant-method.md` | Elephant Method for sideboard-first deckbuilding |
| `ref/decks/decklist-cindra-blue.md` | Target deck: Blue Cindra ("What if Redline was good") |
| `ref/decks/decklist-arakni.md` | Target deck: Arakni Marionette (Calling Memphis 1st) |
| `ref/decks/decklist-cindra.md` | Reference deck: Red Cindra (Calling Brisbane) |
| `ref/decks/decklist-victor.md` | Reference deck: Victor Goldmane |

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
| Orchestrator | Coordinates work, talks to user, spawns other agents |
