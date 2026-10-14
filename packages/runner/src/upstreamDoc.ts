// Checks docs/upstream.md's cited paths, which a submodule bump can move.

/** Cited on purpose though absent from a fresh clone: gitignored. */
const ABSENT_BY_DESIGN = new Set(["packages/runner/scratch", "packages/runner/scratch/"]);

/** The backticked `packages/...` paths in `doc` that `exists` rejects.
 * Placeholders containing `...` are skipped. */
export function missingDocPaths(doc: string, exists: (path: string) => boolean): string[] {
  const cited = [...doc.matchAll(/`(packages\/[^`\s]*)`/g)].map((match) => match[1]!);
  return [...new Set(cited)].filter(
    (path) => !path.includes("...") && !ABSENT_BY_DESIGN.has(path) && !exists(path),
  );
}
