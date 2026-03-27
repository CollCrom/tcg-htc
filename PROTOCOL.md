# Agent Protocol

How agents operate on TCG Hyperbolic Time Chamber. For architecture, see `AGENTS.md`.

## Startup

1. **Read your role file**: `agents/{your-name}.md`
2. **Get current time**: Get the current date and time in YYYY-MM-DD HH:MM format — use this timestamp in all forum posts.
3. **Read project docs**: `AGENTS.md`, then the `ref/` docs listed in your role file (if any).
4. **Read the forum**: `FORUM.md` — see what others have found, vote on relevant posts.
5. **Read your memory**: `memory/{your-name}.md` — what you need to know from prior sessions.
6. **Do your work**: Follow your role file's instructions. Post to `FORUM.md` and update `memory/{your-name}.md` as you go — don't wait until the end.
7. **Shutdown reflection**: Evaluate your spawn prompt, role file, AGENTS.md, forum, and memory. Flag anything wrong, missing, or noisy.

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
| `FORUM.md` | Cross-agent observations, proposals, rules questions. Vote: `+1` agree, `-1` disagree. |
| `memory/{agent}.md` | What you need across sessions. What you wish you'd known. |

Forum post format: `**Author:** name | **Timestamp:** YYYY-MM-DD HH:MM | **Votes:** +N/-M`

## Guidelines

- Read before acting — understand docs, forum, and existing code before making changes
- Be specific — file paths, line numbers, rule numbers, concrete details in posts
- Don't modify `CLAUDE.md` unless explicitly asked by a human
