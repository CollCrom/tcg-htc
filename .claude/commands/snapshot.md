Run a game and generate a board viewer HTML with step-through snapshots.

## Steps

1. Generate snapshots by running the demo scenario:

```bash
python3 tools/demo_scenario.py demo_snapshots.json
```

2. Convert snapshots to a self-contained HTML board viewer:

```bash
python3 tools/board_viewer.py demo_snapshots.json board_view.html
```

3. Open the HTML viewer:

```bash
open board_view.html
```

4. Report how many snapshots were captured and tell the user the board viewer is open. They can step through states with arrow keys or J/K.

Note: `demo_scenario.py` uses a hardcoded seed (0). If the user wants a different seed, the script would need to be modified to accept a seed argument.
