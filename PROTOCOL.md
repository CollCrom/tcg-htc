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

- **Always start from clean main**: `git checkout main && git pull origin main`, then create the feature branch
- Builder implements engine features on a feature branch
- **Builder must NOT create PRs.** Builder implements, runs tests, and stops.
- Orchestrator spawns the Skeptic to review all proposed changes for rules correctness
- Skeptic outputs a structured review (correct / issues / missing tests / ambiguous) with a verdict (approve or request changes)
- Critical issues block the PR — Orchestrator sends Builder back to fix, then re-runs Skeptic
- Loop continues until Skeptic returns APPROVE
- **Rebase onto latest main** before pushing: `git fetch origin main && git rebase origin/main`
- **Only the Orchestrator creates PRs**, and only after the Skeptic has approved
- PR description includes skeptic status (e.g., "Skeptic: CLEAN after N rounds")
- **PRs auto-merge** (squash + delete branch) — do not manually merge or ask about merging

## Communication


| Channel             | Use for                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `memory/{agent}.md` | What you need across sessions. What you wish you'd known.            |
| Spawn prompts       | Orchestrator passes context and skeptic feedback to builder/skeptic. |


## Memory Policy

Each agent writes to `memory/{agent-name}.md`. Write learnings **during** work, not just at the end.

### What each agent writes

**Orchestrator** (`memory/orchestrator.md`):

- Session summaries: which PRs shipped, what changed, test counts
- Process learnings: what workflows worked or failed
- Open TODOs and deferred items
- User corrections on FaB rules

**Builder** (`memory/builder.md`):

- Architecture decisions and why (e.g., "used namedtuple for X because...")
- Gotchas discovered during implementation (e.g., "target_filter closures can't have side effects")
- Patterns established that future work should follow (e.g., "use `make_once_filter` for single-use effects")
- Bug classes encountered and their fixes

**Skeptic** (`memory/skeptic.md`):

- Known accepted simplifications (with justification)
- Recurring bug patterns to check for (e.g., `definition.supertypes` bypasses)
- Rules clarifications from the user
- Review history: what was reviewed, verdict, key findings
- Card-specific implementation notes (correct behaviors verified)

### When to write

- **Builder**: After each commit or when discovering something non-obvious
- **Skeptic**: After each review round (findings, verdict, new patterns found)
- **Orchestrator**: After each PR ships and at end of session

### What NOT to write

- Things derivable from code or git history
- Ephemeral task state (use tasks for that)
- Duplicates of what's already in memory

## Guidelines

- Read before acting — understand docs and existing code before making changes
- Be specific — file paths, line numbers, rule numbers, concrete details in posts
- Don't modify `CLAUDE.md` unless explicitly asked by a human

