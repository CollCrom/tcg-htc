"""Tests for pre-game equipment selection phase.

Players choose which equipment to bring from their pool before each game.
For slots with multiple options, a CHOOSE_EQUIPMENT decision is presented.
For slots with only one option, it is auto-selected.
"""

from __future__ import annotations

from pathlib import Path

from htc.cards.card import CardDefinition
from htc.cards.card_db import CardDatabase
from htc.decks.deck_list import DeckEntry, DeckList
from htc.decks.loader import parse_deck_list
from htc.engine.actions import Decision, PlayerResponse
from htc.engine.game import Game
from htc.enums import (
    CardType,
    DecisionType,
    EquipmentSlot,
    SubType,
)
from htc.player.random_player import RandomPlayer
from htc.state.game_state import GameState

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# --- Deck fixtures ---

DECK_ONE_PER_SLOT = """\
Hero: Bravo, Showstopper
Weapons: Anothos
Equipment: Crater Fist, Helm of Isen's Peak, Tectonic Plating, Ironrot Legs
---
3x Adrenaline Rush (Red)
3x Adrenaline Rush (Yellow)
3x Adrenaline Rush (Blue)
3x Debilitate (Red)
3x Debilitate (Yellow)
3x Debilitate (Blue)
3x Pummel (Red)
3x Pummel (Yellow)
3x Pummel (Blue)
3x Cartilage Crush (Red)
3x Cartilage Crush (Yellow)
3x Cartilage Crush (Blue)
3x Disable (Red)
3x Disable (Yellow)
3x Disable (Blue)
3x Sink Below (Red)
3x Sink Below (Yellow)
3x Sink Below (Blue)
3x Sigil of Solace (Red)
3x Sigil of Solace (Blue)
"""

# Deck with 2 chest options and 2 legs options (like Cindra)
DECK_MULTI_SLOT = """\
Hero: Bravo, Showstopper
Weapons: Anothos
Equipment: Helm of Isen's Peak, Tectonic Plating, Ironrot Legs, Crater Fist, Nullrune Robe, Nullrune Boots
---
3x Adrenaline Rush (Red)
3x Adrenaline Rush (Yellow)
3x Adrenaline Rush (Blue)
3x Debilitate (Red)
3x Debilitate (Yellow)
3x Debilitate (Blue)
3x Pummel (Red)
3x Pummel (Yellow)
3x Pummel (Blue)
3x Cartilage Crush (Red)
3x Cartilage Crush (Yellow)
3x Cartilage Crush (Blue)
3x Disable (Red)
3x Disable (Yellow)
3x Disable (Blue)
3x Sink Below (Red)
3x Sink Below (Yellow)
3x Sink Below (Blue)
3x Sigil of Solace (Red)
3x Sigil of Solace (Blue)
"""


class EquipmentTrackingPlayer:
    """A player that records CHOOSE_EQUIPMENT decisions and picks a specific option."""

    def __init__(self, choices: dict[str, str] | None = None, seed: int = 0):
        """
        choices: maps slot name (e.g. "chest") to the equipment name to pick.
        If a slot is not in choices, picks the first option.
        """
        self.choices = choices or {}
        self.equipment_decisions: list[Decision] = []
        self._random = RandomPlayer(seed=seed)

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        if decision.decision_type == DecisionType.CHOOSE_EQUIPMENT:
            self.equipment_decisions.append(decision)
            # Check if we have a preference for this slot
            for slot_name, equip_name in self.choices.items():
                if slot_name in decision.prompt:
                    target_id = f"equip_{equip_name}"
                    for opt in decision.options:
                        if opt.action_id == target_id:
                            return PlayerResponse(selected_option_ids=[target_id])
            # Default: pick first option
            return PlayerResponse(selected_option_ids=[decision.options[0].action_id])
        return self._random.decide(game_state, decision)


def _load_db() -> CardDatabase:
    return CardDatabase.load(DATA_DIR / "cards.tsv")


# --- Tests ---


def test_single_option_per_slot_auto_selects():
    """When each slot has exactly one equipment, no CHOOSE_EQUIPMENT decision is presented."""
    db = _load_db()
    deck = parse_deck_list(DECK_ONE_PER_SLOT)
    p1 = EquipmentTrackingPlayer()
    p2 = EquipmentTrackingPlayer()
    game = Game(db, deck, deck, p1, p2, seed=42)

    # Run equipment selection directly
    selected = game._select_equipment(0, deck)

    # No decisions should have been asked (one option per slot)
    assert len(p1.equipment_decisions) == 0
    # All 4 equipment pieces should be selected
    assert len(selected) == 4
    assert "Crater Fist" in selected
    assert "Helm of Isen's Peak" in selected
    assert "Tectonic Plating" in selected
    assert "Ironrot Legs" in selected


def test_multi_option_slot_presents_decision():
    """When a slot has 2+ options, a CHOOSE_EQUIPMENT decision is presented."""
    db = _load_db()
    deck = parse_deck_list(DECK_MULTI_SLOT)
    p1 = EquipmentTrackingPlayer()
    p2 = RandomPlayer(seed=99)
    game = Game(db, deck, deck, p1, p2, seed=42)

    selected = game._select_equipment(0, deck)

    # Should have gotten decisions for chest (Tectonic Plating vs Nullrune Robe)
    # and legs (Ironrot Legs vs Nullrune Boots)
    assert len(p1.equipment_decisions) == 2

    # Check decision types and prompts
    for d in p1.equipment_decisions:
        assert d.decision_type == DecisionType.CHOOSE_EQUIPMENT
        assert d.player_index == 0
        assert d.min_selections == 1
        assert d.max_selections == 1

    # Check slot names in prompts
    prompts = [d.prompt for d in p1.equipment_decisions]
    assert any("chest" in p for p in prompts)
    assert any("legs" in p for p in prompts)

    # Head and arms should be auto-selected
    assert "Helm of Isen's Peak" in selected
    assert "Crater Fist" in selected
    assert len(selected) == 4  # one per slot


def test_player_can_choose_specific_equipment():
    """Player can choose which equipment to use for a contested slot."""
    db = _load_db()
    deck = parse_deck_list(DECK_MULTI_SLOT)

    # Player specifically chooses Nullrune Robe for chest and Nullrune Boots for legs
    p1 = EquipmentTrackingPlayer(choices={
        "chest": "Nullrune Robe",
        "legs": "Nullrune Boots",
    })
    p2 = RandomPlayer(seed=99)
    game = Game(db, deck, deck, p1, p2, seed=42)

    selected = game._select_equipment(0, deck)

    assert "Nullrune Robe" in selected
    assert "Nullrune Boots" in selected
    assert "Tectonic Plating" not in selected
    assert "Ironrot Legs" not in selected


def test_selected_equipment_used_in_player_state():
    """Equipment selection is wired into _setup_game — selected pieces end up in player state."""
    db = _load_db()
    deck = parse_deck_list(DECK_MULTI_SLOT)

    # Player 1 picks Nullrune Robe, Player 2 picks Tectonic Plating
    p1 = EquipmentTrackingPlayer(choices={"chest": "Nullrune Robe", "legs": "Nullrune Boots"})
    p2 = EquipmentTrackingPlayer(choices={"chest": "Tectonic Plating", "legs": "Ironrot Legs"})
    game = Game(db, deck, deck, p1, p2, seed=42)
    game.play()

    # Check player 1's chest equipment
    p1_chest = game.state.players[0].equipment.get(EquipmentSlot.CHEST)
    assert p1_chest is not None
    assert p1_chest.name == "Nullrune Robe"

    # Check player 2's chest equipment
    p2_chest = game.state.players[1].equipment.get(EquipmentSlot.CHEST)
    assert p2_chest is not None
    assert p2_chest.name == "Tectonic Plating"


def test_random_player_handles_choose_equipment():
    """RandomPlayer can handle CHOOSE_EQUIPMENT decisions without crashing."""
    db = _load_db()
    deck = parse_deck_list(DECK_MULTI_SLOT)
    p1 = RandomPlayer(seed=42)
    p2 = RandomPlayer(seed=99)
    game = Game(db, deck, deck, p1, p2, seed=7)

    # Should not crash — the key test is that the game completes
    result = game.play()
    assert result.turns > 0


def test_empty_equipment_pool():
    """A deck with no equipment still works."""
    db = _load_db()
    deck = parse_deck_list(DECK_ONE_PER_SLOT)
    deck_no_equip = DeckList(
        hero_name=deck.hero_name,
        weapons=deck.weapons,
        equipment=[],
        cards=deck.cards,
    )
    p1 = EquipmentTrackingPlayer()
    p2 = RandomPlayer(seed=99)
    game = Game(db, deck_no_equip, deck, p1, p2, seed=42)

    selected = game._select_equipment(0, deck_no_equip)
    assert selected == []
    assert len(p1.equipment_decisions) == 0


def test_decision_options_match_equipment_names():
    """Decision options have action_ids matching equip_{name} pattern."""
    db = _load_db()
    deck = parse_deck_list(DECK_MULTI_SLOT)
    p1 = EquipmentTrackingPlayer()
    p2 = RandomPlayer(seed=99)
    game = Game(db, deck, deck, p1, p2, seed=42)

    game._select_equipment(0, deck)

    for d in p1.equipment_decisions:
        for opt in d.options:
            assert opt.action_id.startswith("equip_")
            # The name after "equip_" should be a real equipment name
            name = opt.action_id[len("equip_"):]
            assert name in deck.equipment


def test_cindra_deck_equipment_selection():
    """Integration test: Cindra's real decklist has contested chest and legs slots."""
    db = _load_db()

    ref_dir = Path(__file__).parent.parent.parent / "ref"
    decklist_path = ref_dir / "decklist-cindra-blue.md"
    if not decklist_path.exists():
        return  # Skip if ref decklist not available

    # Import the markdown parser from integration tests
    from tests.integration.test_full_game import parse_markdown_decklist
    deck = parse_markdown_decklist(decklist_path.read_text())

    # Cindra has 2 chest (Blood Splattered Vest, Fyendal's Spring Tunic)
    # and 2 legs (Dragonscaler Flight Path, Tide Flippers)
    p1 = EquipmentTrackingPlayer(choices={
        "chest": "Blood Splattered Vest",
        "legs": "Tide Flippers",
    })
    p2 = RandomPlayer(seed=99)
    game = Game(db, deck, deck, p1, p2, seed=42)

    selected = game._select_equipment(0, deck)

    # Should get 2 decisions (chest and legs)
    assert len(p1.equipment_decisions) == 2

    # Check selections
    assert "Mask of Momentum" in selected  # head, auto
    assert "Flick Knives" in selected  # arms, auto
    assert "Blood Splattered Vest" in selected  # chest, chosen
    assert "Tide Flippers" in selected  # legs, chosen
    assert "Fyendal's Spring Tunic" not in selected
    assert "Dragonscaler Flight Path" not in selected


def test_each_player_gets_own_equipment_decision():
    """Both players independently choose their equipment."""
    db = _load_db()
    deck = parse_deck_list(DECK_MULTI_SLOT)

    p1 = EquipmentTrackingPlayer(choices={"chest": "Nullrune Robe"})
    p2 = EquipmentTrackingPlayer(choices={"chest": "Tectonic Plating"})
    game = Game(db, deck, deck, p1, p2, seed=42)

    # Run setup directly
    game._setup_game()

    # Both players should have been asked about equipment
    assert len(p1.equipment_decisions) == 2  # chest + legs
    assert len(p2.equipment_decisions) == 2  # chest + legs

    # Player 1 decisions should have player_index=0
    for d in p1.equipment_decisions:
        assert d.player_index == 0

    # Player 2 decisions should have player_index=1
    for d in p2.equipment_decisions:
        assert d.player_index == 1
