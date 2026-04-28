"""Shared test fixtures and helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from engine.cards.card import CardDefinition
from engine.cards.card_db import CardDatabase
from engine.cards.instance import CardInstance
from engine.decks.loader import parse_deck_list
from engine.rules.action_builder import ActionBuilder
from engine.rules.actions import PlayerResponse
from engine.rules.combat import CombatManager
from engine.rules.cost_manager import CostManager
from engine.rules.effects import EffectEngine
from engine.rules.events import EventBus
from engine.rules.abilities import AbilityRegistry
from engine.rules.game import Game, GameResult
from engine.rules.keyword_engine import KeywordEngine
from engine.rules.stack import StackManager
from engine.enums import CardType, EquipmentSlot, SubType, Zone
from engine.player.random_player import RandomPlayer
from engine.state.game_state import GameState
from engine._demo_deck import BRAVO_DECK_TEXT
from engine.state.player_state import PlayerState

# Shared filesystem layout — every test file imports from here rather than
# recomputing its own Path(__file__) chain.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
REF_DIR = REPO_ROOT / "ref"
CARDS_TSV = DATA_DIR / "cards.tsv"

# Backwards-compatible alias for the demo deck.
WARRIOR_DECK = BRAVO_DECK_TEXT


def run_game(seed: int = 7, p1_seed: int = 42, p2_seed: int = 123) -> GameResult:
    """Run a complete game between two random players with warrior decks."""
    db = CardDatabase.load(CARDS_TSV)
    deck1 = parse_deck_list(WARRIOR_DECK)
    deck2 = parse_deck_list(WARRIOR_DECK)
    p1 = RandomPlayer(seed=p1_seed)
    p2 = RandomPlayer(seed=p2_seed)
    game = Game(db, deck1, deck2, p1, p2, seed=seed)
    return game.play()


def make_card(
    instance_id: int = 1,
    name: str = "Test Card",
    *,
    power: int | None = 3,
    defense: int | None = 2,
    cost: int | None = 1,
    is_attack: bool = True,
    keywords: frozenset = frozenset(),
    zone: Zone = Zone.HAND,
    owner_index: int = 0,
) -> CardInstance:
    """Create a CardInstance with sensible defaults for testing."""
    subtypes = frozenset({SubType.ATTACK}) if is_attack else frozenset()
    defn = CardDefinition(
        unique_id=f"test-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=power,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=subtypes,
        supertypes=frozenset(),
        keywords=keywords,
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def make_pitch_card(
    instance_id: int = 200,
    owner_index: int = 0,
    pitch: int = 3,
) -> CardInstance:
    """Create a pitchable card for testing resource payment."""
    defn = CardDefinition(
        unique_id=f"pitch-{instance_id}",
        name="Pitch Fodder",
        color=None,
        pitch=pitch,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


# Maps equipment subtypes to their canonical zones
_SLOT_ZONE: dict[SubType, Zone] = {
    SubType.HEAD: Zone.HEAD,
    SubType.CHEST: Zone.CHEST,
    SubType.ARMS: Zone.ARMS,
    SubType.LEGS: Zone.LEGS,
}


def make_equipment(
    instance_id: int = 50,
    name: str = "Test Equipment",
    *,
    defense: int = 2,
    subtype: SubType = SubType.CHEST,
    keywords: frozenset = frozenset(),
    keyword_values: dict | None = None,
    owner_index: int = 1,
    zone: Zone | None = None,
) -> CardInstance:
    """Create an equipment CardInstance with sensible defaults for testing.

    If *zone* is not specified, it is inferred from *subtype* (e.g.
    SubType.HEAD → Zone.HEAD).  Pass *zone* explicitly to override
    (e.g. Zone.COMBAT_CHAIN for defending equipment).
    """
    if zone is None:
        zone = _SLOT_ZONE.get(subtype, Zone.CHEST)
    defn = CardDefinition(
        unique_id=f"eq-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=0,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({subtype}),
        supertypes=frozenset(),
        keywords=keywords,
        functional_text="",
        type_text="",
        keyword_values=keyword_values or {},
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def make_weapon(
    instance_id: int = 100,
    name: str = "Test Staff",
    *,
    power: int | None = None,
    arcane: int | None = None,
    cost: int | None = None,
    subtypes: frozenset | None = None,
    keywords: frozenset = frozenset(),
    functional_text: str = "",
    type_text: str = "",
    owner_index: int = 0,
    zone: Zone = Zone.WEAPON_1,
) -> CardInstance:
    """Create a weapon CardInstance with sensible defaults for testing."""
    if subtypes is None:
        subtypes = frozenset({SubType.STAFF, SubType.TWO_HAND})
    defn = CardDefinition(
        unique_id=f"weapon-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=power,
        defense=None,
        health=None,
        intellect=None,
        arcane=arcane,
        types=frozenset({CardType.WEAPON}),
        subtypes=subtypes,
        supertypes=frozenset(),
        keywords=keywords,
        functional_text=functional_text,
        type_text=type_text,
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def make_state(life: int = 20) -> GameState:
    """Create a minimal GameState with two players."""
    state = GameState()
    state.players = [
        PlayerState(index=0, life_total=life),
        PlayerState(index=1, life_total=life),
    ]
    return state


def make_game_shell(
    *,
    action_points: dict[int, int] | None = None,
    resource_points: dict[int, int] | None = None,
    life: int = 20,
) -> Game:
    """Create a minimal Game object for unit-testing internal methods."""
    game = Game.__new__(Game)
    game.state = make_state(life=life)
    game.effect_engine = EffectEngine()
    game.events = EventBus()
    game.stack_mgr = StackManager()
    game.combat_mgr = CombatManager(game.effect_engine)
    game.cost_manager = CostManager(game.effect_engine, lambda d: game._ask(d), game.events)
    game.keyword_engine = KeywordEngine(
        game.effect_engine, game.events, lambda d: game._ask(d),
    )
    game.ability_registry = AbilityRegistry()
    game._register_abilities()
    game.action_builder = ActionBuilder(game.effect_engine, game.ability_registry)
    game._register_event_handlers()
    game._banish_instead_of_graveyard = set()
    game.state.action_points = action_points or {0: 0, 1: 0}
    game.state.resource_points = resource_points or {0: 0, 1: 0}
    game.state.turn_player_index = 0
    return game


# ---------------------------------------------------------------------------
# Mock ask callback factories
# ---------------------------------------------------------------------------


def make_mock_ask(
    prompt_responses: dict[str, list[str]],
) -> Callable:
    """Create a mock ask callback that maps prompt keywords to option IDs.

    *prompt_responses* maps a substring to look for in ``decision.prompt``
    to a list of ``selected_option_ids`` to return when that substring is
    found.  An empty list means return ``["pass"]``.  If no prompt keyword
    matches, ``["pass"]`` is returned.

    Example::

        ask = make_mock_ask({"Opt": ["opt_bottom_1", "opt_bottom_2"]})
    """
    def _ask(decision):
        if decision.prompt:
            for keyword, option_ids in prompt_responses.items():
                if keyword in decision.prompt:
                    ids = option_ids if option_ids else ["pass"]
                    return PlayerResponse(selected_option_ids=ids)
        return PlayerResponse(selected_option_ids=["pass"])
    return _ask


def make_mock_ask_once(first_response: PlayerResponse) -> Callable:
    """Create a mock ask callback that returns *first_response* once, then always passes.

    Useful for tests that need a specific defend or action response on the
    first decision, then want all subsequent decisions to pass.
    """
    called = [False]

    def _ask(decision):
        if not called[0]:
            called[0] = True
            return first_response
        return PlayerResponse(selected_option_ids=["pass"])

    return _ask
