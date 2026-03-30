## Startup

You are the orchestrator. Read `agents/orchestrator.md` and follow `PROTOCOL.md`.

## Git Hygiene

- **Never push directly to `main`.** All changes go through feature branches and PRs.
- **Start from clean main:** Always `git checkout main && git pull` before creating a new branch.
- **Branch naming:** `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `test/<topic>`
- **Commits:** Small, focused commits with clear messages explaining *why*, not just *what*.
- **PRs:** Every PR needs a summary and test plan. PRs auto-merge (squash + delete branch) — do not manually merge.
- **Rebase before push:** `git fetch origin main && git rebase origin/main` right before pushing.
- **Skeptic gate:** Before creating any PR, run the skeptic agent in a loop on all proposed changes. Fix any critical issues it finds and re-run until the skeptic returns CLEAN. Only then create the PR. Include the skeptic status (e.g. "Skeptic: CLEAN after N rounds") in the PR test plan.
- **Remote:** Uses SSH alias `github-personal` for the CollCrom account. Remote URL: `git@github-personal:CollCrom/tcg-htc.git`
- **Local git config:** `collcrom@gmail.com` — do not use the work email for this repo.
