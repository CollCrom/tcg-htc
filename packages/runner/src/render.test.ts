import { cardData, scripts } from "@fyendal/cards";
import { applyIntent, createGame, legalIntents as engineLegalIntents, projectStateFor, type GameState } from "@fyendal/engine";
import { describe, expect, it } from "vitest";
import { randomAgent, type Intent, type Seat, type View } from "./agent.js";
import { runGame, type Replay } from "./game.js";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE } from "./list/fixtureLists.js";
import { pickDecklist } from "./list/pickDecklist.js";
import { measureDecision } from "./measure.js";
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

  it("renders each Intent in plain language, naming its cards with their colours", () => {
    const { view, seat, legal } = decisionAt(replay, MID_GAME_STEP);

    const entries = numberedEntries(renderDecision(view, seat, legal).text);

    expect(entries[0]).toBe("1. play Buckling Blow (blue), pitching Test of Might (red) and Clash of Might (blue)");
    expect(entries).toContain("11. play Thunk (blue) from arsenal, pitching Buckling Blow (blue) and Clash of Might (blue)");
    expect(entries).toContain("14. attack with Titan's Fist, pitching Buckling Blow (blue)");
    expect(entries.at(-1)).toBe("18. pass (end your turn)");
  });

  it("shows every log line of the current turn and the previous turn, without printing tags", () => {
    const { view, seat, legal } = decisionAt(replay, MID_GAME_STEP);

    const log = section(renderDecision(view, seat, legal).text, "Log, previous turn and this turn:");

    expect(log[0]).toBe("— Turn 5: Ira, Crimson Haze's turn —");
    expect(log).toContain("Ira, Crimson Haze pitches Feign Vengeance");
    expect(log.at(-1)).toBe("— Turn 6: Bravo, Flattering Showman's turn —");
    expect(log).toHaveLength(10);
    expect(log.join("\n")).not.toMatch(/Turn 4|⟦/);
  });

  it("lists each visible opponent card once with its cost, pitch, attack, defense and text, and none of the Seat's own", () => {
    const { view, seat, legal } = decisionAt(replay, MID_GAME_STEP);

    const reference = section(renderDecision(view, seat, legal).text, "Opponent's cards you can see:");

    expect(reference).toContain(
      "Sirens of Safe Harbor (red): generic action - attack. Cost 2, pitch 1, attack 6, defense 2. When this is put into your graveyard from anywhere, gain 1{h}.",
    );
    expect(reference).toContain("Edge of Autumn: ninja weapon - sword, 2h. Attack 1. Once per Turn Action - {r}: Attack. Go again");
    expect(reference).toContain("Ira, Crimson Haze: ninja hero. Life 20, intellect 4. Your second attack each turn gets +1{p}.");
    // Two printings of Sirens sit in the graveyard: one entry each. Feign Vengeance was pitched last turn and is back in the deck: no entry.
    expect(reference.filter((line) => line.startsWith("Sirens of Safe Harbor"))).toHaveLength(2);
    expect(reference).toHaveLength(10);
    expect(reference.join("\n")).not.toMatch(/Buckling Blow|Titan's Fist|Bravo|Feign Vengeance/);
  });

  it("pins one rendered decision", () => {
    const { view, seat, legal } = decisionAt(replay, MID_GAME_STEP);

    expect(renderDecision(view, seat, legal).text).toMatchSnapshot();
  });

  it("renders no Intent of the Game as JSON or raw field names", () => {
    let entriesChecked = 0;
    for (const { view, seat, legal } of decisions(replay)) {
      for (const entry of numberedEntries(renderDecision(view, seat, legal).text)) {
        expect(entry).not.toMatch(/[{}"]|Ids?\b|\bkind\b|optionId|instance/);
        entriesChecked++;
      }
    }
    expect(entriesChecked).toBeGreaterThan(500);
  });
});

describe("measureDecision", () => {
  it("counts the Intents offered, the numbered entries and the tokens of the text", () => {
    const { view, seat, legal } = decisionAt(replay, MID_GAME_STEP);

    const measurement = measureDecision(view, seat, legal);

    expect(measurement).toMatchObject({ seat: 1, intents: 27, reorderFreeIntents: 18 });
    expect(measurement.tokens).toBe(Math.ceil(renderDecision(view, seat, legal).text.length / 4));
  });
});

/** The lines of a rendering's section, from its heading line to the next heading or the end. */
function section(text: string, heading: string): string[] {
  const lines = text.split("\n");
  const start = lines.indexOf(heading);
  expect(start).toBeGreaterThanOrEqual(0);
  const rest = lines.slice(start + 1);
  const end = rest.findIndex((line) => /^[A-Z][^.]*:$/.test(line) && !line.startsWith("—"));
  return rest.slice(0, end === -1 ? undefined : end);
}

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

interface Decision {
  view: View;
  seat: Seat;
  legal: Intent[];
}

/** What the acting Seat was shown at `step` of a replay, and what it could do. */
function decisionAt(replay: Replay, step: number): Decision {
  return decisionOf(stateAt({ ...replay, intents: replay.intents.slice(0, step) }));
}

/** Every decision of a replay, in order. */
function* decisions(replay: Replay): Generator<Decision> {
  let state = newGame(replay);
  for (const intent of replay.intents) {
    const decision = decisionOf(state);
    yield decision;
    const applied = applyIntent(state, decision.seat, intent);
    if (!applied.ok) throw new Error(`engine rejected ${intent.kind}: ${applied.error}`);
    state = applied.state;
  }
}

function decisionOf(state: GameState): Decision {
  const seat: Seat = (state.pendingDecision?.player ?? state.priorityPlayer) === 1 ? 1 : 0;
  const legal = engineLegalIntents(state, seat).filter((intent) => intent.kind !== "concede" && !intent.kind.endsWith("-draw"));
  return { view: projectStateFor(state, seat), seat, legal };
}

function stateAt(replay: Replay): GameState {
  let state = newGame(replay);
  replay.intents.forEach((intent, step) => {
    const applied = applyIntent(state, decisionOf(state).seat, intent);
    if (!applied.ok) throw new Error(`step ${step}: engine rejected ${intent.kind}: ${applied.error}`);
    state = applied.state;
  });
  return state;
}

function newGame(replay: Replay): GameState {
  return createGame({ decklists: [replay.decklists[0], replay.decklists[1]], cards: cardData, scripts, seed: replay.seed, startPlayer: replay.startingSeat }); // glossary: upstream
}
