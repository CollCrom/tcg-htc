# Match protocol — how a player agent talks to the engine

You are one seat in a Flesh and Blood match. The engine runs as an HTTP
server on `localhost`. Every decision you make is one HTTP round-trip.
You see only your own state; opponent hidden zones are redacted.

---

## Loop

Until the game ends, repeat:

1. **Wait for a pending decision.**
   ```bash
   .venv/Scripts/python.exe tools/agent_cli.py --port $PORT wait --player $SEAT
   ```
   Returns when either the engine asks you something or the game ends.
   Output is one JSON line:
   - `{"pending": {<decision>}, "status": {<status>}}` — your turn to choose.
   - `{"pending": null, "status": {"status": "game_over", ...}}` — done.

2. **Read the decision.** Fields you care about:
   - `decision_type` — what kind of question this is (see below).
   - `prompt` — short human text from the engine.
   - `min_selections` / `max_selections` — how many `action_id`s to send back.
   - `options[]` — each has `action_id`, `description`, `action_type`,
     `card_instance_id`. **You must respond with `action_id`s from this list.**
   - `state` — your view of the board.

   The wrapper response also carries `pending_age_seconds` (sibling of
   `pending` and `status`): seconds since this seat's current decision was
   raised, or `null` when no decision is pending. Observability only — the
   engine never times out a decision; you can ignore this field, but
   orchestrators use it to spot wedged matches.

3. **Reason.** Look at `state.you.life`, `state.opponent.life`,
   `state.you.hand`, the `combat_chain`, etc. Pick the action that best
   serves your gameplan. Be deliberate; do not auto-pick.

4. **Submit your action.**
   ```bash
   .venv/Scripts/python.exe tools/agent_cli.py --port $PORT act --player $SEAT --id $ACTION_ID
   ```
   For multi-select decisions, repeat `--id` once per choice:
   ```bash
   ... act --player A --id defend_85 --id defend_107 --id pass
   ```
   Response: `{"ok": true, "status": {...}}` or an `{"error": ...}` if
   you submitted nonsense.

   **If you get an `error` containing `unknown action_ids`**, the engine
   moved to a different decision for your seat between your `wait` and
   your `act`. Don't bail — go back to step 1, call `wait` again to get
   the current decision, and re-pick from its options. Don't reuse the
   stale `action_id`. If the same submission 409s twice in a row, that's
   a real bug; report it instead of looping forever.

5. Loop.

If you ever want a quick read on overall match state without a pending
fetch:

```bash
.venv/Scripts/python.exe tools/agent_cli.py --port $PORT status
```

---

## Decision types you will see

The `decision_type` field carries one of these strings. Always trust
`min_selections` / `max_selections` over the descriptions below; the
engine is authoritative.

| `decision_type` | What it means | Selection |
|---|---|---|
| `choose_equipment` | Pre-game: pick one option per slot when multiple available. Fired once per ambiguous slot. | exactly 1 |
| `play_or_pass` | You have priority; play a card, activate something, attack, or `pass`. The default decision shape during your action phase and during opponent attacks. | exactly 1 |
| `attack_target` | Choose which player to attack with the active weapon/attack (when targeting is ambiguous). | exactly 1 |
| `defenders` | Choose which cards from hand to defend with against the active attack. | 0..N — `--id pass` for empty pick, or up to your hand size of `defend_<id>` selections |
| `pitch` | Pay a resource cost: pick cards from hand whose pitch values sum to the required amount. | varies — `min_selections` is the count needed |
| `pitch_order` | When multiple cards are being pitched and order matters (cards go to the bottom of deck), select them in order. | min..max equal to the number being pitched |
| `arsenal` | End of turn: optionally arsenal a card from hand. | 0 or 1 — `pass` available if you don't want to arsenal |
| `reaction` | Reaction window during attack/combat resolution. Pick one reaction card or `pass`. Stacking multiple reactions in one window happens via repeated `reaction` prompts: each resolves before the next is asked. | exactly 1 |
| `optional_ability` | A "may" trigger — yes or no. | exactly 1 |
| `choose_target` | Generic target selection for an ability (a card, player, or other targetable). | usually exactly 1 |
| `choose_mode` | Modal effect — pick one of N branches ("choose one: A or B"). | exactly 1 |
| `order_triggers` | When multiple triggered abilities go on the stack at once, the controller orders them. | full list of trigger ids in chosen order |
| `choose_agent` | Mask of Deceit triggered ability — when Mask of Deceit defends an attack from a **marked** hero, you choose which Agent of Chaos demi-hero to transform into. (Against an unmarked attacker the engine picks randomly without asking.) Arakni-specific, fires mid-combat, not pre-game. | exactly 1 |

---

## State payload — what each field tells you

Top-level keys: `you`, `opponent`, `combat_chain`, `turn`.

**`you`** (full visibility of your seat):
- `life`, `is_marked`, `action_points`, `resource_points`
- `hero` (full card dict), `weapons[]`, `equipment{slot: card|null}`
- `permanents[]`, `hand[]`, `arsenal[]`, `pitch[]`, `graveyard[]`,
  `banished[]`, `soul[]`
- `deck_size` (count, not contents)
- `turn_counters` — per-turn tracking (attacks played, damage dealt, etc.)

**`opponent`** (redacted):
- Same shape **except** `hand` is replaced with `hand_size: int` and
  `hand_revealed: [<cards you've peeked>]`.
- `arsenal` shows face-up cards in full and face-down ones as
  `{"face_down": true}`.
- `banished` is split into `banished_face_up[]` (full) and
  `banished_face_down_count` (number only).

**Card dicts** (every card in any zone) include base values plus, when
they differ from base, effect-modified values:

- Base (always present): `name`, `cost`, `power`, `defense`, `pitch`,
  `health`, `intellect`, `arcane`, `types`, `subtypes`, `supertypes`,
  `keywords`, `color`. Plus `instance_id` (use for identity — `action_id`s
  reference it) and `zone`.
- Hot-zone only (hand, arsenal, pitch, equipment, weapons, permanents,
  hero, soul, combat chain): `type_text`, `functional_text`, `is_tapped`,
  `activated_this_turn`, `face_up`, `counters`, `is_proxy`.
- Cold zones (graveyard, banished face-up): rules text and per-instance
  flags are **stripped** to save tokens. All strategic fields above are
  preserved — name, types, subtypes, supertypes, keywords, stats — so
  card-counting and type-aware effects still work. If you really need the
  rules text of a cold-zone card, look it up:

  ```bash
  .venv/Scripts/python.exe tools/agent_cli.py --port $PORT card --name "Codex of Frailty"
  ```

- Modified (post continuous effects): `modified_power`,
  `modified_defense`, `modified_cost`, `modified_subtypes`,
  `modified_keywords`, `modified_supertypes`. **Only present when they
  differ from base.** A missing `modified_X` means "no continuous effect
  changed this; modified equals base." Use modified values for combat
  math when they're present; fall back to base otherwise.

The engine auto-resolves any decision where the player has exactly one
option and must pick exactly one (~73% of all prompts in practice — most
``play_or_pass`` and ``reaction`` windows). You will only be asked when
there's a real choice.

**`combat_chain`**: `is_open` (bool) and `links[]` with `link_number`,
`active_attack` (the card on top), `attack_source`,
`attack_target_index` (0/1), `defending_cards[]`, `damage_dealt`,
`hit`, `hit_count`.

**`turn`**: `number`, `phase` (e.g. `start`, `action`, `end`),
`combat_step`, `active_player_index`, `priority_player_index`. Check
`active_player_index == your_index` to see whose turn it is.

**`active_effects[]`**: replacement effects currently registered that
won't otherwise show up as `modified_*` values on cards. Most commonly:
damage prevention (e.g. Shelter from the Storm activated as an instant —
the card sits in graveyard, but its effect is still live). Each entry:

- `source_name` — the card that created the effect.
- `controller` — player_index that activated/owns it.
- `target_player` — player_index it applies to.
- `kind` — short slug like `"damage_prevention"`.
- `remaining_uses` — int charges left, or absent if not usage-limited.
- `summary` — one-line human-readable description.

Both seats see the same list. If you're calculating damage from an
attack and `active_effects` includes a `damage_prevention` targeting
the defender, expect each of your damage instances to be reduced by
the prevention's per-instance amount until it expires. Empty list when
nothing is active.

Pre-game equipment-selection decisions arrive with a stripped-down
`state` (`{"phase": "pre_game_setup", "note": "..."}`) — pick from
`options` based on the descriptions; you can't yet see hands or boards.

---

## What `action_id` looks like

The engine generates them; you echo them back verbatim:

- `play_<instance_id>` — play a card from your hand
- `defend_<instance_id>` — assign a card as a defender
- `activate_<instance_id>` — activate a weapon / equipment ability
- `equip_<name>` — pre-game equipment pick
- `pass` — decline the prompt

Don't construct `action_id`s yourself — copy them from `options[].action_id`.

---

## Mindset

- One decision per loop iteration. Don't try to "batch" plays. The
  engine will ask you again right after.
- Track *why* — what's your plan? what are you holding for? — at least
  briefly in your reasoning before each `act`. The match transcript
  becomes a teaching artifact.
- Only **your seat's** decisions will arrive. If `pending` is null and
  the game is in progress, it's the opponent's turn or the engine is
  resolving — `wait` again.
- The opponent's hand is hidden. Don't try to query it; the redactor
  will show `hand_size` and `hand_revealed[]` (cards previously peeked).
- When the game ends, `wait` returns with `status.status == "game_over"`
  and a `winner_seat`. Stop there.
