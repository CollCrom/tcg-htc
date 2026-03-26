"""Tests for Phantasm keyword (8.3.11).

Phantasm: if defended by a non-Illusionist attack action card with 6+ power,
destroy the Phantasm attack.
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.combat import CombatManager
from htc.engine.effects import EffectEngine
from htc.engine.events import EventBus
from htc.engine.game import Game
from htc.engine.stack import StackManager
from htc.enums import CardType, Keyword, SubType, SuperType, Zone
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState
from tests.conftest import make_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game_shell() -> Game:
    game = Game.__new__(Game)
    game.state = GameState()
    game.state.players = [
        PlayerState(index=0, life_total=20),
        PlayerState(index=1, life_total=20),
    ]
    game.effect_engine = EffectEngine()
    game.events = EventBus()
    game.stack_mgr = StackManager()
    game.combat_mgr = CombatManager(game.effect_engine)
    game._register_event_handlers()
    game.state.action_points = {0: 0, 1: 0}
    game.state.resource_points = {0: 0, 1: 0}
    game.state.turn_player_index = 0
    return game


def _make_phantasm_attack(instance_id: int = 1, power: int = 5) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"phantasm-{instance_id}",
        name="Phantasm Attack",
        color=None,
        pitch=None,
        cost=1,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ILLUSIONIST}),
        keywords=frozenset({Keyword.PHANTASM}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id, definition=defn, owner_index=0, zone=Zone.COMBAT_CHAIN,
    )


def _make_defender(
    instance_id: int = 10,
    name: str = "Defender",
    power: int = 6,
    is_attack_action: bool = True,
    supertypes: frozenset = frozenset(),
) -> CardInstance:
    subtypes = frozenset({SubType.ATTACK}) if is_attack_action else frozenset()
    types = frozenset({CardType.ACTION})
    defn = CardDefinition(
        unique_id=f"def-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=0,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=types,
        subtypes=subtypes,
        supertypes=supertypes,
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id, definition=defn, owner_index=1, zone=Zone.COMBAT_CHAIN,
    )


def _setup_combat(game: Game, attack: CardInstance, defenders: list[CardInstance]) -> None:
    """Set up a combat chain with attack and defenders."""
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    for d in defenders:
        game.combat_mgr.add_defender(game.state, link, d)


# ---------------------------------------------------------------------------
# Phantasm triggers
# ---------------------------------------------------------------------------


def test_phantasm_triggered_by_non_illusionist_6_power():
    """Non-Illusionist attack action with 6+ power destroys Phantasm attack."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is True
    assert attack.zone == Zone.GRAVEYARD
    assert game.state.combat_chain.is_open is False


def test_phantasm_not_triggered_by_5_power():
    """Attack action with only 5 power does NOT trigger Phantasm."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=5)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False
    assert game.state.combat_chain.is_open is True


def test_phantasm_not_triggered_by_illusionist():
    """Illusionist attack action with 6+ power does NOT trigger Phantasm."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(
        power=7, supertypes=frozenset({SuperType.ILLUSIONIST}),
    )
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_not_triggered_by_non_attack_action():
    """Non-attack action card (even with 6+ power) does NOT trigger Phantasm."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=8, is_attack_action=False)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_not_triggered_without_keyword():
    """Attack without Phantasm keyword is not affected."""
    game = _make_game_shell()
    attack = make_card(instance_id=1, power=5)  # no Phantasm
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_triggered_by_any_qualifying_defender():
    """If ANY defender meets the criteria, Phantasm triggers."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    small_def = _make_defender(instance_id=10, name="Small", power=3)
    big_def = _make_defender(instance_id=11, name="Big", power=7)
    _setup_combat(game, attack, [small_def, big_def])

    result = game._check_phantasm()

    assert result is True
    assert attack.zone == Zone.GRAVEYARD


def test_phantasm_exact_6_power_triggers():
    """Exactly 6 power should trigger (>= 6, not > 6)."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is True


def test_phantasm_no_defenders():
    """No defenders means Phantasm doesn't trigger."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    _setup_combat(game, attack, [])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_defending_cards_cleaned_up():
    """When Phantasm triggers, defending cards should also be cleaned up by close_chain."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    game._check_phantasm()

    # Defender should be in graveyard (close_chain moves non-equipment defenders there)
    assert defender.zone == Zone.GRAVEYARD
    # Combat chain should be fully reset
    assert len(game.state.combat_chain.chain_links) == 0


def test_phantasm_equipment_does_not_trigger():
    """Equipment defense should not trigger Phantasm (not an attack action)."""
    game = _make_game_shell()
    attack = _make_phantasm_attack()

    eq_def = CardDefinition(
        unique_id="eq-1", name="Big Shield", color=None, pitch=None,
        cost=0, power=None, defense=6, health=None, intellect=None,
        arcane=None, types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.ARMS}), supertypes=frozenset(),
        keywords=frozenset(), functional_text="", type_text="",
    )
    eq = CardInstance(instance_id=50, definition=eq_def, owner_index=1, zone=Zone.COMBAT_CHAIN)
    _setup_combat(game, attack, [eq])

    result = game._check_phantasm()

    assert result is False
