# Orchestrator Memory

Persistent learnings across sessions. Update this as you go.

## Session Learnings

### 2026-03-27: Repo Process Audit + Phase 4 Completion

- **Oscilio dropped, Cindra is the new target.** Blue Cindra vs Arakni Marionette is the matchup. Red Cindra kept as reference.
- **Skeptic gate must be enforced by orchestrator.** PR #27 went up without skeptic approval because the builder created the PR itself. Fixed: builder spawn prompts must always say "do NOT create a PR." Orchestrator runs skeptic loop, orchestrator creates PR.
- **definition.keywords bypass is a recurring bug.** Any time new keyword checks are added, verify they go through `effect_engine.get_modified_keywords()` not `card.definition.keywords`. Skeptic has flagged this multiple times.
- **game.py was split into managers** (PR #29). ActionBuilder, KeywordEngine, CostManager extracted. Future keyword work goes in keyword_engine.py, not game.py.
- **3 TODOs in game.py** need Phase 5: attack reaction effects (line 338), triggered effects (line 780), pitch order choice (line 1215). Tracked in FORUM.md.

## Process Notes

- Skeptic CI workflows intentionally disabled (`if: false`) due to API token cost. Skeptic runs manually via agent spawns during orchestrator sessions.
- Auto-merge doesn't check for approval — acceptable since skeptic runs pre-PR, not in CI.
- All PRs should include "Skeptic: CLEAN after N rounds" or "Skeptic: N/A" in the test plan.
