# Agent Protocol

How agents operate on TCG Hyperbolic Time Chamber. For architecture, see `AGENTS.md`.

## Startup

1. **Read your role file**: `agents/{your-name}.md`
2. **Read project docs**: `AGENTS.md`, then the `ref/` docs listed in your role file (if any).
3. **Read your memory**: `memory/{your-name}.md` — what you need to know from prior sessions.
4. **Do your work**: Follow your role file's instructions. Update `memory/{your-name}.md` as you go — don't wait until the end.
5. **Shutdown reflection**: Evaluate your spawn prompt, role file, AGENTS.md, and memory. Flag anything wrong, missing, or noisy.

## Builder / Skeptic Handoff

The core workflow is: **Builder builds, Orchestrator gates, Skeptic reviews.**

- Builder implements engine features on a feature branch
- **Builder must NOT create PRs.** Builder implements, runs tests, and stops.
- Orchestrator spawns the Skeptic to review all proposed changes for rules correctness
- Skeptic outputs a structured review (correct / issues / missing tests / ambiguous) with a verdict (approve or request changes)
- Critical issues block the PR — Orchestrator sends Builder back to fix, then re-runs Skeptic
- Loop continues until Skeptic returns APPROVE
- **Only the Orchestrator creates PRs**, and only after the Skeptic has approved
- PR description includes skeptic status (e.g., "Skeptic: CLEAN after N rounds")

## Communication

| Channel | Use for |
|---------|---------|
| `memory/{agent}.md` | What you need across sessions. What you wish you'd known. |
| Spawn prompts | Orchestrator passes context and skeptic feedback to builder/skeptic. |

## Guidelines

- Read before acting — understand docs and existing code before making changes
- Be specific — file paths, line numbers, rule numbers, concrete details in posts
- Don't modify `CLAUDE.md` unless explicitly asked by a human
