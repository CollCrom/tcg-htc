## Workspace

fyendal's engine is vendored as a git submodule at `vendor/fyendal.net`, pinned to upstream commit `22e9ed8b952efaa746ce4f0f8d5c975a703ab683`. Stay on that commit until a deliberate bump; upstream changes daily. The pnpm workspace takes upstream's packages (shared, protocol, engine, cards, bot) and our `packages/*`, never upstream's apps.

Before calling `@fyendal/engine` or `@fyendal/cards`, read `docs/upstream.md` (entry points, gotchas).

Develop in WSL: upstream has a file named `CON.json`, which Windows can't create. Node 24 (`.nvmrc`), pnpm 10.28.2 via corepack, TypeScript run through tsx with no build step.

Setup, for a fresh clone or a new worktree:

```bash
git submodule update --init   # a fresh clone can use `git clone --recurse-submodules` instead
corepack enable pnpm
pnpm install --frozen-lockfile
```

Run pnpm from the repo root. Inside `vendor/fyendal.net`, pnpm treats upstream's own workspace (apps included) as the root.

Checks:

- `pnpm test:upstream` runs `pnpm test` in upstream's engine, cards and bot packages; bot's runs upstream's `generate:bot-runtime` first. They must pass before blaming our code.
- `pnpm typecheck` typechecks our packages.
- `pnpm check:glossary` fails on names in `packages/*/src` that use a word `GLOSSARY.md` marks _Avoid_.
- `pnpm test` runs our packages' vitest suites.
- `pnpm smoke` creates a Game from an upstream precon and prints Seat 0's legal Intents.
- `pnpm suite` runs the Phase 1 suite: 100 Ira vs Bravo Games between random Agents (seeds 1 to 50, both seat orders), checks every replay reproduces, and prints outcomes, measurements and exit-criteria verdicts. It takes about a minute and exits non-zero if a criterion fails. Results: `docs/phase1-report.md`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on CollCrom/tcg-htc. Read, create and close them with the `gh` commands in `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Ticket workflow

Every ticket gets its own worktree and branch off the latest main: use the `ticket-worktree` skill before writing any code. PRs merge automatically once tests pass (`.github/workflows/auto-merge.yml`).

The exception is `/implement-spec`: a whole spec lands on one integration branch, and goes to main as one PR that closes the spec and all its tickets.
