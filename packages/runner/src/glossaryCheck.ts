import ts from "typescript";

export interface Breach {
  path: string;
  line: number;
  identifier: string;
  word: string;
}

/** Ends a line whose names must stay upstream's. */
export const UPSTREAM_MARKER = "// glossary: upstream";

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
        if (word && !marked.has(line)) breaches.push({ path, line, identifier: name.text, word });
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  return breaches;
}

function avoidWords(glossary: string): string[] {
  return [...glossary.matchAll(/^_Avoid_:(.*)$/gm)].flatMap((match) =>
    match[1]!
      .split(/,(?![^(]*\))/)
      .map((entry) => entry.trim())
      .filter((entry) => !/\(for /.test(entry))
      .map((entry) => entry.replace(/\(.*\)/, "").trim().toLowerCase()),
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
