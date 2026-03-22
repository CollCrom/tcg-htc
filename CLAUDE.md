See AGENTS.md.

## Git Hygiene

- **Never push directly to `main`.** All changes go through feature branches and PRs.
- **Branch naming:** `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `test/<topic>`
- **Commits:** Small, focused commits with clear messages explaining *why*, not just *what*.
- **PRs:** Every PR needs a summary and test plan. Squash-merge to keep `main` history clean.
- **Remote:** Uses SSH alias `github-personal` for the CollCrom account. Remote URL: `git@github-personal:CollCrom/tcg-htc.git`
- **Local git config:** `collcrom@gmail.com` — do not use the work email for this repo.
