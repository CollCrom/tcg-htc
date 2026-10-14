// Checks docs/upstream.md's cited paths, which a submodule bump can move.

/** Cited on purpose though absent from a fresh clone: gitignored. */
const ABSENT_BY_DESIGN = new Set(["packages/runner/scratch"]);

const CITED_PATH = /`((?:\.\.\/)*(?:vendor\/fyendal\.net\/)?(?:packages|apps)\/[^`\s]*)`/g;

/** The backticked `packages/...` and `apps/...` paths in `doc`, and relative
 * imports into `vendor/`, that `exists` rejects. A relative import is checked
 * from the repo root, a trailing slash is dropped, and placeholders containing
 * `...` are skipped. */
export function missingDocPaths(doc: string, exists: (path: string) => boolean): string[] {
  const cited = [...doc.matchAll(CITED_PATH)].map((match) =>
    match[1]!.replace(/^(\.\.\/)+/, "").replace(/\/$/, ""),
  );
  return [...new Set(cited)].filter(
    (path) => !path.includes("...") && !ABSENT_BY_DESIGN.has(path) && !exists(path),
  );
}
