Do a DRY (Don't Repeat Yourself) and YAGNI (You Aren't Gonna Need It) pass on the code.

This is a propose-then-apply pass. Surface candidates first, get user approval, then change code. Do not edit anything in steps 1–3.

## Scope

Resolve `$ARGUMENTS` in this order:
- A path or glob → scope to that.
- `all` → all of `engine/` and `tools/`.
- `diff` or empty → files changed on the current branch: `git diff --name-only main...HEAD -- '*.py'`. If that list is empty, ask the user what to scope to.

## Step 1 — DRY findings (read-only)

Look for, in this order of priority:

1. **Repeated literals** — same string/number in 3+ places where one constant would do. Likely suspects in this repo: deck-text blobs, `data/cards.tsv` paths, `Path(__file__).parent...` chains, default seeds.
2. **Near-identical helpers** — functions with the same signature and substantively the same body across modules. Verify they actually do the same thing (read the bodies — don't trust signatures).
3. **Duplicated test setup** — `make_*` factories or boilerplate setup re-defined per file when `tests/conftest.py` or `tests/_helpers/` could host one copy.
4. **Path computations** — same `__file__` traversal pattern in many files. Hoist to a shared `REPO_ROOT` constant.

Skip:
- Two-call duplication. Wait for the third occurrence.
- Surface-similar code that's evolving in different directions (parallel-but-diverging).
- Coincidentally-equal constants in unrelated modules.

## Step 2 — YAGNI findings (read-only)

Look for, in this order of priority:

1. **Unused exports** — public functions/classes/constants with zero importers. Verify with `grep -rn "from <mod> import <name>\|<mod>\.<name>" --include='*.py' --include='*.md'` (the `*.md` matters — slash-command files reference module paths).
2. **Single-call wrappers** — a function called from exactly one site, with no test of its own. Inline it.
3. **Dead branches** — `if False:`, `if isinstance(x, SomethingThatCantHappen)`, defensive handlers for impossible inputs given the caller contract.
4. **Unused parameters / default args nobody overrides** — if every call passes the default, drop the parameter.
5. **Speculative configuration** — config knobs / hooks / extension points with no current consumer.
6. **Commented-out code** — old code preserved as comments. Surface, don't auto-delete.

Skip — these are NOT YAGNI violations:
- `engine/player/interface.py` — the `PlayerInterface` Protocol. Used by external agents, no internal importer required.
- `engine/player/stdio_player.py` — JSONL adapter. Same reason.
- Type-only or Protocol-only definitions used for type annotations.
- Test fixtures whose only "consumers" are tests in the same directory (the test IS the consumer).
- TODO comments — surface them, do not auto-remove.

## Step 3 — Present findings

Single message, two tables:

```
DRY                                                   | YAGNI
1. <what>  <where>  → <proposed fix>                 | 1. <what>  <where>  → <proposed fix>
2. ...                                                | 2. ...
```

Then ask: **"Apply which? (`all`, numbers like `D1,D3,Y2`, or describe what to skip.)"** Wait for an explicit answer. Default is to do nothing.

## Step 4 — Apply approved changes

For each approved item:
1. Make the change.
2. Run the directly-affected test files (`pytest <files>`). If anything breaks, revert that single change and continue with the rest — don't pile broken changes on top of each other.

After all changes:
1. Full suite: `python -m pytest -q --tb=line`.
2. Report:
   - Count applied / count skipped.
   - Test count before vs after — must be equal. A DRY/YAGNI pass should never reduce test count.
   - `git diff --stat` net line delta.
   - Any item where you couldn't verify safely — flag for the user.

## Guardrails

- Never extract a shared helper for fewer than 3 callers.
- Never inline a function that has its own test.
- Never delete a name that appears in a docstring, README, or `.claude/commands/*.md` without confirming.
- If consolidation requires a rename, prefer keeping the old name as an alias for one commit so callers can be updated incrementally.
- If you suspect a "duplication" is actually parallel evolution, leave it and label it "intentional duplication" in the report.

$ARGUMENTS
