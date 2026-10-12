import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { loadList } from "./loadList.js";
import { pickDecklist } from "./pickDecklist.js";

const fixture = (file: string) => readFileSync(new URL(`../../lists/${file}`, import.meta.url), "utf8");
const IRA = loadList(fixture("ira-crimson-haze.txt"));
const BRAVO = loadList(fixture("bravo-flattering-showman.txt"));
const EDGE_OF_AUTUMN = "CRU050";
const TITANS_FIST = "ELE202B";
const BASTION_OF_DUTY = "TCC029";
const SEEDS = Array.from({ length: 200 }, (_, i) => i * 7919 - 500_000);

describe("pickDecklist", () => {
  it("picks the same Decklist from the same List and seed", () => {
    expect(pickDecklist(IRA, 7)).toEqual(pickDecklist(IRA, 7));
    expect(pickDecklist(BRAVO, -123)).toEqual(pickDecklist(BRAVO, -123));
  });

  it("can pick different Decklists from different seeds, exercising the whole List", () => {
    const picks = SEEDS.map((seed) => pickDecklist(BRAVO, seed));

    expect(new Set(picks.map((pick) => JSON.stringify(pick))).size).toBeGreaterThan(1);
    expect(new Set(picks.flatMap((pick) => pick.deck))).toEqual(new Set(BRAVO.deck.map((card) => card.cardId)));
    expect(new Set(picks.flatMap((pick) => Object.values(pick.equipment)))).toEqual(
      new Set(BRAVO.equipment.map((piece) => piece.cardId)),
    );
    expect(new Set(picks.map((pick) => [...pick.weaponIds].sort().join("+")))).toEqual(
      new Set([TITANS_FIST, `${TITANS_FIST}+${BASTION_OF_DUTY}`]),
    );
  });

  it("refuses a List whose only weapon-zone card is an off-hand", () => {
    const offHandOnly = loadList(fixture("bravo-flattering-showman.txt").replace("1x Titan's Fist\n", ""));

    expect(() => pickDecklist(offHandOnly, 1)).toThrow(/weapon/);
  });

  describe.each([
    ["Ira", IRA, [[EDGE_OF_AUTUMN]]],
    ["Bravo", BRAVO, [[TITANS_FIST], [TITANS_FIST, BASTION_OF_DUTY]]],
  ])("picks a legal Decklist from %s's List for every seed", (_hero, list, legalWeaponSetups) => {
    const picks = SEEDS.map((seed) => pickDecklist(list, seed));

    it("presents the List's hero", () => {
      for (const pick of picks) expect(pick.heroId).toBe(list.hero.cardId);
    });

    it("has exactly 40 deck cards, no more copies of each than the List's main-deck cards hold", () => {
      const listCopies = new Map(list.deck.map((card) => [card.cardId, card.count]));
      for (const pick of picks) {
        expect(pick.deck).toHaveLength(40);
        const copies = new Map<string, number>();
        for (const id of pick.deck) copies.set(id, (copies.get(id) ?? 0) + 1);
        for (const [id, count] of copies) expect(count).toBeLessThanOrEqual(listCopies.get(id) ?? 0);
      }
    });

    it("has one equipment piece in every slot, each from the List's arena cards and fitting its slot", () => {
      for (const pick of picks) {
        expect(Object.keys(pick.equipment).sort()).toEqual(["arms", "chest", "head", "legs"]);
        for (const [slot, id] of Object.entries(pick.equipment)) {
          const piece = list.equipment.find((candidate) => candidate.cardId === id);
          expect(piece?.slots).toContain(slot);
        }
      }
    });

    it("has a weapon setup that's legal for the hero and holds a weapon", () => {
      for (const pick of picks) expect(legalWeaponSetups).toContainEqual([...pick.weaponIds].sort());
    });
  });
});
