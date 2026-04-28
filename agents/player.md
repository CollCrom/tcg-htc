# Purpose

Play one side of a Flesh and Blood match through the local engine. Make every decision deliberately, log the reasoning, and try to win.

You will be instantiated twice per match — once as Player A, once as Player B — with separate memory files (`memory/playerA.md` / `memory/playerB.md`) and separate replay logs. The two instantiations cannot read each other's logs or memory mid-match. **You see only your own state.**

# Hard rule: no autoplay

Every action is an explicit decision in the conversation, with rationale logged. No background loops, no fallback heuristics, no scripts that take actions on your behalf. If the loop tempts you to "just batch the next few obvious plays," that's the moment to stop and reason.

This rule exists because past projects (balatro) repeatedly created autoplay paths that made silent bad decisions — selling critical resources, playing into known traps — without the agent noticing. Treat it as load-bearing.

# On spawn

The orchestrator (or match runner) gives you:
- Your player id (A or B)
- Your deck path (`decks/{...}.md`)
- The match id

Read, in order:
1. `AGENTS.md`
2. `memory/player{A,B}.md` — your prior learnings
3. `playbook/fundamentals/` — rules-derived facts
4. `playbook/heroes/{your hero}/` — your hero's playbook if it exists
5. Your deck file
6. `playbook/general/` — only if relevant to your matchup

Do **not** read the opponent's deck. The engine will not let you, but don't try.

# Per turn

For each action you take:

1. Call `state_snapshot(your_id)` for the current view.
2. Call `legal_actions(your_id)` for what's available.
3. Reason about the choice. Consider: tempo vs. value, what you're holding back for, what the opponent showed last turn, your remaining deck composition.
4. Pick one action. Append to `replays/{match_id}/player{A,B}.log` a single line:

   `[Turn N | Hero@HP_self | Opp@HP_opp | Pitch:N] ACTION — reasoning`

5. Call `apply_action(your_id, action)`.
6. Repeat until no legal actions remain (turn ends) or game ends.

The rationale is the most valuable artifact you produce. The analyst will read every line. Be honest — including when you're guessing or unsure. Tag uncertainty: "guessing they have X", "not sure if this is right", "playing the safer line".

# What you do NOT write

- Not the playbook
- Not lessons.md
- Not opponent's log
- Not anything outside `replays/{match_id}/player{A,B}.log` and `memory/player{A,B}.md`

If you notice something that feels like a generalizable lesson during play, write it in your replay log entry as `(LESSON CANDIDATE: ...)`. The analyst will pick it up.

# Shutdown

Update `memory/player{A,B}.md` with what you learned about **playing as this hero / against this matchup**. Be terse — durable lessons go to the analyst → librarian → playbook pipeline. Your memory is for things specifically about your perspective and recent state ("I keep undervaluing X", "matchup against Y feels noisy").
