// The two heroes the Claude scripts play between, by the name the flags, Game
// ids and the manifest use, and their fixture Lists. `heroOf` is the one
// mapping from a List's hero card name back to that identifier.
import { BRAVO_LIST_FILE, fixtureList, IRA_LIST_FILE, type List } from "@tcg-htc/runner";

/** The heroes a Game can be played between, by the name the flags use. */
export const HEROES = ["ira", "bravo"] as const;
export type Hero = (typeof HEROES)[number];

/** Each hero's List file in `packages/runner/lists`. */
export const HERO_LIST_FILES: Readonly<Record<Hero, string>> = { ira: IRA_LIST_FILE, bravo: BRAVO_LIST_FILE };

const loaded = new Map<Hero, List>();

/** The List for a hero, loaded once. */
export function heroList(hero: Hero): List {
  let list = loaded.get(hero);
  if (!list) {
    list = fixtureList(HERO_LIST_FILES[hero]);
    loaded.set(hero, list);
  }
  return list;
}

/** The hero whose List is led by the hero card of this name: "Ira, Crimson
 * Haze" is `ira`. Throws for a name no List here is led by. */
export function heroOf(heroName: string): Hero {
  const hero = HEROES.find((candidate) => heroList(candidate).hero.name === heroName);
  if (!hero) throw new Error(`no List here is led by ${heroName}; the heroes are ${HEROES.join(" and ")}`);
  return hero;
}

/** The other of the two heroes: the opponent of `hero`. */
export function otherHero(hero: Hero): Hero {
  return hero === "ira" ? "bravo" : "ira";
}

/** The hero's name as the report prints it: "ira" becomes "Ira". */
export function heroTitle(hero: Hero): string {
  return hero.charAt(0).toUpperCase() + hero.slice(1);
}
