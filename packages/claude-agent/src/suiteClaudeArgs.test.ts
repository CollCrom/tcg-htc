import { describe, expect, it } from "vitest";
import { formatSeeds, parseSeeds, parseSuiteClaudeArgs, suiteRunDirName } from "./suiteClaudeArgs.js";

describe("parseSuiteClaudeArgs", () => {
  it("reads each Seat's model and effort, the concurrency, the seeds and the results directory", () => {
    expect(
      parseSuiteClaudeArgs(["--model0", "sonnet", "--effort0", "high", "--model1", "haiku", "--effort1", "low", "--concurrency", "3", "--seeds", "2-4", "--results", "out"]),
    ).toEqual({
      config: {
        seeds: [2, 3, 4],
        lists: ["ira", "bravo"],
        configs: [
          { model: "sonnet", effort: "high" },
          { model: "haiku", effort: "low" },
        ],
        concurrency: 3,
        maxSteps: 600,
      },
      results: "out",
    });
  });

  it("defaults to seeds 1 to 5, opus at medium in both Seats, two Games at a time and the results directory", () => {
    expect(parseSuiteClaudeArgs([])).toEqual({
      config: {
        seeds: [1, 2, 3, 4, 5],
        lists: ["ira", "bravo"],
        configs: [
          { model: "opus", effort: "medium" },
          { model: "opus", effort: "medium" },
        ],
        concurrency: 2,
        maxSteps: 600,
      },
      results: "results",
    });
  });

  it("rejects a model or effort Claude Code doesn't have, a concurrency under one, bad seeds, a flag it doesn't know and --resume for now", () => {
    expect(() => parseSuiteClaudeArgs(["--model1", "gpt"])).toThrow(/--model1.*opus.*sonnet.*haiku.*fable/);
    expect(() => parseSuiteClaudeArgs(["--effort0", "extreme"])).toThrow(/--effort0.*low.*medium.*high.*xhigh.*max/);
    expect(() => parseSuiteClaudeArgs(["--concurrency", "0"])).toThrow(/--concurrency/);
    expect(() => parseSuiteClaudeArgs(["--concurrency", "two"])).toThrow(/--concurrency/);
    expect(() => parseSuiteClaudeArgs(["--seeds", "five"])).toThrow(/--seeds/);
    expect(() => parseSuiteClaudeArgs(["--seeds", "5-1"])).toThrow(/--seeds/);
    expect(() => parseSuiteClaudeArgs(["--seat", "1"])).toThrow(/--seat/);
    expect(() => parseSuiteClaudeArgs(["extra"])).toThrow(/extra/);
    expect(() => parseSuiteClaudeArgs(["--resume", "results/some-run"])).toThrow(/--resume.*not implemented yet/);
  });
});

describe("parseSeeds", () => {
  it("reads a range, a comma list, or one seed", () => {
    expect(parseSeeds("1-5")).toEqual([1, 2, 3, 4, 5]);
    expect(parseSeeds("1,3,8")).toEqual([1, 3, 8]);
    expect(parseSeeds("7")).toEqual([7]);
    expect(parseSeeds("1-2,5")).toEqual([1, 2, 5]);
  });

  it("rejects what isn't a seed", () => {
    expect(() => parseSeeds("")).toThrow(/--seeds/);
    expect(() => parseSeeds("1.5")).toThrow(/--seeds/);
    expect(() => parseSeeds("3-1")).toThrow(/--seeds/);
    expect(() => parseSeeds("1,1")).toThrow(/--seeds/);
  });
});

describe("formatSeeds", () => {
  it("writes consecutive seeds as a range and the rest as a list", () => {
    expect(formatSeeds([1, 2, 3, 4, 5])).toBe("1-5");
    expect(formatSeeds([1, 3, 8])).toBe("1,3,8");
    expect(formatSeeds([7])).toBe("7");
    expect(parseSeeds(formatSeeds([2, 3, 4]))).toEqual([2, 3, 4]);
  });
});

describe("suiteRunDirName", () => {
  it("names a Run by when it started", () => {
    expect(suiteRunDirName(new Date("2026-10-24T09:05:30.123Z"))).toBe("2026-10-24T09-05-30Z-suite");
  });
});
