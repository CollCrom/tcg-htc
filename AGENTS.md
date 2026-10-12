## Workspace

fyendal's engine is vendored as a git submodule at `vendor/fyendal.net`, pinned to upstream commit `22e9ed8b952efaa746ce4f0f8d5c975a703ab683`. Stay on that commit until a deliberate bump; upstream changes daily. The pnpm workspace takes upstream's packages (shared, protocol, engine, cards, bot) and our `packages/*`, never upstream's apps.

Develop in WSL: upstream has a file named `CON.json`, which Windows can't create. Node 24 (`.nvmrc`), pnpm 10.28.2 via corepack, TypeScript run through tsx with no build step.

Setup, for a fresh clone or a new worktree:

```bash
git submodule update --init   # a fresh clone can use `git clone --recurse-submodules` instead
corepack enable pnpm
pnpm install
```

Checks:

- `pnpm test:upstream` runs upstream's engine, cards and bot tests (the bot tests generate their runtime id first). They must pass before blaming our code.
- `pnpm smoke` creates a Game from an upstream precon and prints Seat 0's legal Intents.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on CollCrom/tcg-htc, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Ticket workflow

Every ticket gets its own worktree and branch off the latest main: use the `ticket-worktree` skill before writing any code. PRs merge automatically once tests pass (`.github/workflows/auto-merge.yml`).
