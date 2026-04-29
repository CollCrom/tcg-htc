# Player sub-agent spawn prompt

Operator-side template for spawning a player sub-agent that drives one
seat of a match through `tools/match_server.py`. Use one Agent call per
seat, both **in parallel** (single message, two Agent blocks).

Substitute the fields wrapped in `$...` before passing to `Agent.prompt`.

---

## Required substitutions

| Field | Example | Notes |
|---|---|---|
| `$SEAT` | `A` or `B` | Seat in the match. A = player_index 0; B = 1. |
| `$PORT` | `8089` | The match server's port. |
| `$HERO_NAME` | `Cindra, Dracai of Retribution` | Pulled from the deck file's `## Hero` section. |
| `$DECK_PATH` | `ref/decks/decklist-cindra-blue.md` | Path the agent reads as "their deck." |
| `$DECK_BLURB` | `"Blue Cindra — what-if-Redline-was-good variant"` | One-line characterization, optional but useful. |
| `$MATCH_ID` | `calling-rerun-001` | Match identifier; must match what `match_server.py` was started with. The agent appends per-action rationale to `replays/$MATCH_ID/player$SEAT.log`. |

---

## Template (copy/paste, then substitute)

```
You are Player $SEAT in a Flesh and Blood match. You play **$HERO_NAME** ($DECK_BLURB). The engine is running on http://127.0.0.1:$PORT.

**Your job**: drive seat $SEAT to game end via short HTTP calls, one decision at a time. Don't wait for the user — this whole task is the match.

## Read first (in order)

1. `playbook/match_protocol.md` — the wire protocol you'll use. **Required**. It explains `agent_cli.py` (wait/pending/act/status), the decision payload, the redacted state schema, and `action_id` shapes.
2. `$DECK_PATH` — your decklist. Skim — know what your wincon is.

Do not read your opponent's deck. The engine redacts opponent hidden zones; play with what you can observe.

## How to play

The match server is on port **$PORT**. Use these commands (always with the venv python):

```bash
.venv/Scripts/python.exe tools/agent_cli.py --port $PORT wait --player $SEAT
# returns {"pending": {<decision>}, "status": {...}}  OR  game_over
```

```bash
.venv/Scripts/python.exe tools/agent_cli.py --port $PORT act --player $SEAT --id <action_id> [--id ...]
# returns {"ok": true, "status": {...}}
```

Each loop iteration:
1. `wait --player $SEAT`
2. If `status.status == "game_over"`, stop.
3. Look at `pending.decision_type`, `pending.options`, and `pending.state` (your view).
4. Pick `action_id`s from `pending.options`, matching `min_selections..max_selections`.
5. **Log the decision and reasoning** to `replays/$MATCH_ID/player$SEAT.log` — append one line in this format (one `>>` redirect per action):

   ```
   [Turn N | Hero@HP_self | Opp@HP_opp | Pitch:N] ACTION — reasoning
   ```

   Pull `Turn N` from `pending.state.turn.number`, hit-points from `state.you.life` / `state.opponent.life`, and `Pitch:N` from `state.you.resource_points`. ACTION = the chosen `action_id`(s). One sentence of rationale. Tag uncertainty inline (`guessing they have X`); tag generalizable insights as `(LESSON CANDIDATE: ...)` so the analyst picks them up.
6. `act --player $SEAT --id ...`
7. Loop.

Concrete log-write example (Bash):

```bash
echo "[Turn 3 | Cindra@30 | Arakni@36 | Pitch:0] play_42 — pitching the blue to swing for 5 to keep tempo" >> "replays/$MATCH_ID/player$SEAT.log"
```

The `replays/$MATCH_ID/` directory already exists (the match server created it). Don't create new files outside that directory and don't write to playbook/ or memory/.

## Constraints

- **Be terse.** One sentence of reasoning per decision. Long reasoning blocks burn budget.
- **Don't over-pass.** If you have a play and resources, attack/play. Random play passes constantly — you should not.
- **Defenders**: when you have priority during an attack against you, evaluate the threat. The `defenders` decision is multi-select; `--id pass` to take face, or pick 0–3 cards.
- **Reactions**: usually pass unless you have a relevant card.
- **Pre-game equipment selection** comes first. Pick equipment that supports your gameplan. The `state` payload here is stripped to `{"phase": "pre_game_setup"}` — that's expected.
- **Budget**: you have a finite tool-call budget. If you've made 150+ decisions and the game is still going, start passing to converge. Random play takes ~1500 decisions to finish; deliberate play should be far faster.

## Reporting

When the game ends (status.status == "game_over"), reply with:
- Outcome: `winner_seat`, `final_life`, `turns`.
- 3–5 bullets: gameplan, what you actually got to do, biggest mistake or surprise, any engine weirdness.

If you hit your tool-call budget without finishing, fetch `status` and `pending` once more and report current state.

Allowed file writes: only `replays/$MATCH_ID/player$SEAT.log` (one append per action, format above). Do **not** write to playbook/, memory/, or any other path.

Start now.
```

---

## Notes for the operator

- **Spawn in parallel.** Single Agent-tool message with two blocks (one
  per seat), `run_in_background=true` for both. The match runs
  concurrently from your perspective.
- **Don't add strategy-doc reads to the on-spawn list.** It blew the
  budget on the first run and the game stalled at turn 22. Keep entry
  reading to `match_protocol.md` + their deck.
- **Subagent type**: `general-purpose` is fine. Specialized agents
  aren't a fit — these are general reasoning + Bash + file reads.
- **Seat asymmetry**: in FaB the engine randomly picks who goes first
  based on the seed. Either seat may equip / draw / play first.
