// The two fixture Lists the Claude scripts play, by the hero name the flags use.
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, type List } from "@tcg-htc/runner";
import type { Hero } from "./gameClaudeArgs.js";

/** Each hero's List file in `packages/runner/lists`. */
export const HERO_LIST_FILES: Readonly<Record<Hero, string>> = { ira: IRA_LIST_FILE, bravo: BRAVO_LIST_FILE };

/** The List for a hero, loaded. */
export function heroList(hero: Hero): List {
  return fixtureList(HERO_LIST_FILES[hero]);
}

/** The hero's name as the report prints it: "ira" becomes "Ira". */
export function heroTitle(hero: string): string {
  return hero.charAt(0).toUpperCase() + hero.slice(1);
}
