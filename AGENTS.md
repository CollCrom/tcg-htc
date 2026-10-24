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

- `pnpm check` runs the fast checks CI runs; each part is its own script in `package.json`. Run it before pushing. Two gotchas: `check:glossary` covers names in `packages/*/src` against `GLOSSARY.md`'s _Avoid_ words, and `lint:workflows` (actionlint 1.7.7 over `.github/workflows/`) downloads the binary into the gitignored `.cache/` once, while CI's runner also has shellcheck, so a `run:` step can fail there and pass here.
- `pnpm test:upstream` runs `pnpm test` in upstream's engine, cards and bot packages; bot's runs upstream's `generate:bot-runtime` first. They must pass before blaming our code.
- `pnpm smoke` creates a Game from an upstream precon and prints Seat 0's legal Intents.
- `pnpm suite` runs the Phase 1 suite: 100 Ira vs Bravo Games between random Agents (seeds 1 to 50, both seat orders), checks every replay reproduces, and prints outcomes, measurements and exit-criteria verdicts. It takes about a minute and exits non-zero if a criterion fails. Results: `docs/phase1-report.md`.

A new check is a root `package.json` script wired into `check`. TypeScript ones live in `packages/runner/src` with their vitest test beside them; shell ones in `scripts/`.

## Claude Agents

Claude Agents play through Claude Code in print mode on the developer's subscription (`docs/adr/0002-claude-agents-through-claude-code.md`): the `claude` binary must be on the path and logged in, and `ANTHROPIC_API_KEY` must not be set, because print mode bills the API when it is (the call strips it from the child anyway). Package: `packages/claude-agent` (its README has the call and the Agent).

- `pnpm game:claude [--seed 1] [--first ira|bravo] [--model0 opus] [--effort0 medium] [--model1 opus] [--effort1 medium] [--results results]` plays one Game between two Claude Agents on the Ira and Bravo Lists, `--first` naming the hero in Seat 0. Each Agent first builds its Decklist from its List in one call, told only the opponent's hero. It prints one line per decision and exits non-zero on a stall or error. The Game file (setup, both Decklist builds, both system prompts, replay, outcome, measurements, every Decision record) lands in `results/<timestamp>-game-<seed>-<first>-first/`, rewritten after every decision; `results/` is gitignored. About 250 decisions at 5 to 15 s each: it spends the subscription, so don't run it as a check.
- `pnpm suite:claude [--model0 opus] [--effort0 medium] [--model1 opus] [--effort1 medium] [--concurrency 2] [--seeds 1-5] [--results results]` plays the Phase 2 suite as one Run: each seed with each List in Seat 0 once (ten Games by default), `--concurrency` Games at a time, each capped at 600 decisions (over it is a stall). It prints one line per decision and per Game status change, then the report path, and exits non-zero if an exit criterion fails (a Game not won or drawn, or ended on an Agent's fault). The Run lands in `results/<timestamp>-suite/`: `manifest.json` (config, every Game's status and outcome, rewritten on every change), one Game file per Game and `report.md`, which the owner commits as `docs/phase2-report.md`. Hours of subscription time; `--resume` (#177) is not implemented yet.
- `TCG_HTC_LIVE_CLAUDE=1 pnpm --filter @tcg-htc/claude-agent test` adds the one live test (a single real `haiku` call); without the variable, every test is offline.

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
