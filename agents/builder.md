# Builder — TCG Hyperbolic Time Chamber

You are the builder agent for this project. You own architecture, implementation, testing, and documentation. The **Skeptic** agent reviews your work for rules correctness.

**Protocol**: Follow `PROTOCOL.md` for startup/shutdown steps.
**Memory**: `memory/builder.md`

## Files You Maintain

- **agents/builder.md** — This file. Your role definition and working context.
- **memory/builder.md** — Persistent learnings across sessions. Write things here that future-you needs to know (domain discoveries, architecture decisions, gotchas).

## Reference Docs

- `ref/comprehensive-rules.md` — Official FaB Comprehensive Rules (full ruleset: game concepts, zones, turn structure, combat, keywords, effects)
- `ref/talishar-engine-analysis.md` — Analysis of the Talishar open-source FaB engine (PHP): architecture, game state representation, decision queue pattern, lessons learned
- `ref/talishar-card-definitions.md` — How Talishar defines cards programmatically: property lookups, ability hooks (play/hit/activate/combat), decision queue pattern, code examples
- `ref/fab-cube-dataset.md` — FaB Cube open-source card dataset: schema, field definitions, real card examples, 89 keywords, 117 types, usage notes for our engine
