# Engine Developer — Session Memory

## Auto-resolve invariant (commit 0c4c7c7)

`Game._ask` short-circuits decisions where:

- `len(decision.options) == 1`, AND
- `decision.min_selections == decision.max_selections == 1`.

Any other shape — multiple options, multi-select with multiple options, or
optional selections — round-trips to the player interface. Locked in by
`tests/core/test_auto_resolve.py` (added 2026-04-29).

When an analyst flags a "missing prompt" suspicion:

1. Check the decision's option count at the relevant code path.
   Resolution-step decisions (`build_resolution_decision`) include attack
   cards from hand + arsenal + banished + instants + a `pass` option, so
   they almost always have ≥2 options for the turn player. **They are
   NOT auto-resolved.**
2. The non-turn player's resolution-step decision is usually `[pass]`
   only (no attacks allowed). That **is** auto-resolved — but it's a
   no-op that only saves a redundant round-trip. The turn player always
   sees their prompt first.
3. Verify by checking the player's rationale log: did they record a
   pass? If yes, it was a player choice, not engine elision.

## Cindra-blue-vs-arakni-002 triage (2026-04-29)

Three suspicions, all investigated:

- **Klaive go-again post-hit prompt missing** — NOT A BUG. Player B was
  prompted at the resolution step (decision had attacks-from-hand +
  pass), and chose pass. Their own log L26 confirms ("chain closed,
  0 AP; LESSON CANDIDATE: ... I lost it by passing post-hit"). The
  auto-resolve only fires for the opposing player's no-option pass,
  which doesn't suppress the turn-player's go-again opportunity. Locked
  in via `tests/core/test_auto_resolve.py`.

- **Player A T6 stall** — NEEDS-MORE-INFO (player-agent / harness
  failure, not engine). Player A's log ends at T5; engine cleanly
  emitted `START_OF_ACTION_PHASE` for A at T6 and is sitting on a valid
  pending decision. The engine state machine is fine — `match_server`
  blocks `decide()` on a condition variable until `POST /action`
  arrives. There is no engine-side timeout, so an agent crash leaves
  the engine waiting forever. Reproduction recipe for next time:

  - Capture `server.log` (it was referenced in lessons.md but is missing
    from `replays/cindra-blue-vs-arakni-002/`). Without it we can't
    distinguish 409 loops from agent silence.
  - The 409 retry path in `playbook/match_protocol.md` (commit 8a84a9c)
    only addresses the agent-side handling; the server itself emits
    409s correctly when no decision is pending or ids are unknown
    (`tools/match_server.py:HttpBridgePlayer.submit`). No state-machine
    hole on the engine side.
  - To repro: kill the player A subprocess mid-match and watch B
    poll forever. That's the symptom here.
  - Possible engine-side mitigation (defer to harness owner): add a
    `--decide-timeout` on the bridge that returns a synthetic
    "agent timed out" error to /status after N seconds idle on a
    pending decision. Out of scope for this session.

- **DAMAGE_PREVENTED missing** — FIXED. Added a new `DAMAGE_PREVENTED`
  event type emitted by `ShelterPrevention.replace()`. Carries the
  original damage source, prevented amount, and prevention source name
  (`data['prevention_source']`). Also enriched
  `DEAL_DAMAGE.data['prevention'][]` with in-band info so analysts
  reading the events stream get the source / amount on either event.
  Test: `test_shelter_emits_damage_prevented_event` in
  `tests/abilities/test_remaining_infra.py`.

  Future damage-prevention sources should follow the same pattern:
  set `event.modified = True`, append a record to
  `event.data['prevention']`, and emit a `DAMAGE_PREVENTED`
  event with source / amount. Snapshot consumers continue to use
  `iter_replacement_effects()` / `describe()` for ongoing prevention
  surfacing — that path is unchanged.

## match_server liveness — pending_age_seconds (2026-04-29)

`GET /pending?player=X` now returns
`pending_age_seconds: float | null` alongside `pending` and `status`.
`HttpBridgePlayer._pending_since` is captured (`time.monotonic()`) when
`decide()` raises a decision and cleared when the response is consumed.
Observability only — server still does not time out decisions.
Locked in by `tests/integration/test_match_server.py::test_match_server_reports_pending_age_seconds`.
Wire-format docs updated in `playbook/match_protocol.md`.

## tools/match_server.py — sys.path bootstrap (2026-04-29)

The two pre-existing `tests/integration/test_match_server.py` failures
were not Windows port binding. Root cause: the test launches
`python tools/match_server.py` as a subprocess, and Python sets
`sys.path[0]` to `tools/` (the script directory), not the repo root.
`htc` is not installed (`pip show htc` → "not found"); inside pytest
the repo root is on `sys.path` via pytest's rootdir, so direct module
imports work, but a freshly-spawned `python tools/match_server.py`
crashes at `from engine.cards.card_db import CardDatabase`. The crash
is silent because the test redirects subprocess stdout/stderr to a
log file and only consults it after the boot timeout.

Fix: prepend `Path(__file__).resolve().parent.parent` to `sys.path` at
the top of `tools/match_server.py` (mirrors the pattern in
`tools/scenario_viewer.py`). If a future tools script is meant to be
run as `python tools/foo.py` and imports from `engine`, it needs the
same bootstrap.

Diagnostic recipe for similar "server didn't come up" failures: read
the redirected stdout file; if there's a Python traceback, the test's
HTTP timeout is masking a process crash, not a port race.

## TODOs / loose ends

- Only one place in the engine sets `modified=True` on DEAL_DAMAGE
  today (Shelter from the Storm). When new prevention cards land
  (e.g. Cindra's Mark of Magma reduction, Bravo's Crater Fist?),
  audit them to ensure they emit `DAMAGE_PREVENTED` too.
- `pending_age_seconds` is observability only. If we want a
  watchdog/auto-fail behavior for stalled agents, add it as a separate
  `--decide-timeout` flag rather than overloading this signal.

## Cindra-blue-vs-arakni-004 triage (2026-04-29)

Three observability bugs flagged by analyst, all addressed:

- **Bug 1 — `_return_to_brood` emits no event — FIXED.** Added
  `EventType.RETURN_TO_BROOD`. Emitted from the closure handler
  registered in `Game._become_agent_of_chaos` when the Demi-Hero
  reverts to the brood at the controller's next end phase. Event
  carries `source = brood_hero` and `data = {previous_hero, new_hero}`.
  Locked in by `tests/abilities/test_mask_of_deceit.py::TestReturnToBroodEvent`.

- **Bug 2 — `BECOME_AGENT` second transform looked mistagged —
  RECLASSIFIED, payload enriched.** The T5 ACTION transform in match
  004 was *correctly* stamped: Trap-Door returned to brood silently at
  T4 END, then on T5 Cindra attacked, Arakni defended with Mask of
  Deceit which fires `MaskOfDeceitTrigger` on `DEFEND_DECLARED` →
  re-transform mid-combat. This is exactly when Mask should fire (rule
  text "When this defends"). The fix is event-payload only: added
  `BECOME_AGENT.data['trigger_source']` carrying a free-form label
  identifying *why* the transform fired (`"Mask of Deceit"` vs
  `"Arakni end-phase ability"`). Locked in by
  `tests/abilities/test_mask_of_deceit.py::TestBecomeAgentTriggerSource`.
  **Lesson:** before assuming an event is mistagged, trace the trigger
  registry — multiple cards can emit the same event, and the
  apparent-bug may be a payload-disambiguation gap, not a state-machine
  hole. The `_return_to_brood` closure is the silent step that hides
  the cycle from the analyst.

- **Bug 3 — `CindraRetributionTrigger` Fealty creation emits no event
  — FIXED + scope expanded.** Two real bugs found here:
  1. The trigger recorded `target_was_marked` at ATTACK_DECLARED time
     and missed mid-attack mark applications (Exposed-as-attack-reaction
     in match 004 T17 marks the defender between ATTACK_DECLARED and
     HIT). Refactored to read `event.data["target_was_marked"]` from
     the HIT event directly — `Game._resolve_combat_chain` already
     captures the pre-hit mark state (game.py:1704) precisely so triggers
     can see it. Removed the `_target_was_marked` instance field and the
     ATTACK_DECLARED branch.
  2. The shared `create_token` helper (`engine/cards/abilities/_helpers.py`)
     did not emit `CREATE_TOKEN`. All token-creation sites
     (Frailty Trap, Inertia Trap, Death Touch, Codex of Ponder/Fealty,
     Bloodrot Pox, Silver, etc.) flowed through it without surfacing
     anything to events.jsonl. Helper now emits `CREATE_TOKEN` with
     `source_name` field. The lone non-helper site
     (`_create_graphene_chelicera` — weapon-slot token, can't use the
     permanent-zone helper) was updated to emit too. `_create_fealty_token`
     in `Game` now routes through the helper to avoid double-emit.
  Locked in by:
  - `tests/abilities/test_hero_abilities.py::test_cindra_creates_fealty_token_when_mark_applied_mid_attack`
  - `tests/abilities/test_hero_abilities.py::test_cindra_fealty_creation_emits_create_token_event`
  - `tests/abilities/test_hero_abilities.py::test_create_token_helper_emits_create_token_event`

## New event types added (2026-04-29)

- `EventType.RETURN_TO_BROOD` — inverse of `BECOME_AGENT`. Emitted
  when a Demi-Hero (Agent of Chaos) reverts to the brood/base hero
  at the controller's next end phase.

## Patterns observed about event-emission gaps

The recurring failure mode: **a trigger calls a state-mutation helper
that doesn't emit an event**, leaving only `log.info` to surface the
fact something happened. This was true for return-to-brood,
Fealty creation, AND the Graphene Chelicera weapon-token. Audit rule
for new triggers/helpers: if it mutates state that the analyst could
care about, emit an event with a `source_name` (or `trigger_source`)
field naming the rule that fired it. Tokens, transformations,
and revert/reset-style state changes are the high-risk surface.
