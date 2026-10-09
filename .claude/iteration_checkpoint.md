# Iteration checkpoint

## Matches processed

- **cindra-blue-vs-arakni-002** (processed 2026-04-29; corrected 2026-04-29; integrated 2026-04-29) - `replays/cindra-blue-vs-arakni-002/lessons.md`. Status: **integrated by librarian**. Match did not reach a terminal state (Player A stalled at T6 action phase); usable for play-pattern lessons but not for win/loss claims.
  - LC-004 (CONFIRMED) → `playbook/heroes/arakni/fundamentals.md` (Marionette transform timing).
  - LC-001 (INFERRED), LC-002 (INFERRED), LC-003 (HYPOTHESIS) → `playbook/open-questions.md`. Per role spec, single-match INFERRED claims do not promote until corroborated by a second match.
  - Engine-bug findings: **all resolved** (Klaive go-again = player error, T6 stall mitigated via `pending_age_seconds` exposure, Shelter prevention now emits `DAMAGE_PREVENTED` event). Not propagated to playbook.
  - Data-quality notes: kept in lessons file; not playbook material.
  - **Correction pass:** original T1 narrative had four errors (Whittle "applies Mark", Whittle "consumes Mark", power double-count, wrong "first decisive moment"); revised by analyst — Decisive Moments + LC-001 + LC-004 rewritten, meta-lesson appended to `memory/analyst.md`.

- **cindra-blue-vs-arakni-004** (processed 2026-04-29; LC-004 corrected 2026-04-30; integrated 2026-04-30) — `replays/cindra-blue-vs-arakni-004/lessons.md`. Project's first complete match (Cindra Blue wins T23 lethal, 30-life margin). 152 decisions across both seats via `tools/auto_player.py`.
  - **LC-001 (CORROBORATED + refined)** → `playbook/heroes/arakni/fundamentals.md` updated. Agent of Chaos form is RNG-selected via `state.rng.choice(player.demi_heroes)` (heroes.py:392); 002 hit Tarantula, 004 hit Trap-Door then Redback after return-to-brood + re-mark.
  - **LC-002 (still INFERRED)** → kept in `playbook/open-questions.md` with mixed-evidence update (T7 violation, T15 adherence). Awaiting 3rd match.
  - **LC-003 (CORROBORATED)** → `playbook/heroes/cindra/fundamentals.md` (new file). Cindra's Fealty trigger fires on Cindra's own attack hitting a marked opponent.
  - **LC-004 (INFERRED, REVISED)** → `playbook/open-questions.md`. Originally misattributed equipment destruction to Scale's rider; corrected to Blade Break on `COMBAT_CHAIN_CLOSES` after Arakni stacked three Blade-Break defenders. Meta-lesson appended to `memory/analyst.md`.
  - **LC-005 (HYPOTHESIS)** → `playbook/open-questions.md`. Cindra-first vs Arakni significantly better than Cindra-second. Single-data-point speculation.
  - **LC-006 (INFERRED, judgment-call promotion)** → `playbook/heroes/arakni/fundamentals.md` with explicit caveat. Single-match but mechanism-concrete; cross-references LC-004 in case they consolidate.
  - **Engine notes (RESOLVED 2026-04-29 by engine-developer):**
    - **Bug 1 — `_return_to_brood` emits no event: FIXED.** Added new `RETURN_TO_BROOD` event type, emitted from the closure handler in `Game._become_agent_of_chaos`. Carries `previous_hero` + `new_hero` + brood-hero source.
    - **Bug 2 — `BECOME_AGENT` second transform mistagged turn/phase: RECLASSIFIED — NOT a timing bug.** The T5 ACTION transform was correctly stamped: it was `MaskOfDeceitTrigger` firing on `DEFEND_DECLARED` mid-combat (Mask grants the Marionette transform-back-from-Brood when defending), not the end-phase Marionette trigger. Cause: previous Arakni form returned to brood at T4 END (silently), Mask defended at T5 ACTION → re-transform. Fix: enrich `BECOME_AGENT.data['trigger_source']` to disambiguate (`"Mask of Deceit"` vs `"Arakni end-phase ability"`) so analysts can trace why each transform fired.
    - **Bug 3 — Fealty token CREATE_TOKEN missing: FIXED + ROOT-CAUSE EXPANDED.** Two issues: (a) `CindraRetributionTrigger` recorded mark-state at ATTACK_DECLARED time, missing mid-attack mark applications via Exposed (the actual T17 sequence in match 004 — Demonstrate Devotion attacked unmarked Arakni, Exposed marked mid-resolution, HIT had `target_was_marked=true` but trigger had recorded False). Switched to reading `event.data['target_was_marked']` from HIT directly (Game already captures this pre-handler-run). (b) The shared `create_token` helper didn't emit `CREATE_TOKEN`. Audited and fixed: helper now emits with `source_name`; `_create_graphene_chelicera` (the lone non-helper token site, weapon slot) also emits.

## Drift signals for schema-critic

- `playbook/heroes/{hero}/` layout in `playbook/README.md` doesn't enumerate `fundamentals.md`, but two instances now exist (arakni and cindra). Two paths logged in `playbook/proposals/notes-for-schema-critic.md`.
- `playbook/matchups/` directory doesn't exist but LC-004's promotion target wants to live there. Conflict with the README's documented per-hero `matchups/` placement. Logged in `playbook/proposals/notes-for-schema-critic.md`.

## Pending integration items

- (none — match 004 fully integrated)

## Playbook-reader gap (resolved 2026-05-04)

User flagged the schema-critic's observation that nothing in the playbook reaches a player at decision time. Verified the contradiction:

- `agents/player.md` lines 20-26 prescribed broad playbook reads on spawn (`fundamentals/`, `heroes/{hero}/`, `general/`).
- `playbook/player_spawn_prompt.md` (the actual operator template) stripped reads to `match_protocol.md` + the deck file with a note: "blew the budget on the first run."
- `tools/auto_player.py` (the per-decision driver used for matches 002 and 004) had zero references to `playbook/`.

So the curated lessons-flow had a producer (analyst → librarian) but no consumer past the librarian — the schema-critic's anti-case #1 ("a consumer appears") was the unresolved structural question.

**Resolution: hybrid (option 3 + auto_player wiring).**

- `tools/auto_player.py` now embeds `playbook/heroes/{slug}/fundamentals.md` into the cached system prompt (new `--hero-slug` CLI flag, new `_load_playbook_excerpt`). Match-static, cache-stable, prefix prompt-cache amortizes it across all ~150 decisions per match. This is the load-bearing change — auto_player is the de-facto player.
- `playbook/player_spawn_prompt.md` adds `$HERO_SLUG` substitution + reads `playbook/heroes/$HERO_SLUG/fundamentals.md` on spawn. Single small file (~25 lines), well under the budget that broke the prior run. Operator notes updated to point future budget-safe slices at auto_player's cached prompt rather than this on-spawn list.
- `agents/player.md` rewritten on-spawn list to match: `match_protocol.md` + hero `fundamentals.md` + deck. Explicit "what you intentionally do NOT read" subsection documents which slices are deferred and why.
- New test `test_playbook_excerpt_loads_hero_fundamentals` pins the wiring (covers present file, missing file, no slug). Existing `test_full_system_prompt_exceeds_opus_47_cache_minimum` updated to pass the new format key.
- Tests: 1055 → 1056 (+1 new, no regressions). Auto_player suite: 11 → 12.

**Validation strategy:** the next match will exercise this end-to-end. Watch the auto_player launch logs for `system_prompt built: N chars` (should grow by ~2.7K when `--hero-slug cindra` is used) and confirm `cache_read_input_tokens` keeps hitting after the first decision (caching invariant unchanged because the playbook excerpt is cache-stable).

**Follow-up for next match runner:** when launching `auto_player.py`, pass `--hero-slug cindra` for Cindra seats and `--hero-slug arakni` for Arakni seats. The flag is optional (graceful skip with placeholder marker if omitted), so old launch commands still work.

This closes anti-case #1 in `playbook/proposals/2026-04-29-no-change-too-early.md`. The schema-critic's other 4 anti-cases (LC-004 promotion duplication, ~5 hero `fundamentals.md` files, new emergent category, `general/` shape question on LC-002 promotion) remain open.

## Schema-critic reviews

- **2026-04-29 (first spawn)** — produced `playbook/proposals/2026-04-29-no-change-too-early.md`. Verdict: **no change**. Both librarian drift signals (`fundamentals.md` not in README's per-hero layout; `matchups/` placement conflict for LC-004) are real but not load-bearing yet — the playbook has no decision-time consumer (player sub-agents don't read playbook by operator design per `playbook/player_spawn_prompt.md`), and total content is 4 files. Proposal documents 5 anti-cases (consumer appears, real duplication on LC-004 promotion, ~5 hero `fundamentals.md` files, new emergent category, LC-002 promotion forcing the `general/` shape question) that should trigger a future schema-critic to act. Awaiting librarian/orchestrator response.
- **2026-05-04** — appended dated closure note to `playbook/proposals/2026-04-29-no-change-too-early.md` recording that anti-case #1 ("a consumer appears") fired via the auto_player `--hero-slug` wiring. Anti-cases #2-#5 remain open triggers.

## Stateless per-decision spawn prototype (2026-05-05)

User ruled `auto_player.py` (Anthropic API path) off the table for cost (~$7/run on Opus, ~$1.40/run on Sonnet, both unwelcome). That made Option B (Claude Code sub-agent players) the only path to matches. Option B historically stalled at 30-50 decisions due to O(N²) transcript growth. Prototype goal: stateless per-decision spawns, each invocation a fresh CC sub-agent with a compact briefing, asymptotic O(N × briefing) instead of O(N²).

**Engine-developer deliverable** (worktree branch `feat/spawn-player-prototype`, commits `fa2946b` initial + `f406fc5` Windows fixes):
- `tools/spawn_player.py` — single-decision driver. Fetches pending decision via `agent_cli.py`, builds compact briefing (match protocol inlined + hero `fundamentals.md` + deck + redacted state + options), spawns `claude -p --output-format text` with briefing on stdin, parses strict `ACTION:` / `RATIONALE:` two-line contract, posts via `agent_cli.py act`, exits. Engine-developer pivoted from in-CC `Agent` tool (not reachable from a CLI script) to `claude -p` subprocess — same structural property (fresh session, no inherited transcript).
- `tools/_prototype_driver.py` — throwaway loop driver alternating seats based on `agent_cli.py pending`.
- 19 unit tests for briefing builder + reply parser. All green.

**Live-run findings (smoke-001 / cindra-blue-vs-arakni-005 setup):**
- **39 successful decisions** (17 seat A Arakni + 22 seat B Cindra) before CC subscription quota wall hit at decision 40 ("You're out of extra usage — resets 3am America/New_York"). Past the 30-50 stall point that killed long-session matches 002 + 003. **Structural validation: complete. The O(N²) collapse is gone.**
- **Per-decision wall-clock: 9-147s, mean ~50s for real-game decisions, ~12s for pre-game equipment / pitch / arsenal picks.** A full 150-decision match would be ~75-90 minutes wall-clock plus the CC quota cost of 150 fresh sub-agent spawns.
- **Two bugs found and fixed during the run** (committed in `f406fc5`):
  1. WinError 206 (Windows command-line length limit ~32K chars). Briefing was passed as argv; combined deck + protocol + state + options crossed the limit by decision 3. Fix: pass briefing via stdin (`claude -p` accepts via `--input-format text` default).
  2. UnicodeEncodeError on Windows because `subprocess.run(text=True)` defaults to cp1252. Briefings contain non-cp1252 chars (e.g. `→` from playbook content). Fix: explicit `encoding='utf-8', errors='replace'`.
- **Decision quality looks meaningful.** Spot check: T1 seat A picked Stalker's Steps citing "Arakni's attack-chaining gameplan" (engaged with playbook content). Mid-game decisions chose between defending and passing, picked appropriate pitch cards, activated daggers. No obvious random or absurd plays in the 39 captured rationales.
- **First-player observation worth flagging:** despite swapping decks (Arakni on seat A, Cindra on seat B with seed 23 — match 004 had it reversed), Cindra still went first per engine RNG. Same seed → same `turn_player_index 1` regardless of who's in which seat. So this run does NOT serve as the LC-005 controlled comparison; that needs a deliberate seed search (or engine first-player override).

**Artifacts on disk** (worktree at `.claude/worktrees/agent-ac8a72011076ef6ea/`):
- `replays/smoke-001/events.jsonl` — engine event stream
- `replays/smoke-001/playerA.log` — 17 Arakni rationales
- `replays/smoke-001/playerB.log` — 22 Cindra rationales
- `replays/smoke-001/prototype-metrics.log` — 47 entries (39 ok + 8 fail records from the bug iterations)

**State of play / decision needed from user:**
- Match server died when the failed background run terminated. In-memory game state is gone; `events.jsonl` may be sufficient for analyst on the partial. Or treat this as throwaway prototype data and run a real match later.
- The "auto_player off the table" decision was made when the user assumed Option B was budget-free. Now we know Option B costs CC quota at a rate that exhausted the user's "extra usage" tier in ~38 decisions. The cost picture has changed; user may want to revisit. Comparison points: `auto_player.py` on Sonnet 4.7 at ~$1.40/run (predictable, finishes in ~5 min) vs. `spawn_player.py` on CC quota (variable, may take ~75 min, hits a hard quota wall mid-match). Both deliver the stateless-per-decision shape; the question is which budget the user prefers to spend.
- PR #113 (`feat/match-004-cycle`) still open with the auto_player infrastructure. If the user reverses the "off the table" decision, that PR's work is reusable. If not, auto_player.py becomes dead code on main once #113 merges.

**Prototype branch `feat/spawn-player-prototype` status:** 2 commits. Not yet pushed. No PR opened. Awaiting user direction on whether to keep, push, or merge.

## Open PRs

- **#113** `feat/match-004-cycle` — https://github.com/CollCrom/tcg-htc/pull/113. Covers all commits since PR #112 merged: per-decision Anthropic API driver (`tools/auto_player.py`), match cindra-blue-vs-arakni-004 ran end-to-end on this driver, three engine observability fixes (one of which was a real Cindra gameplay bug in `CindraRetributionTrigger`), full lessons-flow integration (analyst → engine-dev → librarian → schema-critic). 1054 → 1062 tests passing. Status: opened, awaiting CI + review/merge. **Don't push more commits to `feat/match-004-cycle` after merge — open a fresh branch instead** (PR #112 lesson, captured in `memory/orchestrator.md`).
