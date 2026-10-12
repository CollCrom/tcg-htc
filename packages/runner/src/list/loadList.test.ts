import { describe, expect, it } from "vitest";
import { BRAVO_LIST_FILE, fixtureListText, IRA_LIST_FILE } from "./fixtureLists.js";
import { loadList } from "./loadList.js";

const IRA = fixtureListText(IRA_LIST_FILE);
const BRAVO = fixtureListText(BRAVO_LIST_FILE);

describe("loadList", () => {
  it("loads Ira's List with its hero, arena cards and main-deck cards", () => {
    const list = loadList(IRA);

    expect(list.name).toBe("Sunday Showdown: Atlanta 1st 🇺🇸");
    expect(list.format).toBe("silver-age");
    expect(list.hero).toEqual({ cardId: "CRU046", name: "Ira, Crimson Haze" });
    expect(list.weapons).toEqual([{ cardId: "CRU050", name: "Edge of Autumn", colour: null, count: 1 }]);
    expect(list.equipment.map((e) => [e.name, e.slots])).toEqual([
      ["Blade Beckoner Helm", ["head"]],
      ["Blood Scent", ["chest"]],
      ["Double Cross Strap", ["chest"]],
      ["Mask of the Swarming Claw", ["head"]],
      ["Pouncing Paws", ["legs"]],
      ["Tearing Shuko", ["arms"]],
    ]);
    expect(list.deck).toHaveLength(24);
    expect(list.deck).toContainEqual({ cardId: "CRU063", name: "Flying Kick", colour: "red", count: 2 });
    expect(list.deck).toContainEqual({ cardId: "CRU065", name: "Flying Kick", colour: "blue", count: 2 });
    expect(list.deck.reduce((n, c) => n + c.count, 0)).toBe(48);
  });

  it("loads Bravo's List, counting the off-hand as a weapon", () => {
    const list = loadList(BRAVO);

    expect(list.format).toBe("silver-age");
    expect(list.hero).toEqual({ cardId: "SBR001", name: "Bravo, Flattering Showman" });
    expect(list.weapons).toEqual([
      { cardId: "TCC029", name: "Bastion of Duty", colour: null, count: 1 },
      { cardId: "ELE202B", name: "Titan's Fist", colour: null, count: 1 },
    ]);
    expect(list.equipment).toHaveLength(8);
    expect(list.equipment).toContainEqual({
      cardId: "MPG007", name: "Gauntlet of Boulderhold", colour: null, count: 1, slots: ["arms"],
    });
    expect(list.deck).toContainEqual({ cardId: expect.any(String), name: "Crash and Bash", colour: "red", count: 1 });
    expect(list.deck.reduce((n, c) => n + c.count, 0)).toBe(45);
  });

  it("fails naming a line that doesn't match a card", () => {
    const text = IRA.replace("2x Growl (red)", "2x Grrowl (red)").replace("2x Humble (red)", "2x Humble (purple)");

    expect(() => loadList(text)).toThrow(/2x Grrowl \(red\)[\s\S]*2x Humble \(purple\)/);
  });

  // Every card is implemented at the pinned upstream commit, so the check is swapped out here.
  it("fails naming every unimplemented card with its colour", () => {
    const unimplemented = new Set(["Ira, Crimson Haze|0", "Edge of Autumn|0", "Pouncing Paws|0", "Flying Kick|1"]);
    const isImplemented = (card: { name: string; pitch?: number }) => !unimplemented.has(`${card.name}|${card.pitch ?? 0}`);

    let message = "";
    try {
      loadList(IRA, { isImplemented });
    } catch (error) {
      message = (error as Error).message;
    }

    expect(message).toContain("Ira, Crimson Haze");
    expect(message).toContain("Edge of Autumn");
    expect(message).toContain("Pouncing Paws");
    expect(message).toContain("Flying Kick (red)");
    expect(message).not.toContain("Flying Kick (blue)");
  });

  describe("rejects a List that isn't legal in Silver Age", () => {
    it("more than 2 copies of a card", () => {
      const text = IRA.replace("2x Growl (red)", "3x Growl (red)").replace("2x Humble (red)", "1x Humble (red)");

      expect(() => loadList(text)).toThrow(/growl/i);
    });

    it("more than 55 cards", () => {
      const text = IRA.replace("2x Untamed (red)", "2x Untamed (red)\n1x Brutal Assault (red)");

      expect(() => loadList(text)).toThrow(/56 cards/);
    });

    it("a banned card", () => {
      const text = IRA.replace("2x Growl (red)", "2x Pulping (red)");

      expect(() => loadList(text)).toThrow(/Pulping is banned/);
    });

    it("a benched hero", () => {
      const text = IRA.replace("Hero: Ira, Crimson Haze", "Hero: Briar");

      expect(() => loadList(text)).toThrow(/Briar is benched/);
    });
  });

  it("fails naming a line with a heading it doesn't recognise, such as a card written without a count", () => {
    const text = IRA.replace("2x Aspect of Tiger: Body (red)", "Aspect of Tiger: Body (red)");

    expect(() => loadList(text)).toThrow(/line 16[^\n]*Aspect of Tiger: Body \(red\)/);
  });

  it("fails when the List doesn't state a format", () => {
    expect(() => loadList(IRA.replace("Format: Silver Age\n", ""))).toThrow(/no format/);
  });

  it("fails naming a format other than Silver Age", () => {
    expect(() => loadList(IRA.replace("Format: Silver Age", "Format: Classic Constructed"))).toThrow(
      /Classic Constructed/,
    );
  });
});
