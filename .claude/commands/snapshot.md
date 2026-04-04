Run a game with a specific seed and generate a board viewer with step-through snapshots.

## Steps

1. Run the demo scenario tool with the given seed to generate snapshots:

```bash
python3 tools/demo_scenario.py demo_snapshots.json
```

Note: The demo_scenario.py currently uses a hardcoded seed. If the user wants a specific seed, modify the script or tell them.

2. Open the board viewer HTML:
```bash
open tools/board_viewer.py  # or serve it
```

Actually, the board viewer reads from `demo_snapshots.json`. Just run:

```bash
python3 tools/demo_scenario.py demo_snapshots.json && echo "Snapshots captured"
```

3. Tell the user to open `tools/board_viewer.html` (or the appropriate viewer file) in their browser, and report how many snapshots were captured.

If a seed argument is provided: $ARGUMENTS — note that demo_scenario.py may need to be updated to accept a seed argument. Report this to the user if so.
