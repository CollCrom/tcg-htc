# Analyst memory — patterns about *how to analyze well*

(Knowledge about the game itself goes in lessons.md / playbook, not here.)

## Patterns observed across matches processed so far

### How to disambiguate "engine bug" from "player error" from "stale event-stream"

- The events.jsonl is sparse — many decisions and prevention effects do not generate their own events. `modified=true` on DEAL_DAMAGE is often the only signal a damage-prevention effect (Shelter from the Storm, etc.) triggered. `engine/rules/events.py:223` documents this. **Don't conclude "the player lied about activating X" just because there's no explicit event for X**; check whether the resulting damage event is `modified`.
- When a player's log self-flags a "lesson candidate" or "engine modifier I don't see," treat it as a hypothesis to verify via the event stream and rules — not an automatic engine bug. The Klaive go-again case in cindra-blue-vs-arakni-002 is genuinely ambiguous (could be either) — those should be routed to engine-developer with the ambiguity called out, not asserted as bugs.
- Server.log access patterns disambiguate "engine crashed" vs "player agent stalled". If `/pending` keeps returning 200 but no `POST /action` arrives from one side, the player agent is the failure point, not the engine.

### How to verify seat assignment

- Don't trust the directory name (e.g., "cindra-blue-vs-arakni-002") to imply Player A = Cindra. Confirm via the START_OF_TURN events and the cards played: Spinneret/Whittle are Arakni cards, Kunai of Retribution is Cindra. Match those to the `target_player` field. (In this match: A=0=Cindra, B=1=Arakni; Arakni went first.)

### How to ground claims about decisive moments

- **Look for state-change events first** (BECOME_AGENT, hero life changes, large damage events). These bound the game's trajectory and usually point to the real inflection.
- **Cross-reference the rules** before declaring a transformation/trigger "obvious" — Mark removal-on-hit (rule 9.3.3) explained why a turn-1 mark didn't transform Marionette early; without checking, an analyst could write a wrong story about transformation timing.
- **Rationale logs explain intent, events explain outcome.** When the two disagree, events win. Player A's "activate_59" was not in the event stream as its own event but the resulting damage event was `modified=true`, so the action *did* happen — the disagreement was about event surfacing, not about the action.

### Signs a "lesson candidate" is actually two tangled lessons

- Pitch-discipline failures often co-occur with planning failures. e.g., Player A pitched a 3-pitch Blue for a 1R cost AND arsenaled a card that went dead. These are separate decision rules (pitch discipline vs. arsenal hedging vs. plan flexibility) — don't merge them into a single "Player A misplayed turn 2" lesson.

### Things to keep an eye out for next time

- When neither player's rationale matches the event stream, sanity-check by counting: total damage in events vs. life-total deltas implied by rationale.
- When a match doesn't reach a terminal state, prefix the result line clearly ("**No game-end**") so downstream agents (librarian) don't promote a "Player B wins" claim that isn't grounded.
- The engine emits Tarantula's `-1 life` rider as some other event type (or possibly not at all distinct from HIT). Need to track this in next Arakni match to be sure.
- Two recent commits suggest classes of bugs to consider when something looks weird:
  - `8a84a9c` (player sub-agent 409 handling) — agent-side prompt hangs.
  - `0c4c7c7` (auto-resolve forced single-option decisions) — could change whether go-again prompts surface.

## Process improvements

- For matches where one player log is much shorter than the other, expect the shorter side has gaps in rationale. Don't assume silence = "no decision was made"; the engine may have auto-resolved or the agent may have crashed.
- Always read `ref/rules/comprehensive-rules.md` for any keyword you're about to make a claim about (Mark, Stealth, Piercing, etc.) — don't rely on memory of card text.

## Meta-lessons from the cindra-blue-vs-arakni-002 correction pass (2026-04-29)

A prior pass of this match got four T1 facts wrong. The correction surfaced these durable rules for future matches:

### Derive combat math from `events.jsonl`, not from prose recall

- Always cross-check three numbers per attack: (a) base power from the card's TSV row at the **specific color** that was played, (b) modifiers attributable to other cards/abilities resolved this turn, (c) the `DEAL_DAMAGE` event's `amount` field. If your reconstructed (base + mods − blocks) doesn't equal the event's amount, your reconstruction is wrong, not the engine.
- Don't write things like "Whittle (4p, +3p from Spinneret)" — that double-counts. Express attacks as `power N base + M from <source> = X attack, blocked for Y, Z net`. The reader (and you) will catch arithmetic errors.
- Card variants matter. Read the color suffix in the chain-link string (`CardDefinition('Foo' (Blue))`) on `ATTACK_DECLARED`/`PLAY_CARD` data — Red/Yellow/Blue have different stats and different bonus magnitudes (Spinneret +3/+2/+1, Whittle 3/2/1 power, etc.). Confirm against the deck list (`ref/decks/decklist-*.md`) — if a deck only contains one color of a card, that's the only one that can have been played.

### Distinguish "Granted Keywords" (col 16) from "Interacts with Keywords" (col 18) in `data/cards.tsv`

- Col 16 = the card *applies/grants* this keyword (e.g., Mark of the Black Widow grants Mark).
- Col 18 = the card *cares about* this keyword on something else, but does **not** apply it (e.g., Whittle from Bone interacts with Mark — it triggers when the defender is already marked, but does not mark anyone).
- Before writing "card X applied Mark," check col 16. If Mark is in col 18 only, the card is a Mark-checker, not a Mark-applier. Cross-reference with `engine/cards/abilities/<class>.py` to confirm the implementation matches.

### Mark removal mechanics (rules 9.3.2b, 9.3.3) — only hit events remove Mark

- Mark persists until: (1) the marked hero is hit by an opposing source (Mark removed *as part of* that hit event, per 9.3.3); or (2) the hero ceases to exist (9.3.2b).
- Mark is **not** "consumed" by ability text on the attacking card (e.g., Whittle's "if defender is marked, equip a Chelicera" rider — the equip and the hit are independent; a fully blocked Whittle that successfully attacks a marked hero still equips a Chelicera and does not remove Mark, while a hit removes Mark regardless of source-card text).
- The HIT event's `target_was_marked` field reports the state **at the moment of the check**. If Mark was *applied as a rider* on this hit (e.g., Klaive's mark-on-hit), `target_was_marked` will read `false` because the application happens after the check; the hero is then marked going into end-of-turn. Don't infer "Mark was missing the whole time" from a single `target_was_marked=false` reading.

### Find the *first* state-change before naming a "decisive moment"

- The previous run named T1 as the seed of B's gameplan because Whittle was misread as applying Mark. The actual first Mark in the match arrived at T3 via Klaive — three turns later. **Before claiming "X was the seed," search the events stream for the *earliest* event of the type your story depends on.** For Mark-driven stories: search for HIT events where Mark was applied (either `target_was_marked=true` indicating prior Mark, or a Mark-applier source on a hit with `target_was_marked=false`).
- Corollary: turn-1 openers in a sparse event stream are often *not* decisive. Tempo-changing events tend to be the first BECOME_AGENT, the first big DEAL_DAMAGE with `modified=true`, or the first state-change of a hero/zone — not the first chip damage.

### When you correct yourself, propagate the correction through every section

- A wrong premise about T1 Whittle leaked into Decisive Moments, Plausible Mistakes ("Cindra was already marked from T1 Whittle"), Novel Lines ("every dagger swing re-applies Mark"), LC-001, and LC-004. When fixing one anchor fact, search the whole lessons file for derived claims that depended on it; don't only fix the section the orchestrator pointed at.
