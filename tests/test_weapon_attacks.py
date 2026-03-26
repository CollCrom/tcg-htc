"""Tests for weapon attack activation (rules 1.4.3)."""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.combat import CombatManager
from htc.engine.effects import EffectEngine
from htc.engine.events import EventBus, EventType, GameEvent
from htc.engine.game import Game
from htc.engine.stack import StackManager
from htc.enums import CardType, Keyword, SubType, Zone
from htc.state.combat_state import CombatChainState
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState
from htc.state.turn_counters import TurnCounters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_weapon(
    instance_id: int = 100,
    name: str = "Test Dagger",
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
    keywords: frozenset = frozenset(),
) -> CardInstance:
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
        arcane=None,
        types=frozenset({CardType.WEAPON}),
        subtypes=frozenset({SubType.DAGGER, SubType.ONE_HAND}),
        supertypes=frozenset(),
        keywords=keywords,
        functional_text="Once per Turn Action -- Attack",
        type_text="Weapon - Dagger",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )


def _make_pitch_card(instance_id: int = 200, owner_index: int = 0, pitch: int = 3) -> CardInstance:
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


def _make_game_shell() -> Game:
    """Minimal Game for testing weapon activation."""
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
    game.state.action_points = {0: 1, 1: 0}
    game.state.resource_points = {0: 0, 1: 0}
    game.state.turn_player_index = 0
    return game


# ---------------------------------------------------------------------------
# Can-activate checks
# ---------------------------------------------------------------------------


def test_can_activate_untapped_weapon():
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    assert game._can_activate_weapon(0, weapon) is True


def test_cannot_activate_tapped_weapon():
    game = _make_game_shell()
    weapon = _make_weapon()
    weapon.is_tapped = True
    game.state.players[0].weapons.append(weapon)
    assert game._can_activate_weapon(0, weapon) is False


def test_cannot_activate_without_action_point():
    game = _make_game_shell()
    game.state.action_points[0] = 0
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    assert game._can_activate_weapon(0, weapon) is False


def test_cannot_activate_weapon_without_resources():
    game = _make_game_shell()
    weapon = _make_weapon(cost=2)
    game.state.players[0].weapons.append(weapon)
    # No resources and no cards to pitch
    assert game._can_activate_weapon(0, weapon) is False


def test_can_activate_weapon_with_pitchable_cards():
    game = _make_game_shell()
    weapon = _make_weapon(cost=2)
    game.state.players[0].weapons.append(weapon)
    game.state.players[0].hand.append(_make_pitch_card(pitch=3))
    assert game._can_activate_weapon(0, weapon) is True


# ---------------------------------------------------------------------------
# Attack proxy creation
# ---------------------------------------------------------------------------


def test_proxy_inherits_weapon_power():
    game = _make_game_shell()
    weapon = _make_weapon(power=5)
    proxy = game._create_attack_proxy(weapon, 0)

    assert proxy.is_proxy is True
    assert proxy.proxy_source_id == weapon.instance_id
    assert proxy.definition.power == 5
    assert proxy.definition.is_attack is True
    assert proxy.definition.is_action is True


def test_proxy_inherits_weapon_keywords():
    game = _make_game_shell()
    weapon = _make_weapon(keywords=frozenset({Keyword.GO_AGAIN}))
    proxy = game._create_attack_proxy(weapon, 0)

    assert Keyword.GO_AGAIN in proxy.definition.keywords


def test_proxy_is_not_sent_to_graveyard():
    """Proxies should be removed (not graveyarded) when combat chain closes."""
    game = _make_game_shell()
    weapon = _make_weapon(power=3)
    proxy = game._create_attack_proxy(weapon, 0)

    # Simulate proxy on combat chain
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, proxy, 1)

    # Close chain
    game.combat_mgr.close_chain(game.state)

    assert proxy.zone == Zone.REMOVED
    # Proxy should NOT be in any player's graveyard
    assert proxy not in game.state.players[0].graveyard
    assert proxy not in game.state.players[1].graveyard


# ---------------------------------------------------------------------------
# Weapon activation flow
# ---------------------------------------------------------------------------


def test_weapon_tapped_after_activation():
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)

    # Mock _ask to handle pitch decisions
    game.interfaces = [None, None]
    game._activate_weapon(0, weapon)

    assert weapon.is_tapped is True


def test_weapon_activation_consumes_action_point():
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    game._activate_weapon(0, weapon)

    assert game.state.action_points[0] == 0


def test_weapon_activation_puts_proxy_on_stack():
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    game._activate_weapon(0, weapon)

    assert not game.stack_mgr.is_empty(game.state)
    layer = game.stack_mgr.top(game.state)
    assert layer is not None
    assert layer.card is not None
    assert layer.card.is_proxy is True
    assert layer.card.proxy_source_id == weapon.instance_id


def test_weapon_activation_updates_counters():
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    game._activate_weapon(0, weapon)

    counters = game.state.players[0].turn_counters
    assert counters.num_attacks_played == 1
    assert counters.num_weapon_attacks == 1
    assert counters.has_attacked is True


def test_weapon_activation_opens_combat_chain():
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    assert game.state.combat_chain.is_open is False

    game._activate_weapon(0, weapon)

    assert game.state.combat_chain.is_open is True


def test_weapon_stays_in_weapon_zone():
    """After activation, weapon should still be in weapon zone (just tapped)."""
    game = _make_game_shell()
    weapon = _make_weapon()
    game.state.players[0].weapons.append(weapon)
    game._activate_weapon(0, weapon)

    assert weapon in game.state.players[0].weapons
    assert weapon.zone == Zone.WEAPON_1


def test_go_again_from_weapon():
    """Weapon with Go Again should set has_go_again on the stack layer."""
    game = _make_game_shell()
    weapon = _make_weapon(keywords=frozenset({Keyword.GO_AGAIN}))
    game.state.players[0].weapons.append(weapon)
    game._activate_weapon(0, weapon)

    layer = game.stack_mgr.top(game.state)
    assert layer is not None
    assert layer.has_go_again is True


# ---------------------------------------------------------------------------
# Integration: weapon attacks in full games
# ---------------------------------------------------------------------------


def test_full_game_with_weapons():
    """Warrior deck has Anothos; games should complete with weapon attacks."""
    from tests.conftest import run_game
    result = run_game(seed=42)
    assert result.winner is not None or result.turns >= 200
    assert result.turns > 0


def test_weapon_counter_resets_between_turns():
    """num_weapon_attacks should reset each turn."""
    counters = TurnCounters()
    counters.num_weapon_attacks = 2
    counters.reset()
    assert counters.num_weapon_attacks == 0
