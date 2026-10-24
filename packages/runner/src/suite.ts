// The Phase 1 suite: Ira vs Bravo for 50 seeds in both seat orders, 100 Games
// between random Agents, each replayed to check it reproduces exactly. Games
// are played one after another, as a script with top-level await.
import { isDeepStrictEqual } from "node:util";
import { randomAgent } from "./agent.js";
import { isFailure, replayGame, runGame, type GameResult } from "./game.js";
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE } from "./list/fixtureLists.js";
import type { List } from "./list/loadList.js";
import { pickDecklist } from "./list/pickDecklist.js";

const SEEDS = Array.from({ length: 50 }, (_, index) => index + 1);

const ira = fixtureList(IRA_LIST_FILE);
const bravo = fixtureList(BRAVO_LIST_FILE);

/** Which List sits in Seat 0. Seat 0 starts every Game, so it also goes first. */
const SEAT_ORDERS: readonly (readonly [List, List])[] = [
  [ira, bravo],
  [bravo, ira],
];

/** One Game of the suite and whether its replay reproduces it. */
interface SuiteGame {
  seed: number;
  /** The List in each Seat. */
  lists: readonly [List, List];
  result: GameResult;
  reproduces: boolean;
  replayError?: string;
}

const heroOf = (list: List) => list.hero.name.split(",")[0];
const seatOrderOf = ({ lists }: SuiteGame) => `${heroOf(lists[0])} (Seat 0) vs ${heroOf(lists[1])} (Seat 1)`;

const played: SuiteGame[] = [];
let playMs = 0;
for (const seed of SEEDS) {
  for (const lists of SEAT_ORDERS) {
    const decklists = [pickDecklist(lists[0], seed), pickDecklist(lists[1], seed)] as const;
    const started = performance.now();
    const result = await runGame({ decklists, seed, startingSeat: 0, agents: [randomAgent, randomAgent] });
    playMs += performance.now() - started;
    try {
      const reproduces = isDeepStrictEqual(replayGame(result.replay), result.finalProjection);
      played.push({ seed, lists, result, reproduces });
    } catch (error) {
      played.push({ seed, lists, result, reproduces: false, replayError: String(error) });
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
const failing = played.flatMap((game) => (isFailure(game.result) ? [{ ...game, failure: game.result }] : []));
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
for (const game of diverging)
  console.log(`  seed ${game.seed}, ${seatOrderOf(game)}: ${game.replayError ?? "final replay projection differs"}`);
console.log();
console.log(`Failing Games: ${failing.length}`);
for (const { failure, ...game } of failing)
  console.log(`  seed ${game.seed}, ${seatOrderOf(game)}, step ${failure.step}: ${failure.outcome}: ${failure.detail}`);
console.log();
const passed = failing.length === 0 && diverging.length === 0;
console.log(`Exit criteria: ${passed ? "PASS" : "FAIL"}`);
console.log(`  all Games end in a win or draw: ${failing.length === 0 ? "pass" : "fail"}`);
console.log(`  every replay reproduces:        ${diverging.length === 0 ? "pass" : "fail"}`);
console.log(`  games per second reported:      pass`);
process.exitCode = passed ? 0 : 1;
