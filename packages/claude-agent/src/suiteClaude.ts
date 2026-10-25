// pnpm suite:claude: the Phase 2 suite, ten Games between two Claude Agents on
// the Ira and Bravo Lists through the real Claude Code call, played as one Run
// under results/ that ends in its report. A rate limit pauses the Run (exit
// code 3) and `--resume <runDir>` carries it on. A script with top-level
// await; its flags are parsed in suiteClaudeArgs.ts.
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { claudeCodeCall, describeConfig } from "./claudeCode.js";
import { progressLine } from "./playGame.js";
import { exitCriteria } from "./report.js";
import { readManifest, resumeSuite, runSuite, type Manifest, type ManifestGame, type RunConfig, type RunSuiteOptions } from "./run.js";
import { parseSuiteClaudeArgs, SUITE_USAGE, suiteRunDirName, type SuiteClaudeArgs } from "./suiteClaudeArgs.js";

/** The exit code of a Run that paused on a rate limit. */
export const PAUSED_EXIT_CODE = 3;

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

// pnpm runs a package script in the package directory and keeps the caller's in INIT_CWD.
const callerDir = process.env.INIT_CWD ?? process.cwd();
const printing: Pick<RunSuiteOptions, "call" | "onDecision" | "onGame"> = {
  call: claudeCodeCall(),
  onDecision: (record, progress, { game }) => console.log(progressLine(game.id, record, progress)),
  onGame: (game) => console.log(gameLine(game)),
};

let result: { manifest: Manifest; reportPath?: string };
if (args.resume !== undefined) {
  const runDir = resolve(callerDir, args.resume);
  const paused = readManifest(runDir);
  const left = paused.games.filter(({ status }) => status === "pending" || status === "playing");
  console.log(`Resuming the Run in ${runDir}: ${describeRun(paused.config)}`);
  console.log(`${left.length} of ${paused.games.length} Games left${paused.pausedAt ? `; paused ${paused.pausedAt}` : ""}${paused.pauseDetail ? ` on: ${paused.pauseDetail}` : ""}.`);
  result = await resumeSuite({ runDir, ...printing });
} else {
  const { config } = args;
  const runDir = join(resolve(callerDir, args.results), suiteRunDirName(new Date()));
  mkdirSync(runDir, { recursive: true });
  console.log(`Run: ${describeRun(config)}`);
  console.log(`Run directory: ${runDir}`);
  result = await runSuite({ config, runDir, ...printing });
}

const { manifest, reportPath } = result;
console.log();
if (manifest.status === "paused") {
  console.log(`The Run paused on a rate limit at ${manifest.pausedAt}: ${manifest.pauseDetail}`);
  console.log(`Every Game in flight stopped after its current decision and keeps its Game file. When the usage window resets, resume it with:`);
  console.log(`  ${manifest.resumeHint}`);
  process.exitCode = PAUSED_EXIT_CODE;
} else {
  const criteria = exitCriteria(manifest);
  for (const { criterion, verdict } of criteria.rows) console.log(`${criterion}: ${verdict}`);
  console.log(`Exit criteria: ${criteria.passed ? "PASS" : "FAIL"}`);
  console.log(`Report: ${reportPath}`);
  process.exitCode = criteria.passed ? 0 : 1;
}

/** The one line printed per Game status change. */
function gameLine(game: ManifestGame): string {
  const { outcome } = game;
  const what = !outcome
    ? game.status === "playing" && game.steps !== undefined
      ? ` (stopped after ${game.steps} decisions)`
      : ""
    : outcome.outcome === "win"
      ? `: Seat ${outcome.winner} wins in ${game.steps} decisions`
      : outcome.outcome === "draw"
        ? `: draw in ${game.steps} decisions`
        : `: ${outcome.outcome}${outcome.outcome === "error" && outcome.cause ? ` (${outcome.cause})` : ""} at step ${outcome.step}: ${outcome.detail}`;
  return `game ${game.id} ${game.status}${what}`;
}

function describeRun(config: RunConfig): string {
  return (
    `${config.seeds.length * 2} Games, seeds ${config.seeds.join(", ")}, both seat orders; ` +
    `Seat 0 ${describeConfig(config.configs[0])}, Seat 1 ${describeConfig(config.configs[1])}; ${config.concurrency} at a time, ${config.maxSteps} decisions per Game at most.`
  );
}
