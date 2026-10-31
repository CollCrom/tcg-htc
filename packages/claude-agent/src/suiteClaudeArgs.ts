// The Claude suite script's flags, parsed apart from the script so they can be
// tested without playing a Run.
import { parseArgs } from "node:util";
import { CONFIG_OPTIONS, configsFrom } from "./gameClaudeArgs.js";
import { HEROES } from "./heroLists.js";
import { CLAUDE_MAX_DECISIONS } from "./playGame.js";
import { DEFAULT_CONCURRENCY, DEFAULT_SEEDS, type RunConfig } from "./run.js";

/** A new Run from its flags, or a paused Run to resume. */
export type SuiteClaudeArgs = SuiteRunArgs | SuiteResumeArgs;

export interface SuiteRunArgs {
  config: RunConfig;
  /** The results directory, as given. */
  results: string;
  resume?: undefined;
}

export interface SuiteResumeArgs {
  /** The paused Run's directory, as given; its config comes from its manifest. */
  resume: string;
}

export const SUITE_USAGE =
  "pnpm suite:claude [--model0 <alias>] [--effort0 <level>] [--model1 <alias>] [--effort1 <level>] [--concurrency 2] [--seeds 1-5] [--results <dir>]\n" +
  "       pnpm suite:claude --resume <runDir>   (no other flag: the Run's config is in its manifest)";

/** Parses the flags (`process.argv.slice(2)`). Throws a message naming the
 * flag at fault. */
export function parseSuiteClaudeArgs(args: readonly string[]): SuiteClaudeArgs {
  const { values, positionals } = parseArgs({
    args: [...args],
    options: {
      ...CONFIG_OPTIONS,
      concurrency: { type: "string", default: String(DEFAULT_CONCURRENCY) },
      seeds: { type: "string", default: formatSeeds(DEFAULT_SEEDS) },
      results: { type: "string", default: "results" },
      resume: { type: "string" },
    },
    allowPositionals: true,
    strict: true,
  });
  if (positionals.length > 0) throw new Error(`unexpected argument ${positionals.join(" ")}\nusage: ${SUITE_USAGE}`);
  if (values.resume !== undefined) {
    const others = args.filter((arg) => arg.startsWith("--") && !arg.startsWith("--resume"));
    if (others.length > 0) throw new Error(`--resume takes no other flag; the Run's config is in its manifest (got ${others.join(" ")})`);
    if (!values.resume) throw new Error("--resume needs the paused Run's directory");
    return { resume: values.resume };
  }
  const concurrency = Number(values.concurrency);
  if (!/^\d+$/.test(values.concurrency) || concurrency < 1) throw new Error(`--concurrency must be a whole number of at least 1, not ${values.concurrency}`);
  return {
    config: {
      seeds: parseSeeds(values.seeds),
      lists: [HEROES[0], HEROES[1]],
      configs: configsFrom(values),
      concurrency,
      maxSteps: CLAUDE_MAX_DECISIONS,
    },
    results: values.results,
  };
}

/** Seeds from the `--seeds` flag: ranges (`1-5`) and single seeds, comma
 * separated, in order and without repeats. */
export function parseSeeds(text: string): number[] {
  const seeds: number[] = [];
  for (const part of text.split(",")) {
    const range = part.match(/^(\d+)(?:-(\d+))?$/);
    if (!range) throw new Error(`--seeds must be seeds or ranges like 1-5 or 1,3,8, not ${JSON.stringify(text)}`);
    const first = Number(range[1]);
    const last = range[2] === undefined ? first : Number(range[2]);
    if (last < first) throw new Error(`--seeds has a range that runs backwards: ${part}`);
    for (let seed = first; seed <= last; seed++) {
      if (seeds.includes(seed)) throw new Error(`--seeds names seed ${seed} twice`);
      seeds.push(seed);
    }
  }
  return seeds;
}

/** Seeds as the `--seeds` flag writes them: a range when they are consecutive
 * (`1-5`), otherwise a comma list (`1,3,8`). */
export function formatSeeds(seeds: readonly number[]): string {
  const first = seeds[0];
  const last = seeds.at(-1);
  if (first === undefined || last === undefined) return "";
  const consecutive = seeds.every((seed, index) => seed === first + index);
  return consecutive && seeds.length > 1 ? `${first}-${last}` : seeds.join(",");
}

/** A Run's directory name: when it started (UTC, to the second, no colons so
 * Windows can read it) and `-suite`. */
export function suiteRunDirName(started: Date): string {
  return `${started.toISOString().slice(0, 19).replace(/:/g, "-")}Z-suite`;
}
