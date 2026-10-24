import { expect, it } from "vitest";
import { randomAgent } from "./agent.js";
import { runGame } from "./game.js";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE } from "./list/fixtureLists.js";
import { pickDecklist } from "./list/pickDecklist.js";

const SEED = 120;

it(
  "plays one Game of Ira vs Bravo, from Decklists picked from the fixture Lists, to an outcome",
  async () => {
    const decklists = [
      pickDecklist(fixtureList(IRA_LIST_FILE), SEED),
      pickDecklist(fixtureList(BRAVO_LIST_FILE), SEED),
    ] as const;

    const result = await runGame({ decklists, seed: SEED, startingSeat: 0, agents: [randomAgent, randomAgent] });

    const { replay: _replay, finalProjection: _final, ...outcome } = result;
    console.info(`Ira vs Bravo, seed ${SEED}:`, JSON.stringify(outcome));
    expect(["win", "draw", "stall", "error"]).toContain(result.outcome);
    expect(result.replay.decklists).toEqual(decklists);
  },
  30_000,
);
