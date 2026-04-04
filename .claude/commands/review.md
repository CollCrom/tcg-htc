Spawn the Skeptic agent to review the current branch diff vs main.

Use the Agent tool to spawn a skeptic with this prompt:

---

You are the Skeptic. Read `agents/skeptic.md` and follow `PROTOCOL.md`.

## Task — Review `$CURRENT_BRANCH` vs `main`

Run `git diff main..HEAD -- '*.py'` to see all changes. Read `memory/skeptic.md` for your persistent context.

$ARGUMENTS

### Output Format

Structured review with:
- **Critical issues** (block PR — incorrect game outcomes)
- **Minor issues** (non-blocking)
- **Missing tests** (gaps in coverage)
- **Verified correct** (key mechanics confirmed)

Verdict: APPROVE or REQUEST CHANGES.

Update `memory/skeptic.md` with your findings.
