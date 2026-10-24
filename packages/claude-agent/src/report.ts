// The Phase 2 report, rendered from a Run's manifest and Game files in the
// shape of docs/phase1-report.md. The owner commits it as docs/phase2-report.md.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { GameFile } from "./gameFile.js";
import type { Manifest } from "./run.js";

export interface ReportOptions {
  upstreamCommit: string;
  /** The Run directory, as the report names it. */
  runDir: string;
}

export const REPORT_TITLE = "Phase 2 report: Claude Agents play Ira vs Bravo through Claude Code";

export function renderReport(manifest: Manifest, gameFiles: Record<string, GameFile>, options: ReportOptions): string {
  void manifest;
  void gameFiles;
  void options;
  return `# ${REPORT_TITLE}\n`;
}

const REPO_ROOT = fileURLToPath(new URL("../../../", import.meta.url));

/** The upstream commit vendored at `vendor/fyendal.net`: what the submodule
 * is at, or failing that the commit AGENTS.md says it is pinned to. */
export function upstreamCommit(repoRoot = REPO_ROOT): string {
  try {
    return execFileSync("git", ["-C", `${repoRoot}vendor/fyendal.net`, "rev-parse", "HEAD"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    const pinned = readFileSync(`${repoRoot}AGENTS.md`, "utf8").match(/pinned to upstream commit `([0-9a-f]{40})`/);
    return pinned?.[1] ?? "unknown";
  }
}
