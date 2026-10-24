import { cardData, scripts } from "@fyendal/cards";
import { applyIntent, createGame, legalIntents as engineLegalIntents, projectStateFor } from "@fyendal/engine";
import { describe, expect, it } from "vitest";
import { randomAgent, type Intent, type Seat, type View } from "./agent.js";
import { runGame, type Replay } from "./game.js";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE } from "./list/fixtureLists.js";
import { pickDecklist } from "./list/pickDecklist.js";
import { renderDecision } from "./render.js";

/** Ira (Seat 0) vs Bravo (Seat 1), seed 1, between random Agents. */
const SEED = 1;
const replay = runGame({
  decklists: [pickDecklist(fixtureList(IRA_LIST_FILE), SEED), pickDecklist(fixtureList(BRAVO_LIST_FILE), SEED)],
  seed: SEED,
  startingSeat: 0,
  agents: [randomAgent, randomAgent],
}).replay;

/** Step 78 of that Game: turn 6, Bravo's action phase. Bravo holds four cards
 * and can pay for each play in several pitch orders; Ira has cards in the
 * graveyard, banish, equipment and weapon zones. */
const MID_GAME_STEP = 78;

describe("renderDecision", () => {
  it("numbers one entry per Intent after collapsing pitch orderings, each resolving to an Intent the engine accepts", () => {
    const { view, seat, legal } = decisionAt(replay, MID_GAME_STEP);

    const { text, intents } = renderDecision(view, seat, legal);

    expect(legal).toHaveLength(27);
    expect(intents).toHaveLength(18);
    const entries = numberedEntries(text);
    expect(entries).toHaveLength(intents.length);
    for (const intent of intents) {
      expect(legal).toContainEqual(intent);
      expect(() => stateAt({ ...replay, intents: [...replay.intents.slice(0, MID_GAME_STEP), intent] })).not.toThrow();
    }
    // The first ordering the engine lists is the one kept.
    expect(intents[0]).toEqual(legal[0]);
  });
});

/** The numbered Intent entries at the end of a rendering. */
function numberedEntries(text: string): string[] {
  const start = text.indexOf("Legal Intents:");
  expect(start).toBeGreaterThanOrEqual(0);
  return text
    .slice(start)
    .split("\n")
    .slice(1)
    .filter((line) => /^\d+\. /.test(line));
}

/** What the acting Seat was shown at `step` of a replay, and what it could do. */
function decisionAt(replay: Replay, step: number): { view: View; seat: Seat; legal: Intent[] } {
  const state = stateAt({ ...replay, intents: replay.intents.slice(0, step) });
  const seat: Seat = (state.pendingDecision?.player ?? state.priorityPlayer) === 1 ? 1 : 0;
  const legal = engineLegalIntents(state, seat).filter((intent) => intent.kind !== "concede" && !intent.kind.endsWith("-draw"));
  return { view: projectStateFor(state, seat), seat, legal };
}

function stateAt(replay: Replay) {
  let state = createGame({ decklists: [replay.decklists[0], replay.decklists[1]], cards: cardData, scripts, seed: replay.seed, startPlayer: replay.startingSeat }); // glossary: upstream
  replay.intents.forEach((intent, step) => {
    const seat = (state.pendingDecision?.player ?? state.priorityPlayer) === 1 ? 1 : 0;
    const applied = applyIntent(state, seat, intent);
    if (!applied.ok) throw new Error(`step ${step}: engine rejected ${intent.kind}: ${applied.error}`);
    state = applied.state;
  });
  return state;
}
