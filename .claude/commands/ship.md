Ship the current branch: commit any pending memory updates, rebase onto main, push, and create a PR.

## Pre-flight check

Before doing anything, verify the skeptic has approved:

1. Check `memory/skeptic.md` for a review of the current branch name (`git branch --show-current`). Look for "APPROVE" in the most recent review entry that mentions this branch.
2. If no approval is found, STOP and tell the user: "Skeptic approval not found for this branch. Run `/review` first."
3. If the branch has no changes to `src/htc/`, the skeptic gate is not required — proceed.

## Steps

1. Check for uncommitted changes (`git status --short`). If there are modified memory files, commit them.
2. Rebase onto latest main: `git fetch origin main && git rebase origin/main`
3. Push: `git push -u origin $CURRENT_BRANCH`
4. Get the commit log: `git log --oneline main..HEAD`
5. Create PR with `gh pr create` using this format:

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

The title and summary should be based on the commits on this branch.
