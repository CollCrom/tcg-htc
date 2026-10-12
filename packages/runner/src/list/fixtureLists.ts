// The fixture Lists in packages/runner/lists, for the suite and the tests.
import { readFileSync } from "node:fs";
import { loadList, type List } from "./loadList.js";

export const IRA_LIST_FILE = "ira-crimson-haze.txt";
export const BRAVO_LIST_FILE = "bravo-flattering-showman.txt";

/** The Fabrary export text of a fixture List. */
export function fixtureListText(file: string): string {
  return readFileSync(new URL(`../../lists/${file}`, import.meta.url), "utf8");
}

/** A fixture List, loaded. */
export function fixtureList(file: string): List {
  return loadList(fixtureListText(file));
}
