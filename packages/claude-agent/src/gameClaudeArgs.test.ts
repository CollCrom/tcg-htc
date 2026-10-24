import { describe, expect, it } from "vitest";
import { parseGameClaudeArgs, runDirName } from "./gameClaudeArgs.js";

describe("parseGameClaudeArgs", () => {
  it("reads the seed, which hero goes first, each Seat's model and effort, and the results directory", () => {
    expect(
      parseGameClaudeArgs(["--seed", "7", "--first", "bravo", "--model0", "sonnet", "--effort0", "high", "--model1", "haiku", "--effort1", "low", "--results", "out"]),
    ).toEqual({
      seed: 7,
      first: "bravo",
      configs: [
        { model: "sonnet", effort: "high" },
        { model: "haiku", effort: "low" },
      ],
      results: "out",
    });
  });

  it("defaults to seed 1, Ira first, opus at medium in both Seats and the results directory", () => {
    expect(parseGameClaudeArgs([])).toEqual({
      seed: 1,
      first: "ira",
      configs: [
        { model: "opus", effort: "medium" },
        { model: "opus", effort: "medium" },
      ],
      results: "results",
    });
  });

  it("rejects a seed that isn't an integer, a hero it doesn't know, and a model or effort Claude Code doesn't have", () => {
    expect(() => parseGameClaudeArgs(["--seed", "one"])).toThrow(/--seed/);
    expect(() => parseGameClaudeArgs(["--seed", "1.5"])).toThrow(/--seed/);
    expect(() => parseGameClaudeArgs(["--first", "kano"])).toThrow(/--first.*ira.*bravo/);
    expect(() => parseGameClaudeArgs(["--model1", "gpt"])).toThrow(/--model1.*opus.*sonnet.*haiku.*fable/);
    expect(() => parseGameClaudeArgs(["--effort0", "extreme"])).toThrow(/--effort0.*low.*medium.*high.*xhigh.*max/);
    expect(() => parseGameClaudeArgs(["--seat", "1"])).toThrow(/--seat/);
    expect(() => parseGameClaudeArgs(["extra"])).toThrow(/extra/);
  });
});

describe("runDirName", () => {
  it("names a one-Game Run by when it started, its seed and who went first", () => {
    expect(runDirName(new Date("2026-10-24T09:05:30.123Z"), 7, "bravo")).toBe("2026-10-24T09-05-30Z-game-7-bravo-first");
  });
});
