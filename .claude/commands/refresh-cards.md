Refresh `data/cards.tsv` from the latest Fabrary card dataset.

## Steps

1. Record the current card count: `wc -l data/cards.tsv`
2. Run the refresh:
   ```bash
   python3 -m tools.refresh_cards
   ```
3. Record the new card count and show the diff in row count.
4. Run a quick sanity check that the engine still loads the dataset:
   ```bash
   python3 -m pytest tests/ -q --tb=no -x
   ```
5. Report:
   - Old vs new card count (e.g. "11,950 → 12,180, +230 new rows")
   - Test result (pass/fail)
   - Whether `data/cards.tsv` has uncommitted changes (`git status data/cards.tsv`)

Do NOT commit the change — leave that to the user.
