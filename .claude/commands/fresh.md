Start a fresh branch from clean main.

## Steps

1. Check if current branch has uncommitted changes — warn if so
2. `git checkout main && git pull origin main`
3. Create the new branch: `git checkout -b $ARGUMENTS`
4. Run baseline tests: `python3 -m pytest tests/ -q --tb=no`
5. Report the branch name and baseline test count

If no branch name is provided in the arguments, ask the user for one.
