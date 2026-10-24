// pnpm game:claude: one Game between two Claude Agents on the Ira and Bravo
// Lists, through the real Claude Code call, written to a one-Game Run
// directory under results/. A script with top-level await; its flags are
// parsed in gameClaudeArgs.ts.
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, isFailure, type List } from "@tcg-htc/runner";
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { claudeCodeCall } from "./claudeCode.js";
import { parseGameClaudeArgs, runDirName, USAGE, type GameClaudeArgs, type Hero } from "./gameClaudeArgs.js";
import { gameId, heroSlug } from "./gameFile.js";
import { playGame, progressLine } from "./playGame.js";

let args: GameClaudeArgs;
try {
  args = parseGameClaudeArgs(process.argv.slice(2));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error(`usage: ${USAGE}`);
  process.exit(2);
}

if (process.env.ANTHROPIC_API_KEY) {
  console.warn("ANTHROPIC_API_KEY is set. The Claude Code call strips it so the Game runs on the subscription (ADR-0002); unset it to be sure.");
}

const listsByHero: Record<Hero, List> = { ira: fixtureList(IRA_LIST_FILE), bravo: fixtureList(BRAVO_LIST_FILE) };
const second: Hero = args.first === "ira" ? "bravo" : "ira";
const lists = [listsByHero[args.first], listsByHero[second]] as const;
// pnpm runs a package script in the package directory and keeps the caller's in INIT_CWD.
const runDir = join(resolve(process.env.INIT_CWD ?? process.cwd(), args.results), runDirName(new Date(), args.seed, args.first));
mkdirSync(runDir, { recursive: true });
const id = gameId(args.seed, lists[0].hero.name);

console.log(`Game ${id}: ${lists[0].hero.name} (Seat 0, ${describe(args.configs[0])}) vs ${lists[1].hero.name} (Seat 1, ${describe(args.configs[1])})`);
console.log(`Run directory: ${runDir}`);

const { result, path, file } = await playGame({
  seed: args.seed,
  lists,
  configs: args.configs,
  call: claudeCodeCall(),
  runDir,
  onDecision: (record, progress) => console.log(progressLine(id, record, progress)),
});

const { totals } = file.measurements;
console.log();
if (result.outcome === "win") {
  console.log(`Seat ${result.winner} (${heroSlug(lists[result.winner].hero.name)}) wins in ${result.turns} turns, ${result.steps} decisions.`);
} else if (result.outcome === "draw") {
  console.log(`Draw in ${result.turns} turns, ${result.steps} decisions.`);
} else if (result.outcome === "paused") {
  // A single Game has no resume; its file holds every Intent applied.
  console.log(`paused on a rate limit at step ${result.step}: ${result.detail}`);
} else {
  console.log(`${result.outcome} at step ${result.step}${"cause" in result && result.cause ? ` (${result.cause})` : ""}: ${result.detail}`);
}
console.log(
  `Tokens: ${totals.inputTokens} in, ${totals.cachedTokens} cached, ${totals.outputTokens} out; cost estimate $${totals.costUsd.toFixed(2)}; ` +
    `latency ${(totals.latencyMs / 1000).toFixed(0)} s over ${totals.decisions} decisions; ${totals.retries} retries, ${totals.invalidFirstAnswers} invalid first answers.`,
);
console.log(`Game file: ${path}`);
process.exitCode = isFailure(result) ? 1 : result.outcome === "paused" ? 3 : 0;

function describe({ model, effort }: GameClaudeArgs["configs"][number]): string {
  return `${model} at ${effort}`;
}
