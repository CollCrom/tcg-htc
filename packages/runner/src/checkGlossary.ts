// CI check: fails when a name in packages/*/src uses a word GLOSSARY.md marks
// _Avoid_, or when GLOSSARY.md has an Avoid entry the check could never match.
// Prints one GitHub annotation per breach.
//
// Usage: tsx checkGlossary.ts [glossary path] [source glob]
// Both default to the repo's; the test passes fixtures.

import { globSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { glossaryBreaches, UPSTREAM_MARKER } from "./glossaryNames.js";

const repoRoot = join(import.meta.dirname, "../../..");
const [glossaryPath = join(repoRoot, "GLOSSARY.md"), sourceGlob = "packages/*/src/**/*.ts"] = process.argv.slice(2);
const glossary = readFileSync(glossaryPath, "utf8");
const files = globSync(sourceGlob, { cwd: repoRoot }).map((path) => ({
  path,
  text: readFileSync(resolve(repoRoot, path), "utf8"),
}));

let breaches;
try {
  breaches = glossaryBreaches(glossary, files);
} catch (error) {
  console.log(`::error file=GLOSSARY.md::${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
for (const { path, line, identifier, word } of breaches) {
  console.log(
    `::error file=${path},line=${line}::${identifier} uses "${word}", which GLOSSARY.md marks Avoid. ` +
      `Use the glossary's word, or end the line with "${UPSTREAM_MARKER}" if upstream forces the name.`,
  );
}
console.log(`${files.length} files, ${breaches.length} glossary breaches`);
process.exitCode = breaches.length > 0 ? 1 : 0;
