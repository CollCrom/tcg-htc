import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const repoRoot = join(import.meta.dirname, "../../..");
// One cache per test file: the first run downloads actionlint, the rest reuse it.
const cacheDir = mkdtempSync(join(tmpdir(), "actionlint-cache-"));

const lintWorkflows = (...args: string[]) =>
  spawnSync("bash", [join(repoRoot, "scripts/lint-workflows.sh"), ...args], {
    cwd: repoRoot,
    encoding: "utf8",
    env: { ...process.env, ACTIONLINT_CACHE_DIR: cacheDir },
  });

describe("pnpm lint:workflows", () => {
  it("exits non-zero on a finding", () => {
    const dir = mkdtempSync(join(tmpdir(), "workflow-"));
    const file = join(dir, "broken.yml");
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

  it("runs actionlint 1.7.7, the version CI pins", () => {
    expect(lintWorkflows("-version").stdout).toMatch(/^1\.7\.7\n/);
  });

  it("reuses the cached binary instead of downloading again", () => {
    lintWorkflows("-version");

    const result = lintWorkflows("-version");

    expect(result.stdout).not.toContain("Downloading");
    expect(result.status).toBe(0);
  });
});
