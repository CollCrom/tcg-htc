// The single-Game script's flags, parsed apart from the script so they can be
// tested without playing a Game.
import { parseArgs } from "node:util";
import type { ClaudeConfig, Effort, ModelAlias } from "./claudeCode.js";

/** The heroes a Game can be played between, by the name the flags use. */
export const HEROES = ["ira", "bravo"] as const;
export type Hero = (typeof HEROES)[number];

export const MODELS: readonly ModelAlias[] = ["opus", "sonnet", "haiku", "fable"];
export const EFFORTS: readonly Effort[] = ["low", "medium", "high", "xhigh", "max"];

export const DEFAULT_CONFIG: ClaudeConfig = { model: "opus", effort: "medium" };

export interface GameClaudeArgs {
  seed: number;
  /** The hero in Seat 0, which takes the first turn. */
  first: Hero;
  /** Each Seat's Claude Agent config. */
  configs: readonly [ClaudeConfig, ClaudeConfig];
  /** The results directory, as given. */
  results: string;
}

/** The per-Seat model and effort flags, shared with the suite script. */
export const CONFIG_OPTIONS = {
  model0: { type: "string", default: DEFAULT_CONFIG.model },
  effort0: { type: "string", default: DEFAULT_CONFIG.effort },
  model1: { type: "string", default: DEFAULT_CONFIG.model },
  effort1: { type: "string", default: DEFAULT_CONFIG.effort },
} as const;

/** Each Seat's config from the parsed per-Seat flags. */
export function configsFrom(values: Record<keyof typeof CONFIG_OPTIONS, string>): readonly [ClaudeConfig, ClaudeConfig] {
  return [
    { model: oneOf("--model0", values.model0, MODELS), effort: oneOf("--effort0", values.effort0, EFFORTS) },
    { model: oneOf("--model1", values.model1, MODELS), effort: oneOf("--effort1", values.effort1, EFFORTS) },
  ];
}

export const USAGE =
  "pnpm game:claude [--seed <n>] [--first ira|bravo] [--model0 <alias>] [--effort0 <level>] [--model1 <alias>] [--effort1 <level>] [--results <dir>]";

/** Parses the flags (`process.argv.slice(2)`). Throws a message naming the
 * flag at fault. */
export function parseGameClaudeArgs(args: readonly string[]): GameClaudeArgs {
  const { values, positionals } = parseArgs({
    args: [...args],
    options: {
      seed: { type: "string", default: "1" },
      first: { type: "string", default: HEROES[0] },
      ...CONFIG_OPTIONS,
      results: { type: "string", default: "results" },
    },
    allowPositionals: true,
    strict: true,
  });
  if (positionals.length > 0) throw new Error(`unexpected argument ${positionals.join(" ")}\nusage: ${USAGE}`);
  const seed = Number(values.seed);
  if (!/^-?\d+$/.test(values.seed) || !Number.isSafeInteger(seed)) throw new Error(`--seed must be an integer, not ${values.seed}`);
  return {
    seed,
    first: oneOf("--first", values.first, HEROES),
    configs: configsFrom(values),
    results: values.results,
  };
}

/** `value` if `allowed` holds it; otherwise throws a message naming the flag. */
export function oneOf<T extends string>(flag: string, value: string, allowed: readonly T[]): T {
  if (!(allowed as readonly string[]).includes(value)) throw new Error(`${flag} must be one of ${allowed.join(", ")}, not ${value}`);
  return value as T;
}

/** A one-Game Run's directory name: when it started (UTC, to the second, with
 * no colons so Windows can read it), the seed and who went first. */
export function runDirName(started: Date, seed: number, first: Hero): string {
  const stamp = started.toISOString().slice(0, 19).replace(/:/g, "-");
  return `${stamp}Z-game-${seed}-${first}-first`;
}
