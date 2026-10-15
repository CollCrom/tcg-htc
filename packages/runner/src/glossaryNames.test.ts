import { describe, expect, it } from "vitest";
import { glossaryBreaches } from "./glossaryNames.js";

const GLOSSARY = `# Glossary

**List**:
Every card a player brings.
_Avoid_: Pool, deck (for the whole list)
`;

const breachesIn = (text: string) => glossaryBreaches(GLOSSARY, [{ path: "src/a.ts", text }]);

describe("glossaryBreaches", () => {
  it("flags a variable named with an Avoid word, naming the file and line", () => {
    expect(breachesIn("const list = 1;\nconst pool = 2;\n")).toEqual([
      { path: "src/a.ts", line: 2, identifier: "pool", word: "pool" },
    ]);
  });

  it("flags an Avoid word inside a camelCase name, but not one the glossary qualifies with \"for\"", () => {
    expect(breachesIn("function deckPoolOf(deck: string[]) {}\n")).toEqual([
      { path: "src/a.ts", line: 1, identifier: "deckPoolOf", word: "pool" },
    ]);
  });

  it("skips a line ending in the upstream marker, and upstream names it only reads", () => {
    const text = [
      'import { type DeckPool } from "@fyendal/shared";',
      "function presented({ pool }: { pool: DeckPool }) { // glossary: upstream",
      "  return pool.equipmentPool;",
      "}",
    ].join("\n");
    expect(breachesIn(text)).toEqual([]);
  });

  it("reads every Avoid line, and matches plurals and constant case", () => {
    const glossary = `${GLOSSARY}
**Agent**:
The decision-maker occupying a Seat.
_Avoid_: Bot (reserved for upstream's scripted hero bots), AI
`;
    const text = "const MAX_POOL_SIZE = 1;\nconst bots = [];\ntype AIPlayer = {};\nconst said = 1;\n";
    expect(glossaryBreaches(glossary, [{ path: "src/a.ts", text }])).toEqual([
      { path: "src/a.ts", line: 1, identifier: "MAX_POOL_SIZE", word: "pool" },
      { path: "src/a.ts", line: 2, identifier: "bots", word: "bot" },
      { path: "src/a.ts", line: 3, identifier: "AIPlayer", word: "ai" },
    ]);
  });

  it("throws on an Avoid entry of more than one word, which it could never match", () => {
    const glossary = `${GLOSSARY}
**View**:
What a Seat can see.
_Avoid_: Game state, snapshot
`;
    expect(() => glossaryBreaches(glossary, [])).toThrow(
      'GLOSSARY.md Avoid entry "Game state" is not a single word, so the check could never match it. ' +
        'Only entries qualified "(for …)" are skipped.',
    );
  });

  it("throws on a hyphenated Avoid entry, since names are matched a letters-only part at a time", () => {
    expect(() => glossaryBreaches("_Avoid_: Re-roll\n", [])).toThrow('Avoid entry "Re-roll" is not a single word');
  });

  it("still skips a multi-word Avoid entry the glossary qualifies with \"for\"", () => {
    const glossary = "_Avoid_: Pool, card list (for the whole List)\n";
    const text = "const cardList = 1;\nconst pool = 2;\n";
    expect(glossaryBreaches(glossary, [{ path: "src/a.ts", text }])).toEqual([
      { path: "src/a.ts", line: 2, identifier: "pool", word: "pool" },
    ]);
  });

  it("reads an Avoid entry whose explanation contains a comma", () => {
    const glossary = "_Avoid_: State (the full, unhidden game), memo (for a short, private note)\n";
    const text = "const gameState = 1;\nconst memo = 2;\n";
    expect(glossaryBreaches(glossary, [{ path: "src/a.ts", text }])).toEqual([
      { path: "src/a.ts", line: 1, identifier: "gameState", word: "state" },
    ]);
  });
});
