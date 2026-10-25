// The Phase 2 report, rendered from a Run's manifest and Game files in the
// shape of docs/phase1-report.md. The owner commits it as docs/phase2-report.md.
import { isFailure, type DecisionRecord, type Seat } from "@tcg-htc/runner";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describeConfig, type ClaudeConfig } from "./claudeCode.js";
import type { Hero } from "./gameClaudeArgs.js";
import type { GameFile } from "./gameFile.js";
import { HERO_LIST_FILES, heroList, heroTitle } from "./heroLists.js";
import type { Manifest, ManifestGame, RunConfig } from "./run.js";
import { formatSeeds } from "./suiteClaudeArgs.js";

export interface ReportOptions {
  upstreamCommit: string;
  /** The Run directory, as the report names it. */
  runDir: string;
}

export const REPORT_TITLE = "Phase 2 report: Claude Agents play Ira vs Bravo through Claude Code";

/** The verdict on each exit criterion, and whether the Run passed. */
export interface ExitCriteria {
  passed: boolean;
  rows: { criterion: string; verdict: string }[];
}

/** The exit criteria over the manifest: every Game a win or a draw, and no
 * Game ended by an Agent's failure Decision. */
export function exitCriteria(manifest: Manifest): ExitCriteria {
  const { games } = manifest;
  const failed = games.filter(({ outcome }) => outcome && isFailure(outcome));
  const stalls = failed.filter(({ outcome }) => outcome?.outcome === "stall").length;
  const faults = games.filter(({ outcome }) => outcome?.outcome === "error" && outcome.cause);
  const rows = [
    {
      criterion: `All ${games.length} Games end in a win or draw, with no stalls and no errors`,
      verdict: failed.length === 0 ? "Pass" : `Fail: ${failed.length} failed (${stalls} stall, ${failed.length - stalls} error)`,
    },
    {
      criterion: "No Game ended on an Agent's fault (an error outcome with a Decision failure cause)",
      verdict:
        faults.length === 0
          ? "Pass"
          : `Fail: ${faults.length} Game${faults.length === 1 ? "" : "s"} (${faults.map((game) => `\`${game.id}\`, ${game.outcome?.outcome === "error" ? game.outcome.cause : ""}`).join("; ")})`,
    },
  ];
  return { passed: rows.every(({ verdict }) => verdict === "Pass"), rows };
}

/** The single-Game command that plays a Run's Game again. */
export function reproduceCommand(game: ManifestGame, config: RunConfig): string {
  return `pnpm game:claude --seed ${game.seed} --first ${game.first}${configFlags(config.configs)}`;
}

function configFlags(configs: readonly [ClaudeConfig, ClaudeConfig]): string {
  return configs.map(({ model, effort }, seat) => ` --model${seat} ${model} --effort${seat} ${effort}`).join("");
}

export function renderReport(manifest: Manifest, gameFiles: Record<string, GameFile>, options: ReportOptions): string {
  const { games, config } = manifest;
  const criteria = exitCriteria(manifest);
  const settled = games.filter(({ outcome }) => outcome && !isFailure(outcome)).length;
  const faults = games.filter(({ outcome }) => outcome?.outcome === "error" && outcome.cause).length;
  const verdict = criteria.passed
    ? `All ${games.length} Games ended in a win or draw, and no Game ended on an Agent's fault.`
    : `${settled} of ${games.length} Games ended in a win or draw; ${games.length - settled} failed, ${faults} on an Agent's fault.`;
  const failing = games.filter(({ outcome }) => outcome && isFailure(outcome));

  return [
    `# ${REPORT_TITLE}`,
    `Spec #167, ticket #176. Verdict: **${criteria.passed ? "pass" : "fail"}**. ${verdict}`,
    "## Setup",
    setup(manifest, options),
    "## Results",
    table(["Outcome", "Games"], outcomeRows(manifest)),
    table(
      ["Game", "Seed", "Seat order", "Outcome", "Winner", "Decisions", "Turns", "Models (Seat 0 / Seat 1)"],
      games.map((game) => gameRow(game, config, gameFiles[game.id])),
    ),
    "## Measurements",
    table(["Measurement", "Average", "Maximum"], measurementRows(games.map(({ id }) => gameFiles[id]).filter((file): file is GameFile => !!file))),
    table(["Total", "Value"], totalRows(Object.values(gameFiles))),
    "### Models reported",
    table(
      ["Seat", "Config", "Models Claude Code reported"],
      ([0, 1] as const).map((seat) => [String(seat), describeConfig(config.configs[seat]), modelsCell(modelsReported(Object.values(gameFiles), seat))]),
    ),
    "## Exit criteria",
    table(
      ["Criterion", "Verdict"],
      criteria.rows.map(({ criterion, verdict }) => [criterion, verdict]),
    ),
    "## Failures and issues filed",
    failing.length === 0 ? "None." : failing.map((game) => failureEntry(game, config)).join("\n"),
    "## Decisions",
    OWNER_PLACEHOLDER,
    "## Notes for the next phase",
    OWNER_PLACEHOLDER,
  ].join("\n\n") + "\n";
}

const OWNER_PLACEHOLDER = "_To be written by the owner (#178)._";

function setup(manifest: Manifest, { upstreamCommit, runDir }: ReportOptions): string {
  const { config, games, startedAt, updatedAt } = manifest;
  const [first, second] = config.lists;
  const listLine = config.lists.map((hero) => `\`packages/runner/lists/${HERO_LIST_FILES[hero]}\` (${heroList(hero).hero.name})`).join(" and ");
  return [
    `- **Engine:** fyendal.net at upstream commit \`${upstreamCommit}\`, vendored at \`vendor/fyendal.net\`.`,
    `- **Lists:** ${listLine}.`,
    `- **Agents:** Claude Agents through Claude Code in print mode (ADR-0002): ${config.configs.map((seatConfig, seat) => `Seat ${seat} ${describeConfig(seatConfig)}`).join(", ")}. Each Seat's config stays with the Seat whichever List sits there. Every decision is one fresh call.`,
    `- **Seeds:** ${seedsPhrase(config.seeds)}.`,
    `- **Seat orders:** each seed is played twice, once with ${heroTitle(first)} in Seat 0 and once with ${heroTitle(second)} in Seat 0. Seat 0 starts every Game, so each List goes first once per seed. That makes ${games.length} Games.`,
    `- **Decision cap:** ${config.maxSteps} decisions per Game; a Game over it ends as a stall.`,
    `- **Concurrency:** ${config.concurrency} Games at a time; decisions within a Game are sequential.`,
    `- **Run directory:** \`${runDir}\`, started ${startedAt}, last updated ${updatedAt}.`,
    `- **Command:** \`pnpm suite:claude${configFlags(config.configs)} --seeds ${formatSeeds(config.seeds)} --concurrency ${config.concurrency}\`.`,
  ].join("\n");
}

function seedsPhrase(seeds: readonly number[]): string {
  const flag = formatSeeds(seeds);
  return flag.includes("-") ? flag.replace("-", " to ") : flag.replace(/,/g, ", ");
}

function outcomeRows({ games, config }: Manifest): string[][] {
  const count = (kind: string) => games.filter(({ outcome }) => outcome?.outcome === kind).length;
  const winsFor = (hero: Hero) => games.filter((game) => game.outcome?.outcome === "win" && heroInSeat(game, config, game.outcome.winner) === hero).length;
  return [
    ["Win", `${count("win")} (${config.lists.map((hero) => `${heroTitle(hero)} ${winsFor(hero)}`).join(", ")})`],
    ["Draw", String(count("draw"))],
    ["Stall", String(count("stall"))],
    ["Error", String(count("error"))],
  ];
}

/** The hero in a Seat of a Game: Seat 0 holds `first`, Seat 1 the other List. */
function heroInSeat(game: ManifestGame, config: RunConfig, seat: Seat): string {
  if (seat === 0) return game.first;
  return config.lists.find((hero) => hero !== game.first) ?? config.lists[1];
}

function seatOrder(game: ManifestGame, config: RunConfig): string {
  return `${heroTitle(heroInSeat(game, config, 0))} (Seat 0) vs ${heroTitle(heroInSeat(game, config, 1))} (Seat 1)`;
}

function gameRow(game: ManifestGame, config: RunConfig, file: GameFile | undefined): string[] {
  const { outcome } = game;
  const outcomeText = !outcome
    ? game.status
    : outcome.outcome === "win" || outcome.outcome === "draw"
      ? outcome.outcome
      : `${outcome.outcome}${outcome.outcome === "error" && outcome.cause ? ` (${outcome.cause})` : ""} at step ${outcome.step}`;
  const winner = outcome?.outcome === "win" ? `${heroTitle(heroInSeat(game, config, outcome.winner))} (Seat ${outcome.winner})` : "-";
  const decisions = file ? file.decisions.length : game.steps;
  return [
    `\`${game.id}\``,
    String(game.seed),
    seatOrder(game, config),
    outcomeText,
    winner,
    decisions === undefined ? "-" : String(decisions),
    file?.turns === undefined ? "-" : String(file.turns),
    file ? modelsPlayedBy(file) : "-",
  ];
}

/** The models Claude Code reported for each Seat of one Game, `Seat 0's / Seat 1's`. */
function modelsPlayedBy(file: GameFile): string {
  return ([0, 1] as const).map((seat) => modelsCell(modelsReported([file], seat))).join(" / ");
}

function modelsCell(models: string[]): string {
  return models.map((model) => `\`${model}\``).join(", ") || "-";
}

function measurementRows(files: GameFile[]): string[][] {
  const records = files.flatMap((file) => file.decisions);
  const perGame = (pick: (file: GameFile) => number) => files.map(pick);
  const perDecision = (pick: (record: DecisionRecord) => number) => records.map(pick);
  const measured = (record: DecisionRecord, field: "inputTokens" | "cachedTokens" | "outputTokens" | "latencyMs") => record.decision.measurements?.[field] ?? 0;
  const row = (name: string, values: number[], format: (value: number) => string = integer, averageFormat: (value: number) => string = decimal) => [
    name,
    averageFormat(mean(values)),
    format(values.length ? Math.max(...values) : 0),
  ];
  return [
    row("Decisions per Game", perGame((file) => file.decisions.length)),
    row("Turns per Game", perGame((file) => file.turns ?? 0)),
    row("Input tokens per Game", perGame((file) => file.measurements.totals.inputTokens)),
    row("Input tokens per decision", perDecision((record) => measured(record, "inputTokens"))),
    row("Cached tokens per Game", perGame((file) => file.measurements.totals.cachedTokens)),
    row("Cached tokens per decision", perDecision((record) => measured(record, "cachedTokens"))),
    row("Output tokens per Game", perGame((file) => file.measurements.totals.outputTokens)),
    row("Output tokens per decision", perDecision((record) => measured(record, "outputTokens"))),
    row("Latency per Game (s)", perGame((file) => file.measurements.totals.latencyMs / 1000), decimal),
    row("Latency per decision (s)", perDecision((record) => measured(record, "latencyMs") / 1000), decimal),
    row("Cost estimate per Game ($)", perGame((file) => file.measurements.totals.costUsd), money, money),
  ];
}

function totalRows(files: GameFile[]): string[][] {
  const sum = (pick: (file: GameFile) => number) => files.reduce((total, file) => total + pick(file), 0);
  return [
    ["Decisions", integer(sum((file) => file.measurements.totals.decisions))],
    ["Cost estimate ($)", money(sum((file) => file.measurements.totals.costUsd))],
    ["Retries", integer(sum((file) => file.measurements.totals.retries))],
    ["Invalid first answers", integer(sum((file) => file.measurements.totals.invalidFirstAnswers))],
    ["Plan notes cut", integer(sum((file) => file.measurements.totals.notesCut))],
  ];
}

/** The distinct models Claude Code reported for a Seat's decisions, sorted. */
export function modelsReported(files: GameFile[], seat: Seat): string[] {
  const models = new Set<string>();
  for (const file of files) {
    for (const { seat: recordSeat, decision } of file.decisions) {
      if (recordSeat === seat && decision.measurements?.model) models.add(decision.measurements.model);
    }
  }
  return [...models].sort();
}

function failureEntry(game: ManifestGame, config: RunConfig): string {
  const { outcome } = game;
  if (!outcome || !isFailure(outcome)) return "";
  const cause = outcome.outcome === "error" && outcome.cause ? ` (${outcome.cause})` : "";
  const detail = outcome.detail.replace(/\.?$/, ".");
  return `- \`${game.id}\`: seed ${game.seed}, ${seatOrder(game, config)}, step ${outcome.step}, **${outcome.outcome}**${cause}: ${detail}\n  Reproduce: \`${reproduceCommand(game, config)}\``;
}

function table(header: string[], rows: string[][]): string {
  const line = (cells: string[]) => `| ${cells.join(" | ")} |`;
  return [line(header), line(header.map(() => "---")), ...rows.map(line)].join("\n");
}

const integer = (value: number) => value.toLocaleString("en-US", { maximumFractionDigits: 0 });
const decimal = (value: number) => value.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const money = (value: number) => value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const mean = (values: number[]) => (values.length ? values.reduce((total, value) => total + value, 0) / values.length : 0);

const REPO_ROOT = fileURLToPath(new URL("../../../", import.meta.url));

/** The upstream commit vendored at `vendor/fyendal.net`: what the submodule
 * is at, or failing that the commit AGENTS.md says it is pinned to. */
export function upstreamCommit(repoRoot = REPO_ROOT): string {
  try {
    return execFileSync("git", ["-C", `${repoRoot}vendor/fyendal.net`, "rev-parse", "HEAD"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    const pinned = readFileSync(`${repoRoot}AGENTS.md`, "utf8").match(/pinned to upstream commit `([0-9a-f]{40})`/);
    return pinned?.[1] ?? "unknown";
  }
}
