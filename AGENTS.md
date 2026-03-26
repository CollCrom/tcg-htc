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
| Orchestrator | Coordinates work, talks to user, spawns builder/skeptic |
| Builder | Owns implementation — engine, testing, analysis features |
| Skeptic | Reviews engine code for rules correctness against comprehensive rules + Talishar, identifies missing test coverage |
