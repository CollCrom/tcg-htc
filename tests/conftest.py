"""Shared test fixtures and helpers."""

from pathlib import Path

from htc.cards.card import CardDefinition
from htc.cards.card_db import CardDatabase
from htc.cards.instance import CardInstance
from htc.decks.loader import parse_deck_list
from htc.engine.action_builder import ActionBuilder
from htc.engine.combat import CombatManager
from htc.engine.cost_manager import CostManager
from htc.engine.effects import EffectEngine
from htc.engine.events import EventBus
from htc.engine.game import Game, GameResult
from htc.engine.keyword_engine import KeywordEngine
from htc.engine.stack import StackManager
from htc.enums import CardType, SubType, Zone
from htc.player.random_player import RandomPlayer
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState

DATA_DIR = Path(__file__).parent.parent / "data"

WARRIOR_DECK = """\
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


def run_game(seed: int = 7, p1_seed: int = 42, p2_seed: int = 123) -> GameResult:
    """Run a complete game between two random players with warrior decks."""
    db = CardDatabase.load(DATA_DIR / "cards.csv")
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
    game.action_builder = ActionBuilder(game.effect_engine)
    game.cost_manager = CostManager(game.effect_engine, lambda d: game._ask(d))
    game.keyword_engine = KeywordEngine(
        game.effect_engine, game.events, lambda d: game._ask(d),
    )
    game._register_event_handlers()
    game.state.action_points = action_points or {0: 0, 1: 0}
    game.state.resource_points = resource_points or {0: 0, 1: 0}
    game.state.turn_player_index = 0
    return game
