import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { missingDocPaths } from "./upstreamDoc.js";

const repoRoot = join(import.meta.dirname, "../../..");

describe("missingDocPaths", () => {
  it("names a cited path that exists in neither root", () => {
    const doc = "See `packages/runner/src/game.ts` and `packages/engine/src/gone.ts`.";
    const exists = (path: string) => path.endsWith("game.ts");

    expect(missingDocPaths(doc, exists)).toEqual(["packages/engine/src/gone.ts"]);
  });

  it("finds every path docs/upstream.md cites", () => {
    const doc = readFileSync(join(repoRoot, "docs/upstream.md"), "utf8");
    const exists = (path: string) =>
      existsSync(join(repoRoot, path)) || existsSync(join(repoRoot, "vendor/fyendal.net", path));

    expect(missingDocPaths(doc, exists)).toEqual([]);
  });
});
