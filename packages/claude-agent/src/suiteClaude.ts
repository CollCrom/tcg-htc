// pnpm suite:claude: the Phase 2 suite, ten Games between two Claude Agents on
// the Ira and Bravo Lists through the real Claude Code call, played as one Run
// under results/ that ends in its report. A script with top-level await; its
// flags are parsed in suiteClaudeArgs.ts.
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { claudeCodeCall } from "./claudeCode.js";
import { progressLine } from "./playGame.js";
import { exitCriteria } from "./report.js";
import { runSuite, type ManifestGame } from "./run.js";
import { parseSuiteClaudeArgs, SUITE_USAGE, suiteRunDirName, type SuiteClaudeArgs } from "./suiteClaudeArgs.js";

let args: SuiteClaudeArgs;
try {
  args = parseSuiteClaudeArgs(process.argv.slice(2));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error(`usage: ${SUITE_USAGE}`);
  process.exit(2);
}

if (process.env.ANTHROPIC_API_KEY) {
  console.warn("ANTHROPIC_API_KEY is set. The Claude Code call strips it so the Run plays on the subscription (ADR-0002); unset it to be sure.");
}

const { config } = args;
// pnpm runs a package script in the package directory and keeps the caller's in INIT_CWD.
const runDir = join(resolve(process.env.INIT_CWD ?? process.cwd(), args.results), suiteRunDirName(new Date()));
mkdirSync(runDir, { recursive: true });

console.log(
  `Run: ${config.seeds.length * 2} Games, seeds ${config.seeds.join(", ")}, both seat orders; ` +
    `Seat 0 ${describe(config.configs[0])}, Seat 1 ${describe(config.configs[1])}; ${config.concurrency} at a time, ${config.maxSteps} decisions per Game at most.`,
);
console.log(`Run directory: ${runDir}`);

const { manifest, reportPath } = await runSuite({
  config,
  runDir,
  call: claudeCodeCall(),
  onDecision: (record, progress, { game }) => console.log(progressLine(game.id, record, progress)),
  onGame: (game) => console.log(gameLine(game)),
});

const criteria = exitCriteria(manifest);
console.log();
for (const { criterion, verdict } of criteria.rows) console.log(`${criterion}: ${verdict}`);
console.log(`Exit criteria: ${criteria.passed ? "PASS" : "FAIL"}`);
console.log(`Report: ${reportPath}`);
process.exitCode = criteria.passed ? 0 : 1;

/** The one line printed per Game status change. */
function gameLine(game: ManifestGame): string {
  const { outcome } = game;
  const what = !outcome
    ? ""
    : outcome.outcome === "win"
      ? `: Seat ${outcome.winner} wins in ${game.steps} decisions`
      : outcome.outcome === "draw"
        ? `: draw in ${game.steps} decisions`
        : `: ${outcome.outcome}${outcome.outcome === "error" && outcome.cause ? ` (${outcome.cause})` : ""} at step ${outcome.step}: ${outcome.detail}`;
  return `game ${game.id} ${game.status}${what}`;
}

function describe({ model, effort }: SuiteClaudeArgs["config"]["configs"][number]): string {
  return `${model} at ${effort}`;
}
