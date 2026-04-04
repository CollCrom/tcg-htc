"""Integration tests — full game smoke tests with actual decklists.

Tests:
1. Smoke test running complete games with Cindra and Arakni decklists
2. Hero abilities fire (triggered effects registered)
3. Card abilities registered for decklist cards
4. Equipment abilities registered for decklist equipment
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from htc.cards.card_db import CardDatabase
from htc.decks.deck_list import DeckEntry, DeckList
from htc.engine.abilities import AbilityRegistry
from htc.engine.game import Game, GameResult
from htc.enums import Color, EquipmentSlot
from htc.player.random_player import RandomPlayer

DATA_DIR = Path(__file__).parent.parent.parent / "data"
REF_DIR = Path(__file__).parent.parent.parent / "ref"

_COLOR_MAP = {
    "red": Color.RED,
    "yellow": Color.YELLOW,
    "blue": Color.BLUE,
}


# ---------------------------------------------------------------------------
# Markdown decklist parser
# ---------------------------------------------------------------------------


def parse_markdown_decklist(text: str) -> DeckList:
    """Parse a markdown decklist (ref/ format) into a DeckList.

    Handles the markdown structure with ## Hero, ## Weapons, ## Equipment,
    and ## Deck sections. Card lines like '- 3x Card Name (Red)' or
    '- Card Name (Head)'.
    """
    hero_name = ""
    weapons: list[str] = []
    equipment: list[str] = []
    cards: list[DeckEntry] = []
    section = ""

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Detect sections
        if line.startswith("## Hero"):
            section = "hero"
            continue
        elif line.startswith("## Weapon"):
            section = "weapons"
            continue
        elif line.startswith("## Equipment"):
            section = "equipment"
            continue
        elif line.startswith("## Deck"):
            section = "deck"
            continue
        elif line.startswith("### "):
            # Sub-sections within Deck — skip the header
            continue
        elif line.startswith("## ") or line.startswith("# "):
            section = ""
            continue
        elif line.startswith("**"):
            continue

        if section == "hero" and not line.startswith("-"):
            hero_name = line
        elif section == "weapons" and line.startswith("-"):
            wname, count = _parse_equipment_line_with_count(line)
            if wname:
                weapons.extend([wname] * count)
        elif section == "equipment" and line.startswith("-"):
            ename, count = _parse_equipment_line_with_count(line)
            if ename:
                equipment.extend([ename] * count)
        elif section == "deck" and line.startswith("-"):
            entry = _parse_deck_card_line(line)
            if entry:
                cards.append(entry)

    # Auto-include Agent of Chaos Demi-Heroes for Arakni, Marionette
    from htc.decks.loader import AGENT_OF_CHAOS_DEMI_HEROES
    demi_heroes: list[str] = []
    if "arakni" in hero_name.lower() and "marionette" in hero_name.lower():
        demi_heroes = list(AGENT_OF_CHAOS_DEMI_HEROES)

    return DeckList(hero_name=hero_name, weapons=weapons, equipment=equipment, cards=cards, demi_heroes=demi_heroes)


def _parse_equipment_line(line: str) -> str | None:
    """Parse '- 2x Kunai of Retribution (1H Dagger)' or '- Mask of Momentum (Head)'.

    Returns just the card name, stripping count and parenthetical annotation.
    """
    name, _ = _parse_equipment_line_with_count(line)
    return name


def _parse_equipment_line_with_count(line: str) -> tuple[str | None, int]:
    """Parse equipment line, returning (name, count)."""
    line = line.lstrip("- ").strip()
    count = 1
    m = re.match(r"(\d+)x\s+", line)
    if m:
        count = int(m.group(1))
        line = line[m.end():]
    # Strip parenthetical suffix like '(Head)' or '(1H Dagger)'
    line = re.sub(r"\s*\([^)]*\)\s*$", "", line)
    name = line.strip() if line.strip() else None
    return name, count


def _parse_deck_card_line(line: str) -> DeckEntry | None:
    """Parse '- 3x Card Name (Red)' into a DeckEntry."""
    line = line.lstrip("- ").strip()
    count = 1
    m = re.match(r"(\d+)x\s+", line)
    if m:
        count = int(m.group(1))
        line = line[m.end():]

    color: Color | None = None
    for color_name, color_enum in _COLOR_MAP.items():
        suffix = f"({color_name})"
        if line.lower().endswith(suffix):
            color = color_enum
            line = line[: -len(suffix)].strip()
            break

    if not line:
        return None

    return DeckEntry(name=line, color=color, count=count)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def card_db() -> CardDatabase:
    return CardDatabase.load(DATA_DIR / "cards.tsv")


@pytest.fixture(scope="module")
def cindra_deck() -> DeckList:
    text = (REF_DIR / "decklist-cindra-blue.md").read_text()
    return parse_markdown_decklist(text)


@pytest.fixture(scope="module")
def arakni_deck() -> DeckList:
    text = (REF_DIR / "decklist-arakni.md").read_text()
    return parse_markdown_decklist(text)


# ---------------------------------------------------------------------------
# Test: Decklist parsing
# ---------------------------------------------------------------------------


class TestDecklistParsing:
    """Verify the markdown parser loads decklists correctly."""

    def test_cindra_hero(self, cindra_deck: DeckList) -> None:
        assert cindra_deck.hero_name == "Cindra, Dracai of Retribution"

    def test_cindra_weapons(self, cindra_deck: DeckList) -> None:
        assert "Kunai of Retribution" in cindra_deck.weapons
        assert "Claw of Vynserakai" in cindra_deck.weapons

    def test_cindra_equipment(self, cindra_deck: DeckList) -> None:
        assert "Mask of Momentum" in cindra_deck.equipment
        assert "Flick Knives" in cindra_deck.equipment
        assert "Blood Splattered Vest" in cindra_deck.equipment
        assert "Fyendal's Spring Tunic" in cindra_deck.equipment

    def test_cindra_deck_cards(self, cindra_deck: DeckList) -> None:
        # 80 cards in the decklist
        # Some may not be in CSV (Enflame the Firebrand missing), but parsing should work
        assert cindra_deck.total_deck_cards > 70

    def test_arakni_hero(self, arakni_deck: DeckList) -> None:
        assert arakni_deck.hero_name == "Arakni, Marionette"

    def test_arakni_weapons(self, arakni_deck: DeckList) -> None:
        assert "Hunter's Klaive" in arakni_deck.weapons

    def test_arakni_equipment(self, arakni_deck: DeckList) -> None:
        assert "Mask of Deceit" in arakni_deck.equipment
        assert "Blacktek Whisperers" in arakni_deck.equipment

    def test_arakni_deck_cards(self, arakni_deck: DeckList) -> None:
        assert arakni_deck.total_deck_cards > 70


# ---------------------------------------------------------------------------
# Test: Smoke test — full games complete without crashing
# ---------------------------------------------------------------------------


class TestFullGameSmoke:
    """Run actual games with real decklists. Verify no crashes and sane results."""

    def test_cindra_vs_arakni_game_completes(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Run a game between Cindra and Arakni. Verify it completes."""
        p1 = RandomPlayer(seed=42)
        p2 = RandomPlayer(seed=123)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=7)
        result = game.play()

        assert result is not None
        assert isinstance(result, GameResult)
        # Game should end with a winner or by turn limit
        assert result.turns > 0
        # Life totals should be non-negative
        assert result.final_life[0] >= 0
        assert result.final_life[1] >= 0
        # At least one player should have lost life or hit turn limit
        assert (
            result.final_life[0] < 20
            or result.final_life[1] < 20
            or result.turns >= 200
        )

    def test_multiple_seeds_no_crash(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Run 3 games with different seeds. All should complete."""
        for seed in [1, 42, 999]:
            p1 = RandomPlayer(seed=seed)
            p2 = RandomPlayer(seed=seed + 100)
            game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=seed)
            result = game.play()
            assert result is not None, f"Game crashed with seed={seed}"
            assert result.turns > 0, f"Game had 0 turns with seed={seed}"

    def test_arakni_vs_cindra_reversed(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Reversed player order — Arakni P1, Cindra P2."""
        p1 = RandomPlayer(seed=55)
        p2 = RandomPlayer(seed=66)
        game = Game(card_db, arakni_deck, cindra_deck, p1, p2, seed=77)
        result = game.play()
        assert result is not None
        assert result.turns > 0

    def test_life_totals_consistent(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Winner should have life > 0, loser should have life == 0 (unless turn limit)."""
        p1 = RandomPlayer(seed=42)
        p2 = RandomPlayer(seed=123)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=7)
        result = game.play()

        if result.winner is not None:
            winner_life = result.final_life[result.winner]
            loser_life = result.final_life[1 - result.winner]
            assert winner_life > 0, "Winner should have life remaining"
            assert loser_life == 0, "Loser should be at 0 life"


# ---------------------------------------------------------------------------
# Test: Hero abilities registered
# ---------------------------------------------------------------------------


class TestHeroAbilities:
    """Verify hero ability triggered effects are registered during setup."""

    def test_arakni_hero_ability_registered(
        self, card_db: CardDatabase, arakni_deck: DeckList, cindra_deck: DeckList,
    ) -> None:
        """Arakni's triggered ability should be on the EventBus."""
        from htc.cards.abilities.heroes import ArakniMarionetteTrigger

        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, arakni_deck, cindra_deck, p1, p2, seed=0)
        # Trigger setup by starting a game
        game._setup_game()

        triggers = game.events._triggered_effects
        arakni_triggers = [t for t in triggers if isinstance(t, ArakniMarionetteTrigger)]
        assert len(arakni_triggers) == 1
        assert arakni_triggers[0].controller_index == 0  # Arakni is P1

    def test_cindra_hero_ability_registered(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Cindra's triggered ability should be on the EventBus."""
        from htc.cards.abilities.heroes import CindraRetributionTrigger

        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=0)
        game._setup_game()

        triggers = game.events._triggered_effects
        cindra_triggers = [t for t in triggers if isinstance(t, CindraRetributionTrigger)]
        assert len(cindra_triggers) == 1
        assert cindra_triggers[0].controller_index == 0  # Cindra is P1


# ---------------------------------------------------------------------------
# Test: Equipment abilities registered
# ---------------------------------------------------------------------------


class TestEquipmentAbilities:
    """Verify equipment triggered effects are registered during setup."""

    def test_mask_of_momentum_trigger_registered(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Mask of Momentum trigger should be on EventBus for Cindra."""
        from htc.cards.abilities.equipment import MaskOfMomentumTrigger

        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=0)
        game._setup_game()

        triggers = game.events._triggered_effects
        mom_triggers = [t for t in triggers if isinstance(t, MaskOfMomentumTrigger)]
        assert len(mom_triggers) == 1
        assert mom_triggers[0].controller_index == 0

    def test_cindra_chest_trigger_registered(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Cindra's chest equipment trigger should be on EventBus.

        Cindra has both Blood Splattered Vest and Fyendal's Spring Tunic
        as chest options. Only one fits in the CHEST slot (first loaded wins).
        """
        from htc.cards.abilities.equipment import (
            BloodSplatteredVestTrigger,
            SpringTunicTrigger,
        )

        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=0)
        game._setup_game()

        triggers = game.events._triggered_effects
        cindra_chest_triggers = [
            t for t in triggers
            if isinstance(t, (BloodSplatteredVestTrigger, SpringTunicTrigger))
            and t.controller_index == 0
        ]
        assert len(cindra_chest_triggers) == 1

    def test_arakni_spring_tunic_registered(
        self, card_db: CardDatabase, arakni_deck: DeckList, cindra_deck: DeckList,
    ) -> None:
        """Arakni's Spring Tunic should be registered."""
        from htc.cards.abilities.equipment import SpringTunicTrigger

        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, arakni_deck, cindra_deck, p1, p2, seed=0)
        game._setup_game()

        triggers = game.events._triggered_effects
        tunic_triggers = [t for t in triggers if isinstance(t, SpringTunicTrigger)]
        assert len(tunic_triggers) == 1
        assert tunic_triggers[0].controller_index == 0


# ---------------------------------------------------------------------------
# Test: Card abilities registered in the registry
# ---------------------------------------------------------------------------


class TestCardAbilitiesRegistered:
    """Verify that cards in both decklists have abilities in the registry."""

    def test_generic_abilities_registered(self) -> None:
        """Generic cards shared by both decks should be registered."""
        registry = AbilityRegistry()
        from htc.cards.abilities import (
            register_generic_abilities,
        )
        register_generic_abilities(registry)

        # Ancestral Empowerment, Razor Reflex, Sink Below, Fate Foreseen
        assert registry.lookup("attack_reaction_effect", "Ancestral Empowerment") is not None
        assert registry.lookup("attack_reaction_effect", "Razor Reflex") is not None
        assert registry.lookup("defense_reaction_effect", "Sink Below") is not None
        assert registry.lookup("defense_reaction_effect", "Fate Foreseen") is not None

    def test_assassin_abilities_registered(self) -> None:
        """Assassin cards from Arakni deck should be registered."""
        registry = AbilityRegistry()
        from htc.cards.abilities.assassin import register_assassin_abilities
        register_assassin_abilities(registry)

        # Key Arakni cards
        assert registry.lookup("attack_reaction_effect", "Incision") is not None
        assert registry.lookup("attack_reaction_effect", "To the Point") is not None
        assert registry.lookup("on_play", "Cut from the Same Cloth") is not None

    def test_ninja_abilities_registered(self) -> None:
        """Ninja/Draconic cards from Cindra deck should be registered."""
        registry = AbilityRegistry()
        from htc.cards.abilities.ninja import register_ninja_abilities
        register_ninja_abilities(registry)

        # Key Cindra cards — check a few
        assert registry.lookup("attack_reaction_effect", "Throw Dagger") is not None

    def test_equipment_abilities_registered(self) -> None:
        """Equipment abilities should be registered."""
        registry = AbilityRegistry()
        from htc.cards.abilities.equipment import register_equipment_abilities
        register_equipment_abilities(registry)

        assert registry.lookup("attack_reaction_effect", "Flick Knives") is not None
        assert registry.lookup("attack_reaction_effect", "Tide Flippers") is not None
        assert registry.lookup("attack_reaction_effect", "Blacktek Whisperers") is not None
        # Hunter's Klaive Mark is keyword-driven, no separate on_hit entry

    def test_full_registry_from_game(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """A Game object should have all ability modules registered."""
        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=0)

        # Spot-check across all modules
        reg = game.ability_registry
        assert reg.lookup("attack_reaction_effect", "Ancestral Empowerment") is not None
        assert reg.lookup("attack_reaction_effect", "Incision") is not None
        assert reg.lookup("attack_reaction_effect", "Flick Knives") is not None
        # Hunter's Klaive Mark is keyword-driven, no separate on_hit entry


# ---------------------------------------------------------------------------
# Test: Missing cards are handled gracefully
# ---------------------------------------------------------------------------


class TestMissingCards:
    """Verify the engine handles missing CSV entries without crashing."""

    def test_missing_cards_logged_not_crashed(
        self, card_db: CardDatabase, cindra_deck: DeckList, arakni_deck: DeckList,
    ) -> None:
        """Cards missing from CSV (e.g. Enflame the Firebrand, Stalker's Steps)
        should be skipped gracefully, not crash.
        """
        p1 = RandomPlayer(seed=1)
        p2 = RandomPlayer(seed=2)
        game = Game(card_db, cindra_deck, arakni_deck, p1, p2, seed=0)
        # If this doesn't raise, missing cards were handled
        result = game.play()
        assert result is not None
