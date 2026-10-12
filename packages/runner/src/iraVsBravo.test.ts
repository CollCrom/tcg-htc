import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { randomAgent } from "./agent.js";
import { runGame } from "./game.js";
import { loadList } from "./list/loadList.js";
import { pickDecklist } from "./list/pickDecklist.js";

const list = (file: string) => loadList(readFileSync(new URL(`../lists/${file}`, import.meta.url), "utf8"));
const SEED = 120;

it(
  "plays one Game of Ira vs Bravo, from Decklists picked from the fixture Lists, to an outcome",
  () => {
    const decklists = [
      pickDecklist(list("ira-crimson-haze.txt"), SEED),
      pickDecklist(list("bravo-flattering-showman.txt"), SEED),
    ] as const;

    const result = runGame({ decklists, seed: SEED, startPlayer: 0, agents: [randomAgent, randomAgent] });

    const { replay: _replay, finalProjection: _final, ...outcome } = result;
    console.info(`Ira vs Bravo, seed ${SEED}:`, JSON.stringify(outcome));
    expect(["win", "draw", "stall", "error"]).toContain(result.outcome);
    expect(result.replay.decklists).toEqual(decklists);
  },
  30_000,
);
