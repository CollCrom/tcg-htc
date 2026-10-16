// Finds the names our code declares that use a word GLOSSARY.md marks _Avoid_.

import ts from "typescript";

export interface Breach {
  path: string;
  line: number;
  identifier: string;
  word: string;
  /** The line ends in the upstream marker, which doesn't cover this name. */
  marked: boolean;
}

/** Ends a line whose names must stay upstream's. */
export const UPSTREAM_MARKER = "// glossary: upstream";

/** The only names the marker exempts: the ones upstream forces. */
export const UPSTREAM_MARKER_SCOPE = "an object-literal property or a destructured binding that keeps upstream's field name";

/** The names `files` declare that use one of `glossary`'s _Avoid_ words, as a
 * whole camelCase or snake_case part, or that part plus "s". An Avoid word
 * qualified "(for …)" is wrong in only one sense, so it is left to review.
 * Names a file only reads, such as upstream's fields, aren't checked. */
export function glossaryBreaches(glossary: string, files: { path: string; text: string }[]): Breach[] {
  const words = avoidWords(glossary);
  const breaches: Breach[] = [];
  for (const { path, text } of files) {
    const source = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true);
    const marked = new Set(text.split("\n").flatMap((line, i) => (line.trimEnd().endsWith(UPSTREAM_MARKER) ? [i + 1] : [])));
    const visit = (node: ts.Node): void => {
      const name = declaredName(node);
      if (name) {
        const parts = (name.text.match(/[A-Z]+(?![a-z])|[A-Z]?[a-z]+/g) ?? []).map((part) => part.toLowerCase());
        const word = words.find((word) => parts.some((part) => part === word || part === `${word}s`));
        const line = source.getLineAndCharacterOfPosition(name.getStart()).line + 1;
        const isMarked = marked.has(line);
        if (word && !(isMarked && upstreamForces(node))) {
          breaches.push({ path, line, identifier: name.text, word, marked: isMarked });
        }
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  return breaches;
}

/** The words GLOSSARY.md marks _Avoid_, lower-cased. Throws on an entry that
 * isn't one word of letters: the check compares one part of a name at a time,
 * so such an entry would silently go unenforced. */
function avoidWords(glossary: string): string[] {
  return [...glossary.matchAll(/^_Avoid_:(.*)$/gm)].flatMap((match) =>
    match[1]!
      .split(/,(?![^(]*\))/)
      .map((entry) => entry.trim())
      .filter((entry) => !/\(for /.test(entry))
      .map((entry) => {
        const word = entry.replace(/\(.*\)/, "").trim();
        if (!/^[A-Za-z]+$/.test(word)) {
          throw new Error(
            `GLOSSARY.md Avoid entry "${word}" is not a single word, so the check could never match it. ` +
              'Only entries qualified "(for …)" are skipped.',
          );
        }
        return word.toLowerCase();
      }),
  );
}

/** The name `node` introduces, if it declares one. An import or export that
 * keeps upstream's name introduces nothing. */
function declaredName(node: ts.Node): ts.Identifier | undefined {
  if ((ts.isImportSpecifier(node) || ts.isExportSpecifier(node)) && !node.propertyName) return undefined;
  if (!ts.isDeclarationStatement(node) && !DECLARATIONS.some((is) => is(node))) return undefined;
  const name = ts.getNameOfDeclaration(node as ts.Declaration);
  return name && ts.isIdentifier(name) ? name : undefined;
}

/** Whether `node` names something upstream forces the name of: a property of
 * an object literal we pass to it, or a destructured binding that keeps its
 * field name. Any other declaration is a name we chose. */
function upstreamForces(node: ts.Node): boolean {
  if (ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) return true;
  return ts.isBindingElement(node) && !node.propertyName && ts.isObjectBindingPattern(node.parent);
}

const DECLARATIONS: ((node: ts.Node) => boolean)[] = [
  ts.isVariableDeclaration,
  ts.isParameter,
  ts.isBindingElement,
  ts.isPropertySignature,
  ts.isPropertyDeclaration,
  ts.isPropertyAssignment,
  ts.isShorthandPropertyAssignment,
  ts.isMethodDeclaration,
  ts.isMethodSignature,
  ts.isGetAccessor,
  ts.isSetAccessor,
  ts.isEnumMember,
  ts.isTypeParameterDeclaration,
  ts.isImportSpecifier,
  ts.isExportSpecifier,
  ts.isImportClause,
  ts.isNamespaceImport,
];
