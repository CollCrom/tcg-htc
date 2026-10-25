// One way to write a file a concurrent reader may be opening: the Game file,
// the manifest and the system prompt files all go through it.
import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

/** Writes `text` to `<path>.tmp` and renames it over `path`, creating the
 * directory if need be, so a reader (or a crash) never sees a partial file:
 * `writeFileSync` truncates first, and a `claude` process reading the file at
 * that moment would get an empty or truncated prompt. */
export function writeAtomically(path: string, text: string): void {
  mkdirSync(dirname(path), { recursive: true });
  const temp = `${path}.tmp`;
  writeFileSync(temp, text);
  renameSync(temp, path);
}
