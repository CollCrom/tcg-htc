---
name: refresh-cards
description: Use this skill when the user asks to "pull in new cards", "update cards.tsv", "refresh the card data", "fetch new cards", "sync cards from Fabrary", or otherwise wants to regenerate data/cards.tsv from the upstream Fabrary dataset.
version: 1.0.0
---

# Refresh Cards

Regenerate `data/cards.tsv` from the upstream Fabrary `card.json` dataset using the project's built-in refresh tool.

## When to Use

The user wants new or updated card data — never hand-edit `data/cards.tsv`, since it is auto-generated and any manual rows will be overwritten on the next refresh.

## Source of truth

- Tool: `src/htc/cards/refresh.py` (entry point `python -m htc.cards.refresh`)
- Upstream: `https://raw.githubusercontent.com/fabrary/cards/main/packages/cards/scripts/Released/card.json`
- Output: `data/cards.tsv` (25 columns, tab-separated, header on row 1)

## Steps

1. Run the refresh from the project root:
   ```bash
   python -m htc.cards.refresh
   ```
   On Windows use `python`; on macOS/Linux use `python3`. The script prints a row count and UTC timestamp on success.

2. Sanity-check the diff:
   ```bash
   git diff --stat data/cards.tsv
   wc -l data/cards.tsv
   ```
   Expect a non-trivial line count (thousands) and a header row matching `cards.tsv:1`.

3. Run the keyword/value tests to make sure no card schema regressed:
   ```bash
   python -m pytest tests/keywords/test_keyword_values.py -q
   ```

4. If the refresh succeeded but specific cards are missing or wrong, the issue is upstream in Fabrary — note it back to the user rather than patching `cards.tsv` by hand.

## Offline / pinned variant

If the network is unavailable or the user has a local `card.json` they want to use:

```python
from pathlib import Path
from htc.cards.refresh import fetch_and_convert
fetch_and_convert(json_path=Path("path/to/card.json"))
```

## Things to flag to the user

- Manual edits to `data/cards.tsv` will be lost on the next refresh — if a custom card is needed, keep it in a separate patch script.
- New cards may introduce keywords or abilities the engine doesn't yet implement; check `src/htc/cards/abilities/` if tests fail after a refresh.
- The refresh overwrites the file in place, so commit or stash any in-progress local changes to `data/cards.tsv` first.
