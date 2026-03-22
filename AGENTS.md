# TCG Hyperbolic Time Chamber

A Flesh and Blood TCG testing environment. Simulate games, analyze gameplay, and optimize decks — all at 10x speed.

## Purpose

Train and test FaB decks by simulating full games, analyzing play logs for better lines, and evaluating decklists for card and sideboard improvements.

## Tech Stack

- **Language:** Python
- **Domain:** Flesh and Blood TCG rules engine, game simulation, strategy analysis

## Key Files

- `CLAUDE.md` → Points here
- `AGENTS.md` → This file (project docs, architecture, roadmap)
- `agents/steward.md` → Single agent that owns all development

## Architecture

TBD — the game engine is the first build target. Expected modules:

- **Engine** — FaB rules, game state, turn structure, combat, chain links
- **Decks** — Deck loading, validation, hero/equipment/sideboard configuration
- **Simulation** — Run games between two decks, collect results
- **Analysis** (future) — Log parsing, line suggestions, deck optimization

## Roadmap

1. **Game engine** — FaB rules engine, deck loading, game simulation *(current)*
2. **Log analysis** — Parse game logs, suggest alternative gameplay lines
3. **Deck analysis** — Evaluate decklists, suggest cards and sideboard configurations

## Agents

| Role | Purpose |
|------|---------|
| Steward | Owns all development — engine, testing, analysis features |
