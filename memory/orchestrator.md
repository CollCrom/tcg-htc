# Orchestrator memory

Patterns about *how to coordinate this team specifically*. Game knowledge goes in `playbook/` via the librarian. Match state goes in `.claude/iteration_checkpoint.md`. This file is just for "things I learned about running the loop."

## Spawning patterns

- **Parallel spawn for non-overlapping work.** Single message with multiple `Agent` tool calls. Used successfully for librarian + engine-developer (touch different file trees: `playbook/` + `memory/librarian.md` vs `engine/` + `tests/`). Use this pattern aggressively when concurrency rules allow.
- **Concurrency hard rules** (from `agents/orchestrator.md`): librarian + schema-critic CANNOT run concurrently (both edit `playbook/`). Engine-developer cannot run while a match is in progress. Player A + Player B always run in parallel during a match.
- **Don't load engine source / card DB / rules text into your own context.** Delegate by spawning the relevant role with that role's file as system prompt. The orchestrator's job is routing, not analysis.

## Subagent failure recovery

- **Subagents that time out or stall often leave partial work on disk.** Always run `git status --short` before deciding to re-spawn. Heavy work may have landed; the orchestrator can finish mechanical bookkeeping inline (open-questions update, README refresh, memory-file appends) rather than re-spawning.
  - Worked on the librarian after a stream-idle timeout: both `fundamentals.md` files made it to disk; orchestrator finished the rest.
- **Partial findings from failed runs are valuable.** When re-spawning, fold the prior session's intermediate insights into the new brief.
  - Engine-dev's stalled run identified `MaskOfDeceitTrigger` as the actual cause of Bug 2's "wrong turn/phase tag" — the retry brief leaned on this, saved time.
- **Backend issues can correlate.** Both librarian and engine-developer hit infrastructure problems on the same parallel spawn. If both fail simultaneously, suspect the platform first; re-spawn after a brief delay rather than immediately.

## Match-running patterns

- **Auto_player is the default for matches**, not the long-lived Claude-Code-sub-agent player. The sub-agent player exists in `playbook/two_agent_match.md` as Option B but pays O(N²) token cost — capped real games at ~30-50 decisions before usage limits triggered (matches 002 + 003 both stalled this way).
- **Polling cadence for in-progress matches: 270 seconds** (~4.5 min). Within Anthropic's 5-min cache TTL, low overhead, catches game-end within one tick. Use `ScheduleWakeup` not Monitor — wakeups give you back control with a clean status check, not a stream of noise.
- **Status check at each wakeup**: match-server status + per-seat log line count + last 2-3 rationale entries per seat. Cheap and surfaces both progress (turn advancing) and quality (rationales coherent, not noise).
- **Pre-spawn API key check.** `auto_player.py` reads `.env` at repo root. Verify with a fresh subprocess before launching agents: `python -c "from tools.auto_player import _load_dotenv; _load_dotenv(); ..."`. Don't echo the key.

## Analyst pattern: expect a correction pass

- **Both analyses this session needed correction passes.** Match 002 (Whittle Mark misattribution) and match 004 (Scale equipment-destruction misattribution). Same shape both times — narrative-vs-event-stream causal mismatch. Captured as meta-lesson in `memory/analyst.md`.
- **Budget for this.** When spawning the analyst, expect to need a follow-up correction-spawn after the user spots an error. The analyst's first output is rarely fully correct, but the corrections are small and surgical.
- **The user is part of the QA loop.** They've caught both correction-worthy errors by asking sharp follow-up questions ("did Whittle apply Mark?", "was the Scale Draconic?"). When surfacing analyst findings to the user, lead with the most surprising/load-bearing claims so they can scrutinize.

## PR / branch hygiene

- **Always check PR state before assuming a branch's commits will land.** `gh pr view {n} --json state` returns `MERGED` / `OPEN` / `CLOSED`. If MERGED, future commits to the same branch DON'T get into it.
  - Burned this session: PR #112 was merged mid-session. Edited its description after the merge (succeeded silently), pushed 4 more commits to the branch, declared "PR updated" — they were never in a PR. User caught it. Created PR #113 from a fresh branch off the post-merge HEAD.
- **Squash-merged branches lose commit identity** — the original branch's commits don't exist on main as discrete commits. The diff `origin/main..HEAD` is the truth, not the commit log.
- **Naming convention so far:** `feat/match-{NNN}-cycle` for a complete lessons-flow cycle (analyst → engine-dev → librarian → schema-critic). PR #113 is `feat/match-004-cycle`.

## Lessons-flow cycle (what end-to-end looks like)

For any complete match:

1. **Analyst** on the replay → produces `replays/{match}/lessons.md` with LC-001..N tagged CONFIRMED/INFERRED/HYPOTHESIS.
2. **User reviews** the analyst's output. Expect to need a correction spawn for at least one LC.
3. **Engine-developer** on any flagged engine concerns (often there are 1-3 observability gaps even in clean matches).
4. **Librarian** on the corrected lessons → routes verdicts (CONFIRMED + multi-match → playbook; INFERRED single-match → open-questions; HYPOTHESIS → open-questions; INFERRED with concrete mechanism + immediate value → judgment-call promote with caveat).
5. **Schema-critic** ONLY when drift signals accumulate (≥2 instances of an ad-hoc convention, or a routing call the librarian couldn't make cleanly). Don't spawn after every match — spawn when the librarian has filed structural questions in `playbook/proposals/notes-for-schema-critic.md`.

Steps 3 + 4 can run in parallel (different file trees).

## Role-spec / spawn-template / driver-tool drift

Three artifacts are supposed to agree about what the player reads on spawn: the role spec (`agents/player.md`), the operator template (`playbook/player_spawn_prompt.md`), and the actual driver (`tools/auto_player.py`). They drifted into mutual contradiction over four matches — the role spec said "read playbook," the template said "don't read playbook (budget)," the driver never touched the playbook at all. The schema-critic spotted it but is scoped to playbook structure, not cross-artifact contracts. The orchestrator's job is to notice "no consumer past the librarian" as a coordination smell and reconcile. Lesson: when a producer-consumer pipeline (analyst → librarian → playbook → ???) has the last hop go nowhere, that's a coordination failure regardless of how good each individual role's output is. Triggers to watch for: (a) a role spec whose on-spawn list hasn't been exercised in N matches, (b) an operator template carrying a "we tried this once and it broke" comment with no follow-up plan, (c) a producer artifact (the playbook) that no automated consumer references. The reconciliation pattern that worked: fix the load-bearing artifact first (auto_player, the actual player), then update the spec and template to match. Don't try to fix all three by spawning roles — this is inside the orchestrator's remit and small enough to do inline.

## CC subscription quota as a hard ceiling on Option B

`spawn_player.py` (stateless per-decision spawn via `claude -p`) burns CC subscription quota at a rate that exhausted the user's "extra usage" tier in 39 decisions during the 2026-05-05 prototype run. The quota wall is opaque (no telemetry surfaced) and hits mid-spawn with a stdout banner ("You're out of extra usage — resets 3am"). Plan match runs around this constraint:

- A full match (~150 decisions) almost certainly does NOT fit in one quota window for the user's current plan.
- Per-decision wall-clock for real gameplay is ~50s (full state JSON, many options); pre-game / pitch / arsenal picks are ~12s. Don't extrapolate from smoke-test pace — the smoke was all pre-game equipment picks.
- Auto_player on Sonnet 4.7 (~$1.40/run, predictable, ~5 min wall-clock per match, no quota wall) is the structural alternative. The user ruled it out on dollar cost; if quota becomes the binding constraint, that decision is worth re-opening.

## The "third option" the schema-critic missed

When Option A (auto_player on the API) is too expensive in $ and Option B (long-session sub-agent) collapses on O(N²) transcript growth, **stateless per-decision spawns** (`spawn_player.py`, `claude -p` per decision, no inherited transcript) are the workable middle. The schema-critic's anti-cases enumerated structural reasons to revisit the playbook, but didn't enumerate "the consumer's cost model is wrong, find a third one" as a possibility. Worth remembering: when both currently-listed options have load-bearing problems, the right move may not be picking between them but inventing a third.

## Don't spawn the orchestrator as a subagent

The orchestrator role file presumes whoever embodies it can spawn other roles via the `Agent` tool. A `general-purpose` subagent spawned by the top-level CC instance does NOT have access to the `Agent` tool (only the top-level CC session does). So routing user messages to a "spawned orchestrator" works for Q&A and planning but breaks the moment you need to actually launch engine-developer / player / etc. Lesson: the orchestrator role lives at the top level of a CC session, not nested. If the user wants "interface with the orchestrator directly," that means the top-level Claude reads the orchestrator role file and follows its discipline as conversation context — not a nested spawn.

## Worktree isolation for prototype work

Used `Agent(isolation: "worktree")` for the spawn_player prototype build. Worked well: engine-developer's branch (`feat/spawn-player-prototype`) created off main, isolated from the dirty changes on `feat/match-004-cycle` in the main working tree. After the live run, the worktree retains the prototype branch + replay artifacts; commits made there don't pollute the parent's working tree. Use this pattern any time the prototype work and the existing dirty state would tangle.

## Open questions / state at handoff

- PR #113 (`feat/match-004-cycle`) is open. Awaiting CI + merge.
- Schema-critic verdict on the playbook: NO CHANGE. 5 concrete triggers documented for re-opening (see `playbook/proposals/2026-04-29-no-change-too-early.md`); anti-case #1 closed 2026-05-04 by `auto_player.py` `--hero-slug` wiring.
- LC-002 (pitch discipline) needs a 3rd match for promotion or kill — currently stuck with mixed evidence across matches 002 + 004.
- LC-004 (Blade-Break trade pattern) needs a 2nd Cindra-vs-Arakni match for corroboration. Mechanism is rules-grounded so single corroboration suffices.
- LC-005 (Cindra-first vs Arakni-first hypothesis) needs a controlled comparison: deliberately seed a Cindra-vs-Arakni match where Arakni goes first. Note from 2026-05-05 prototype run: simply swapping which seat gets which deck does NOT flip first player on the same seed (engine RNG picks `turn_player_index` independently of seat-deck assignment). Seed search needed.
- **Next match path:** prototype validated structurally but quota-blocked. User decision needed on whether to (a) revisit auto_player-on-Sonnet (cheapest reliable path, ~$1.40/run), (b) try `spawn_player.py` again after CC quota resets and accept multi-window matches, or (c) park matches and pivot to non-match work (engine coverage, deck refinement). PR #113 carries the auto_player infrastructure if (a).
- **Prototype branch:** `feat/spawn-player-prototype` has 2 commits (`fa2946b` + `f406fc5`). Not pushed. No PR. Awaiting user direction.
