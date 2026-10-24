// renderReport, over a hand-built Run: four Games of two seeds, two won, one
// stalled at the cap and one ended by an Agent's invalid answer.
import type { AgentMeasurements, DecisionRecord, GameOutcome, Intent, Replay, Seat } from "@tcg-htc/runner";
import { describe, expect, it } from "vitest";
import { agentTotals, type GameFile, type GameFileSetup } from "./gameFile.js";
import { exitCriteria, renderReport, reproduceCommand } from "./report.js";
import type { Manifest, ManifestGame } from "./run.js";

const IRA = "Ira, Crimson Haze";
const BRAVO = "Bravo, Flattering Showman";
const heroesOf = (first: string): readonly [string, string] => (first === "ira" ? [IRA, BRAVO] : [BRAVO, IRA]);

const manifestConfig: Manifest["config"] = {
  seeds: [1, 2],
  lists: ["ira", "bravo"],
  configs: [
    { model: "opus", effort: "medium" },
    { model: "sonnet", effort: "high" },
  ],
  concurrency: 2,
  maxSteps: 50,
};

/** A Decision record with just what the report reads. */
function record(seat: Seat, measurements: AgentMeasurements): DecisionRecord {
  return { seat, rendered: "", intents: [], decision: { intent: { kind: "pass" } as Intent, measurements } };
}

/** `count` decisions alternating Seats, each with the same measurements. */
function records(count: number, model: readonly [string, string], measured: Omit<AgentMeasurements, "model" | "effort">): DecisionRecord[] {
  return Array.from({ length: count }, (_, i) => {
    const seat: Seat = i % 2 === 0 ? 0 : 1;
    return record(seat, { model: model[seat], effort: manifestConfig.configs[seat].effort, ...measured });
  });
}

const steady = { inputTokens: 100, cachedTokens: 1000, outputTokens: 10, latencyMs: 2000, costUsd: 0.01, retries: 0, firstAnswerInvalid: false, notesCut: false };

interface Fixture {
  seed: number;
  first: "ira" | "bravo";
  outcome: GameOutcome;
  turns: number;
  decisions: DecisionRecord[];
}

function gameFile({ seed, first, outcome, turns, decisions }: Fixture): GameFile {
  const heroes = heroesOf(first);
  const perSeat = (seat: Seat) => agentTotals(decisions.filter((entry) => entry.seat === seat));
  return {
    status: "complete",
    setup: { seed, startingSeat: 0, lists: heroes, heroes, decklists: [{}, {}] as unknown as GameFileSetup["decklists"], configs: manifestConfig.configs },
    decklistDecisions: [],
    systemPrompts: ["", ""],
    replay: { decklists: [{}, {}] as unknown as Replay["decklists"], seed, startingSeat: 0, intents: [] },
    outcome,
    turns,
    measurements: { decisionsPerSeat: [0, 0], decisions: [], durationMs: 0, perSeat: [perSeat(0), perSeat(1)], totals: agentTotals(decisions), builds: agentTotals([]) },
    decisions,
  };
}

const fixtures: Fixture[] = [
  // 4 decisions: 400 in, 4,000 cached, 40 out, 8 s, $0.04.
  { seed: 1, first: "ira", outcome: { outcome: "win", winner: 1 }, turns: 10, decisions: records(4, ["claude-opus-4-1", "claude-sonnet-4-5"], steady) },
  // 2 decisions, one retried after an invalid first answer, one with cut notes: 400 in, 2,000 cached, 60 out, 10 s, $0.06.
  {
    seed: 1,
    first: "bravo",
    outcome: { outcome: "win", winner: 0 },
    turns: 8,
    decisions: [
      record(0, { model: "claude-opus-4-1-20260101", effort: "medium", ...steady, inputTokens: 200, outputTokens: 30, latencyMs: 5000, costUsd: 0.03, retries: 1, firstAnswerInvalid: true }),
      record(1, { model: "claude-sonnet-4-5", effort: "high", ...steady, inputTokens: 200, outputTokens: 30, latencyMs: 5000, costUsd: 0.03, notesCut: true }),
    ],
  },
  // Stalled at the cap: 50 decisions of the steady kind: 5,000 in, 50,000 cached, 500 out, 100 s, $0.50.
  { seed: 2, first: "ira", outcome: { outcome: "stall", seed: 2, step: 50, detail: "Game exceeded 50 steps" }, turns: 9, decisions: records(50, ["claude-opus-4-1", "claude-sonnet-4-5"], steady) },
  // Ended by Seat 1's second invalid answer at step 7: 8 decisions: 800 in, 8,000 cached, 80 out, 16 s, $0.08.
  {
    seed: 2,
    first: "bravo",
    outcome: { outcome: "error", seed: 2, step: 7, detail: "Seat 1's Claude Agent (sonnet, high): Your answer named Intent 9 but only 1 to 4 are listed", cause: "invalid-answer" },
    turns: 3,
    decisions: records(8, ["claude-opus-4-1", "claude-sonnet-4-5"], steady),
  },
];

const games: ManifestGame[] = fixtures.map(({ seed, first, outcome, decisions }) => ({
  id: `${seed}-${first}-first`,
  seed,
  first,
  status: outcome.outcome === "win" || outcome.outcome === "draw" ? "complete" : "failed",
  outcome,
  file: `game-${seed}-${first}-first.json`,
  steps: outcome.outcome === "stall" || outcome.outcome === "error" ? outcome.step : decisions.length,
  startedAt: "2026-10-24T12:00:01.000Z",
  finishedAt: "2026-10-24T12:30:00.000Z",
}));

const manifest: Manifest = {
  status: "complete",
  config: manifestConfig,
  startedAt: "2026-10-24T12:00:00.000Z",
  updatedAt: "2026-10-24T13:00:00.000Z",
  games,
};
const gameFiles = Object.fromEntries(fixtures.map((fixture) => [`${fixture.seed}-${fixture.first}-first`, gameFile(fixture)]));
const options = { upstreamCommit: "22e9ed8b952efaa746ce4f0f8d5c975a703ab683", runDir: "results/2026-10-24T12-00-00Z-suite" };

const rows = (markdown: string, heading: string): string[] => {
  const section = markdown.split(/^## /m).find((part) => part.startsWith(heading)) ?? "";
  return section.split("\n").filter((line) => line.startsWith("|") && !/^\|( --- \|)+$/.test(line));
};

describe("renderReport", () => {
  const report = renderReport(manifest, gameFiles, options);

  it("opens with the title and the verdict", () => {
    expect(report).toMatch(/^# Phase 2 report: Claude Agents play Ira vs Bravo through Claude Code\n/);
    expect(report).toContain("Verdict: **fail**");
    expect(report).toContain("2 of 4 Games ended in a win or draw");
  });

  it("describes the setup: engine commit, Lists, each Seat's model and effort, seeds, seat orders, cap, concurrency, Run directory and command", () => {
    expect(report).toContain("upstream commit `22e9ed8b952efaa746ce4f0f8d5c975a703ab683`");
    expect(report).toContain("ira-crimson-haze.txt");
    expect(report).toContain("bravo-flattering-showman.txt");
    expect(report).toContain("Seat 0 `opus` at `medium`, Seat 1 `sonnet` at `high`");
    expect(report).toContain("**Seeds:** 1 to 2");
    expect(report).toContain("That makes 4 Games.");
    expect(report).toContain("**Decision cap:** 50");
    expect(report).toContain("**Concurrency:** 2 Games at a time");
    expect(report).toContain("`results/2026-10-24T12-00-00Z-suite`");
    expect(report).toContain("`pnpm suite:claude --model0 opus --effort0 medium --model1 sonnet --effort1 high --seeds 1-2 --concurrency 2`");
  });

  it("tabulates the outcomes and one row per Game", () => {
    expect(rows(report, "Results")).toEqual([
      "| Outcome | Games |",
      "| Win | 2 (Ira 0, Bravo 2) |",
      "| Draw | 0 |",
      "| Stall | 1 |",
      "| Error | 1 |",
      "| Game | Seed | Seat order | Outcome | Winner | Decisions | Turns |",
      "| `1-ira-first` | 1 | Ira (Seat 0) vs Bravo (Seat 1) | win | Bravo (Seat 1) | 4 | 10 |",
      "| `1-bravo-first` | 1 | Bravo (Seat 0) vs Ira (Seat 1) | win | Bravo (Seat 0) | 2 | 8 |",
      "| `2-ira-first` | 2 | Ira (Seat 0) vs Bravo (Seat 1) | stall at step 50 | - | 50 | 9 |",
      "| `2-bravo-first` | 2 | Bravo (Seat 0) vs Ira (Seat 1) | error (invalid-answer) at step 7 | - | 8 | 3 |",
    ]);
  });

  it("tabulates the measurements per Game and per decision, the totals, and the models reported per Seat", () => {
    // Per Game over 4 Games: decisions 4, 2, 50, 8; input 400, 400, 5,000, 800; latency 8, 10, 100, 16 s; cost 0.04, 0.06, 0.50, 0.08.
    // Per decision over 64 decisions: input 6,600 / 64 = 103.1, max 200; cached 64,000 / 64 = 1,000; output 680 / 64 = 10.6, max 30; latency 134 s / 64 = 2.1 s, max 5.0 s.
    expect(rows(report, "Measurements")).toEqual([
      "| Measurement | Average | Maximum |",
      "| Decisions per Game | 16.0 | 50 |",
      "| Turns per Game | 7.5 | 10 |",
      "| Input tokens per Game | 1,650.0 | 5,000 |",
      "| Input tokens per decision | 103.1 | 200 |",
      "| Cached tokens per Game | 16,000.0 | 50,000 |",
      "| Cached tokens per decision | 1,000.0 | 1,000 |",
      "| Output tokens per Game | 170.0 | 500 |",
      "| Output tokens per decision | 10.6 | 30 |",
      "| Latency per Game (s) | 33.5 | 100.0 |",
      "| Latency per decision (s) | 2.1 | 5.0 |",
      "| Cost estimate per Game ($) | 0.17 | 0.50 |",
      "| Total | Value |",
      "| Decisions | 64 |",
      "| Cost estimate ($) | 0.68 |",
      "| Retries | 1 |",
      "| Invalid first answers | 1 |",
      "| Plan notes cut | 1 |",
      "| Seat | Config | Models Claude Code reported |",
      "| 0 | `opus` at `medium` | `claude-opus-4-1`, `claude-opus-4-1-20260101` |",
      "| 1 | `sonnet` at `high` | `claude-sonnet-4-5` |",
    ]);
  });

  it("gives each exit criterion its verdict", () => {
    expect(rows(report, "Exit criteria")).toEqual([
      "| Criterion | Verdict |",
      "| All 4 Games end in a win or draw, with no stalls and no errors | Fail: 2 failed (1 stall, 1 error) |",
      "| No Game ended on an Agent's fault (an error outcome with a Decision failure cause) | Fail: 1 Game (`2-bravo-first`, invalid-answer) |",
    ]);
    expect(exitCriteria(manifest)).toMatchObject({ passed: false });
    expect(exitCriteria({ ...manifest, games: games.slice(0, 2) })).toEqual({
      passed: true,
      rows: [
        { criterion: "All 2 Games end in a win or draw, with no stalls and no errors", verdict: "Pass" },
        { criterion: "No Game ended on an Agent's fault (an error outcome with a Decision failure cause)", verdict: "Pass" },
      ],
    });
  });

  it("lists every failing Game with its seed, seat order, step, outcome, cause, detail and the command that reproduces it", () => {
    const failures = report.split("## Failures and issues filed")[1]!.split("## Decisions")[0]!;
    expect(failures).toContain(
      "- `2-ira-first`: seed 2, Ira (Seat 0) vs Bravo (Seat 1), step 50, **stall**: Game exceeded 50 steps.\n  Reproduce: `pnpm game:claude --seed 2 --first ira --model0 opus --effort0 medium --model1 sonnet --effort1 high`",
    );
    expect(failures).toContain(
      "- `2-bravo-first`: seed 2, Bravo (Seat 0) vs Ira (Seat 1), step 7, **error** (invalid-answer): Seat 1's Claude Agent (sonnet, high): Your answer named Intent 9 but only 1 to 4 are listed.\n  Reproduce: `pnpm game:claude --seed 2 --first bravo --model0 opus --effort0 medium --model1 sonnet --effort1 high`",
    );
    expect(reproduceCommand(games[2]!, manifestConfig)).toBe("pnpm game:claude --seed 2 --first ira --model0 opus --effort0 medium --model1 sonnet --effort1 high");
  });

  it("leaves the Decisions and Notes for the next phase sections for the owner", () => {
    expect(report).toMatch(/\n## Decisions\n\n_To be written by the owner \(#178\)\._\n/);
    expect(report).toMatch(/\n## Notes for the next phase\n\n_To be written by the owner \(#178\)\._\n$/);
  });

  it("passes and reports no failures when every Game is a win or a draw", () => {
    const passing = renderReport({ ...manifest, games: games.slice(0, 2) }, gameFiles, options);
    expect(passing).toContain("Verdict: **pass**. All 2 Games ended in a win or draw, and no Game ended on an Agent's fault.");
    expect(passing).toContain("## Failures and issues filed\n\nNone.");
  });

  it("reports a Game that failed before its file was written, with no measurements for it", () => {
    const unstarted: ManifestGame = {
      ...games[3]!,
      id: "3-ira-first",
      seed: 3,
      first: "ira",
      file: "game-3-ira-first.json",
      steps: 0,
      outcome: { outcome: "error", seed: 3, step: 0, detail: "spawn claude ENOENT" },
    };
    const report = renderReport({ ...manifest, games: [...games, unstarted] }, gameFiles, options);
    expect(rows(report, "Results")).toContain("| `3-ira-first` | 3 | Ira (Seat 0) vs Bravo (Seat 1) | error at step 0 | - | 0 | - |");
    expect(rows(report, "Measurements")).toContain("| Decisions per Game | 16.0 | 50 |");
    expect(report).toContain("- `3-ira-first`: seed 3, Ira (Seat 0) vs Bravo (Seat 1), step 0, **error**: spawn claude ENOENT.");
    expect(rows(report, "Exit criteria")[2]).toBe(
      "| No Game ended on an Agent's fault (an error outcome with a Decision failure cause) | Fail: 1 Game (`2-bravo-first`, invalid-answer) |",
    );
  });
});
