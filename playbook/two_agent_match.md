# Two-agent match runbook

How to run a Flesh and Blood match where both seats are driven by Claude
sub-agents through the local engine.

If you have just cleared context and arrived at this doc, you have
everything you need. The infra is in `tools/match_server.py` +
`tools/agent_cli.py` + `playbook/match_protocol.md` (player briefing) +
`playbook/player_spawn_prompt.md` (operator-side spawn template).

---

## Architecture

```
   ┌─────────────────────────┐
   │  Orchestrator (you)     │
   └──────┬──────────────┬───┘
          │ Agent()      │ Agent()         (in parallel)
          ▼              ▼
   ┌──────────────┐  ┌──────────────┐
   │ Player A     │  │ Player B     │
   │ sub-agent    │  │ sub-agent    │
   └──────┬───────┘  └──────┬───────┘
          │ HTTP            │ HTTP
          ▼                 ▼
       ┌────────────────────────┐
       │  match_server (engine) │
       │  background process    │
       └────────────────────────┘
```

The engine runs as a long-lived HTTP server. Each sub-agent loops:
`wait → reason → act → repeat` via short `tools/agent_cli.py` calls.
Wire payloads mirror the JSONL stdio protocol; only the transport
differs.

---

## Prerequisites

- Python 3.11+ (project tested on 3.14).
- A venv at `.venv/` with the package installed editable.
- `data/cards.tsv` present.
- A pair of decks under `ref/decks/` (the four shipped decks all parse).

### One-time setup (skip if `.venv/` already exists)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .[dev]
```

The `[dev]` extras include `pytest` so the integration test suite (which
covers the match-server bridge) is runnable. On macOS/Linux, the python
is at `.venv/bin/python` instead of `.venv/Scripts/python.exe`.

### Verify

```bash
.venv/Scripts/python.exe -c "from engine.rules.game import Game; print('ok')"
.venv/Scripts/python.exe -c "
from pathlib import Path
from engine.decks.deck_list import parse_markdown_decklist
for n in ['decklist-cindra-blue.md','decklist-arakni.md','decklist-cindra.md','decklist-victor.md']:
    d = parse_markdown_decklist(Path('ref/decks',n).read_text(encoding='utf-8'))
    print(n, d.hero_name, d.total_deck_cards)
"
```

---

## Step 1 — start the match server

```bash
.venv/Scripts/python.exe tools/match_server.py \
    --port 8089 \
    --seed 23 \
    --deck-a ref/decks/decklist-cindra-blue.md \
    --deck-b ref/decks/decklist-arakni.md \
    -v >replays/server.log 2>&1 &
```

Run it as a background command (`run_in_background=true` if you're
calling this from Claude Code). Log goes to `replays/server.log`. The
server holds the live game state in memory; no pickling.

Quick smoke check — should return `in_progress` with both heroes:

```bash
.venv/Scripts/python.exe tools/agent_cli.py --port 8089 status
```

---

## Step 2 — spawn the two player agents

Use `playbook/player_spawn_prompt.md` as the prompt template. Spawn both
in **parallel** (a single message with two `Agent` tool calls), so seat
A can pre-game-equipment-select while seat B is also booting.

Substitute these template fields:
- `$SEAT` → `A` or `B`
- `$PORT` → server port (e.g. `8089`)
- `$HERO_NAME` → from the deck file
- `$DECK_PATH` → e.g. `ref/decks/decklist-cindra-blue.md`

The spawned agents run autonomously until the game ends or they hit
their tool budget.

---

## Step 3 — wait

Both player agents return when the engine reports `game_over` (or when
they hit budget). Their final message is a brief report of outcome +
gameplan retrospective. The server's `replays/server.log` has every
HTTP call.

---

## Step 4 — shut down the server

The server doesn't auto-exit if a player gives up mid-game. Find and
kill by port:

```bash
.venv/Scripts/python.exe -c "
import subprocess
out = subprocess.check_output(['netstat','-ano','-p','TCP'], text=True)
for line in out.splitlines():
    if ':8089' in line and 'LISTENING' in line:
        pid = line.split()[-1]
        subprocess.run(['taskkill','/F','/PID',pid])
        print('killed', pid)
"
```

(Linux/macOS: `lsof -ti :8089 | xargs kill -9`.)

---

## Budget reality

A FaB game has 30–80 decisions per seat under focused play, and each
decision is roughly:
- 1 `wait` Bash call
- some reasoning
- 1 `act` Bash call

So budget on **~150 tool calls per agent minimum**, with overhead for
the briefing read on spawn. The `match_protocol.md` + decklist read on
entry is ~5–10 tool calls.

If both agents read a multi-thousand-word strategy doc on spawn, they
will burn most of their budget on context loading and stall around turn
20–25 with the game still in progress (this happened on the first run).
Keep agent on-spawn reading minimal: `playbook/match_protocol.md` plus
their own decklist is sufficient.

If you want longer matches, either:
1. Trim per-decision reasoning (one sentence max).
2. Use `general-purpose` not `sonnet`; smaller models per decision.
3. Spawn fresh "what should I play right now?" agents per decision
   instead of one long-lived agent (re-introduces context per call).

---

## Available decks

All four parse and build a valid Game; pick any matchup:

| Deck file | Hero | Notes |
|---|---|---|
| `decklist-cindra-blue.md` | Cindra, Dracai of Retribution | Blue Cindra ("What if Redline was good"); 71 cards |
| `decklist-cindra.md` | Cindra, Dracai of Retribution | Red Cindra (Calling Brisbane); 60 cards |
| `decklist-arakni.md` | Arakni, Marionette | Calling Memphis 1st; 73 cards |
| `decklist-victor.md` | Victor Goldmane, High and Mighty | 55 cards (file claims 60 — data discrepancy) |

`decklist-victor.md` references "Riches of Tropal-Dhani (Yellow)" which
isn't in `data/cards.tsv` — the engine warns and drops it. Refresh the
card DB via `/refresh-cards` if needed.

---

## Troubleshooting

- **Server crashes immediately on startup with `snapshot_for assumes a
  2-player game; got 0`** → only happens if you're on an old version of
  `tools/match_server.py` without the pre-game-setup placeholder. The
  current version handles this.
- **Sub-agent's `wait` returns `pending: null` for a long time** → the
  engine is mid-resolution between decisions, or the other seat has
  priority. The agent's `wait` will continue polling.
- **HTTP 409 from `act`** → no pending decision for that player, or
  submitted action_id wasn't in the current `options`. Always copy
  `action_id` verbatim from `pending.options[].action_id`.
- **Server hangs after game_over** → expected; see Step 4.
