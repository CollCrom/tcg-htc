Ship the current branch: commit any pending memory updates, rebase onto main, push, and create a PR.

Before running this, the skeptic must have approved the changes. Include the skeptic status in the PR.

## Steps

1. Check for uncommitted changes (`git status --short`). If there are modified memory files, commit them.
2. Rebase onto latest main: `git fetch origin main && git rebase origin/main`
3. Push: `git push -u origin $CURRENT_BRANCH`
4. Create PR with `gh pr create` using this format:

```
gh pr create --title "<short title under 70 chars>" --body "$(cat <<'EOF'
## Summary
<bullet points describing what changed>

## Test plan
- [x] <N> tests passing (<M> new)
- [x] Skeptic: CLEAN after N rounds
<any round details if there were request-changes rounds>

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

$ARGUMENTS

The title and summary should be based on the commits on this branch (`git log --oneline main..HEAD`).
