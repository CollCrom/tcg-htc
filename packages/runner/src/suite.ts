// The Phase 1 suite: Ira vs Bravo for 50 seeds in both seat orders, 100 Games
// between random Agents, each replayed to check it reproduces exactly.
import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { randomAgent } from "./agent.js";
import { replayGame, runGame, type GameResult } from "./game.js";
import { loadList, type List } from "./list/loadList.js";
import { pickDecklist } from "./list/pickDecklist.js";

const SEEDS = Array.from({ length: 50 }, (_, index) => index + 1);

const list = (file: string) => loadList(readFileSync(new URL(`../lists/${file}`, import.meta.url), "utf8"));
const ira = list("ira-crimson-haze.txt");
const bravo = list("bravo-flattering-showman.txt");

/** Which List sits in Seat 0. Seat 0 starts every Game, so it also goes first. */
const SEAT_ORDERS: readonly (readonly [List, List])[] = [
  [ira, bravo],
  [bravo, ira],
];

interface Played {
  seed: number;
  seatOrder: string;
  /** The List in each Seat. */
  lists: readonly [List, List];
  result: GameResult;
  reproduces: boolean;
  replayError?: string;
}

const heroOf = (list: List) => list.hero.name.split(",")[0];

const played: Played[] = [];
let playMs = 0;
for (const seed of SEEDS) {
  for (const lists of SEAT_ORDERS) {
    const decklists = [pickDecklist(lists[0], seed), pickDecklist(lists[1], seed)] as const;
    const started = performance.now();
    const result = runGame({ decklists, seed, startPlayer: 0, agents: [randomAgent, randomAgent] });
    playMs += performance.now() - started;
    const seatOrder = `${heroOf(lists[0])} (Seat 0) vs ${heroOf(lists[1])} (Seat 1)`;
    try {
      const reproduces = isDeepStrictEqual(replayGame(result.replay), result.finalProjection);
      played.push({ seed, seatOrder, lists, result, reproduces });
    } catch (error) {
      played.push({ seed, seatOrder, lists, result, reproduces: false, replayError: String(error) });
    }
  }
}

const stats = (values: number[]) => {
  const total = values.reduce((sum, value) => sum + value, 0);
  return `average ${(total / values.length).toFixed(1)}, maximum ${Math.max(...values)}`;
};
const decisions = played.flatMap(({ result }) => result.measurements.decisions);
const count = (outcome: GameResult["outcome"]) => played.filter(({ result }) => result.outcome === outcome).length;
const winsFor = (list: List) =>
  played.filter(({ result, lists }) => result.outcome === "win" && lists[result.winner] === list).length;
const failing = played.filter(({ result }) => result.outcome === "stall" || result.outcome === "error");
const diverging = played.filter(({ reproduces }) => !reproduces);

console.log(`Phase 1 suite: ${played.length} Games, seeds ${SEEDS[0]}-${SEEDS.at(-1)}, both seat orders`);
console.log();
console.log("Outcomes");
console.log(`  win:   ${count("win")} (Ira ${winsFor(ira)}, Bravo ${winsFor(bravo)})`);
console.log(`  draw:  ${count("draw")}`);
console.log(`  stall: ${count("stall")}`);
console.log(`  error: ${count("error")}`);
console.log();
console.log(`Games per second: ${(played.length / (playMs / 1000)).toFixed(2)} (${(playMs / 1000).toFixed(1)} s playing, replays excluded)`);
console.log();
console.log("Measurements");
console.log(`  decisions per Game:                  ${stats(played.map(({ result }) => result.measurements.decisions.length))}`);
console.log(`  turns per Game:                      ${stats(played.map(({ result }) => result.turns))}`);
console.log(`  Intents per decision (raw):          ${stats(decisions.map(({ intents }) => intents))}`);
console.log(`  Intents per decision (reorder-free): ${stats(decisions.map(({ reorderFreeIntents }) => reorderFreeIntents))}`);
console.log(`  tokens per decision:                 ${stats(decisions.map(({ tokens }) => tokens))}`);
console.log();
console.log(`Replays: ${played.length - diverging.length} of ${played.length} reproduce exactly`);
for (const { seed, seatOrder, replayError } of diverging)
  console.log(`  seed ${seed}, ${seatOrder}: ${replayError ?? "final replay projection differs"}`);
console.log();
console.log(`Failing Games: ${failing.length}`);
for (const { seed, seatOrder, result } of failing)
  if (result.outcome === "stall" || result.outcome === "error")
    console.log(`  seed ${seed}, ${seatOrder}, step ${result.step}: ${result.outcome}: ${result.detail}`);
console.log();
const passed = failing.length === 0 && diverging.length === 0;
console.log(`Exit criteria: ${passed ? "PASS" : "FAIL"}`);
console.log(`  all Games end in a win or draw: ${failing.length === 0 ? "pass" : "fail"}`);
console.log(`  every replay reproduces:        ${diverging.length === 0 ? "pass" : "fail"}`);
console.log(`  games per second reported:      pass`);
process.exitCode = passed ? 0 : 1;
