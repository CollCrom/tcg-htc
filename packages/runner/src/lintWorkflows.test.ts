import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const repoRoot = join(import.meta.dirname, "../../..");
const tempDir = mkdtempSync(join(tmpdir(), "lint-workflows-"));
// A fresh cache, so the script has to bootstrap from nothing.
const cacheDir = join(tempDir, "cache");

const lintWorkflows = (...args: string[]) =>
  spawnSync("bash", [join(repoRoot, "scripts/lint-workflows.sh"), ...args], {
    cwd: repoRoot,
    encoding: "utf8",
    env: { ...process.env, ACTIONLINT_CACHE_DIR: cacheDir },
  });

describe("pnpm lint:workflows", () => {
  // The first run downloads actionlint and says so on stdout; every test below
  // expects the quiet, cached run.
  beforeAll(() => {
    expect(lintWorkflows("-version").status).toBe(0);
  });

  afterAll(() => {
    rmSync(tempDir, { recursive: true, force: true });
  });

  it("exits non-zero on a finding", () => {
    const file = join(tempDir, "broken.yml");
    writeFileSync(file, "on: push\njobs:\n  build:\n    steps:\n      - run: echo hi\n");

    const result = lintWorkflows(file);

    expect(result.status).not.toBe(0);
    expect(result.stdout).toContain('"runs-on" section is missing');
  });

  it("passes the repo's workflows", () => {
    const result = lintWorkflows();

    expect(result.stdout).toBe("");
    expect(result.status).toBe(0);
  });

  it("runs actionlint 1.7.7", () => {
    expect(lintWorkflows("-version").stdout).toMatch(/^1\.7\.7\n/);
  });

  it("reuses the cached binary instead of downloading again", () => {
    const result = lintWorkflows("-version");

    expect(result.stdout).not.toContain("Downloading");
    expect(result.status).toBe(0);
  });
});
