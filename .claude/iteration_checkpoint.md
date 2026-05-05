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

## Schema-critic reviews

- **2026-04-29 (first spawn)** — produced `playbook/proposals/2026-04-29-no-change-too-early.md`. Verdict: **no change**. Both librarian drift signals (`fundamentals.md` not in README's per-hero layout; `matchups/` placement conflict for LC-004) are real but not load-bearing yet — the playbook has no decision-time consumer (player sub-agents don't read playbook by operator design per `playbook/player_spawn_prompt.md`), and total content is 4 files. Proposal documents 5 anti-cases (consumer appears, real duplication on LC-004 promotion, ~5 hero `fundamentals.md` files, new emergent category, LC-002 promotion forcing the `general/` shape question) that should trigger a future schema-critic to act. Awaiting librarian/orchestrator response.
