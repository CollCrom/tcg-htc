## Agent skills

### Issue tracker

Issues live in GitHub Issues on CollCrom/tcg-htc, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Ticket workflow

Every ticket gets its own worktree and branch off the latest main: use the `ticket-worktree` skill before writing any code. PRs merge automatically once tests pass (`.github/workflows/auto-merge.yml`).
