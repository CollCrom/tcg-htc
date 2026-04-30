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
