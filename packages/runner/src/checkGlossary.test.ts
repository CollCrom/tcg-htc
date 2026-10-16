import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";

const repoRoot = join(import.meta.dirname, "../../..");
const tempDir = mkdtempSync(join(tmpdir(), "check-glossary-"));

const run = (...args: string[]) =>
  spawnSync("pnpm", ["exec", "tsx", "src/checkGlossary.ts", ...args], {
    cwd: join(repoRoot, "packages/runner"),
    encoding: "utf8",
  });

/** Runs the check against a glossary and one source file, both written to a
 * fresh directory, and returns its stdout and exit status. */
const checkGlossary = (glossary: string, source: string) => {
  const dir = mkdtempSync(join(tempDir, "case-"));
  writeFileSync(join(dir, "GLOSSARY.md"), glossary);
  writeFileSync(join(dir, "a.ts"), source);
  return run(join(dir, "GLOSSARY.md"), `${dir}/**/*.ts`);
};

describe("pnpm check:glossary", () => {
  afterAll(() => {
    rmSync(tempDir, { recursive: true, force: true });
  });

  it("exits 0 and prints a summary when no name breaches", () => {
    const result = checkGlossary("_Avoid_: Pool\n", "const list = 1;\n");

    expect(result.stdout).toBe("1 files, 0 glossary breaches\n");
    expect(result.status).toBe(0);
  });

  it("exits 1 with one annotation per breach, naming the file and line", () => {
    const result = checkGlossary("_Avoid_: Pool\n", "const list = 1;\nconst pool = 2;\n");

    expect(result.stdout).toMatch(/^::error file=.*\/a\.ts,line=2::pool uses "pool", which GLOSSARY\.md marks Avoid\. /);
    expect(result.stdout).toMatch(/\n1 files, 1 glossary breaches\n$/);
    expect(result.status).toBe(1);
  });

  it("says the upstream marker doesn't apply to a name we declared ourselves", () => {
    const result = checkGlossary("_Avoid_: Pool\n", "function toUpstreamDeckPool() {} // glossary: upstream\n");

    expect(result.stdout).toMatch(
      /^::error file=.*\/a\.ts,line=1::toUpstreamDeckPool uses "pool", which GLOSSARY\.md marks Avoid\. The "\/\/ glossary: upstream" marker doesn't apply here: /,
    );
    expect(result.status).toBe(1);
  });

  it("exits 1 with an annotation on GLOSSARY.md for an Avoid entry it could never match", () => {
    const result = checkGlossary("_Avoid_: Game state\n", "const list = 1;\n");

    expect(result.stdout).toBe(
      '::error file=GLOSSARY.md::GLOSSARY.md Avoid entry "Game state" is not a single word, so the check could never match it. ' +
        'Only entries qualified "(for …)" are skipped.\n',
    );
    expect(result.status).toBe(1);
  });

  it("checks the repo's own glossary and sources with no arguments", () => {
    const result = run();

    expect(result.stdout).toMatch(/^\d+ files, 0 glossary breaches\n$/);
    expect(result.status).toBe(0);
  });
});
