"""Tests for arcane damage and Arcane Barrier prevention."""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import PlayerResponse
from htc.engine.game import Game
from htc.enums import CardType, EquipmentSlot, Keyword, SubType, Zone
from tests.conftest import make_game_shell, make_pitch_card


def _make_arcane_weapon(
    instance_id: int = 100,
    name: str = "Test Staff",
    arcane: int = 2,
    cost: int | None = None,
    functional_text: str = "**Once per Turn Action** - {r}{r}: Deal 2 arcane damage to target hero.",
    keywords: frozenset = frozenset(),
    owner_index: int = 0,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"staff-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=arcane,
        types=frozenset({CardType.WEAPON}),
        subtypes=frozenset({SubType.STAFF, SubType.TWO_HAND}),
        supertypes=frozenset(),
        keywords=keywords,
        functional_text=functional_text,
        type_text="Weapon - Staff",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )


def _make_arcane_barrier_equipment(
    instance_id: int = 50,
    name: str = "Barrier Robe",
    barrier_value: int = 2,
    owner_index: int = 1,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"ab-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=0,
        power=None,
        defense=0,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.EQUIPMENT}),
        subtypes=frozenset({SubType.CHEST}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.ARCANE_BARRIER}),
        functional_text="",
        type_text="",
        keyword_values={Keyword.ARCANE_BARRIER: barrier_value},
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.CHEST,
    )



def _make_arcane_action(
    instance_id: int = 300,
    arcane: int = 3,
    cost: int = 1,
    owner_index: int = 0,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"arcane-action-{instance_id}",
        name="Aether Dart",
        color=None,
        pitch=None,
        cost=cost,
        power=None,
        defense=2,
        health=None,
        intellect=None,
        arcane=arcane,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="Deal 3 arcane damage to target hero.",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


# ---------------------------------------------------------------------------
# Arcane damage basics
# ---------------------------------------------------------------------------


def test_arcane_damage_reduces_life():
    """Arcane damage should reduce the target's life total."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    source = _make_arcane_weapon()

    game._deal_arcane_damage(source, 1, 3)

    assert game.state.players[1].life_total == 17


def test_arcane_damage_tracks_counters():
    """Arcane damage should update damage_taken, life_lost, damage_dealt."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    source = _make_arcane_weapon(owner_index=0)

    game._deal_arcane_damage(source, 1, 4)

    assert game.state.players[1].turn_counters.damage_taken == 4
    assert game.state.players[1].turn_counters.life_lost == 4
    assert game.state.players[0].turn_counters.damage_dealt == 4


def test_arcane_damage_checks_game_over():
    """Arcane damage killing a player should end the game."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    game.state.players[1].life_total = 3
    source = _make_arcane_weapon(owner_index=0)

    game._deal_arcane_damage(source, 1, 5)

    assert game.state.game_over is True
    assert game.state.winner == 0


def test_zero_arcane_damage_does_nothing():
    """Zero arcane damage should not emit events or change state."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    source = _make_arcane_weapon()

    game._deal_arcane_damage(source, 1, 0)

    assert game.state.players[1].life_total == 20


# ---------------------------------------------------------------------------
# Arcane Barrier prevention
# ---------------------------------------------------------------------------


def test_arcane_barrier_prevents_damage():
    """Player with Arcane Barrier who pays resources prevents arcane damage."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    # Player 1 has Arcane Barrier 2 equipment and resources
    eq = _make_arcane_barrier_equipment(barrier_value=2)
    game.state.players[1].equipment[EquipmentSlot.CHEST] = eq
    game.state.resource_points[1] = 2

    # Mock: choose to prevent 2 damage
    game._ask = lambda d: PlayerResponse(selected_option_ids=["barrier_2"])

    game._deal_arcane_damage(_make_arcane_weapon(), 1, 3)

    # 3 - 2 prevented = 1 damage
    assert game.state.players[1].life_total == 19
    assert game.state.resource_points[1] == 0


def test_arcane_barrier_full_prevention():
    """If barrier >= damage, all damage can be prevented."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    eq = _make_arcane_barrier_equipment(barrier_value=3)
    game.state.players[1].equipment[EquipmentSlot.CHEST] = eq
    game.state.resource_points[1] = 3

    game._ask = lambda d: PlayerResponse(selected_option_ids=["barrier_3"])

    game._deal_arcane_damage(_make_arcane_weapon(), 1, 3)

    assert game.state.players[1].life_total == 20


def test_arcane_barrier_decline():
    """Player who declines Arcane Barrier takes full damage."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    eq = _make_arcane_barrier_equipment(barrier_value=2)
    game.state.players[1].equipment[EquipmentSlot.CHEST] = eq
    game.state.resource_points[1] = 5

    game._ask = lambda d: PlayerResponse(selected_option_ids=["pass"])

    game._deal_arcane_damage(_make_arcane_weapon(), 1, 3)

    assert game.state.players[1].life_total == 17
    assert game.state.resource_points[1] == 5  # no resources spent


def test_arcane_barrier_no_equipment():
    """Without Arcane Barrier equipment, full damage is dealt."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    game._deal_arcane_damage(_make_arcane_weapon(), 1, 3)

    assert game.state.players[1].life_total == 17


def test_arcane_barrier_no_resources():
    """Arcane Barrier without resources to pay can't prevent anything."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    eq = _make_arcane_barrier_equipment(barrier_value=2)
    game.state.players[1].equipment[EquipmentSlot.CHEST] = eq
    # No resources and no hand cards
    game.state.resource_points[1] = 0

    game._deal_arcane_damage(_make_arcane_weapon(), 1, 3)

    assert game.state.players[1].life_total == 17


def test_arcane_barrier_with_pitching():
    """Player can pitch cards to pay for Arcane Barrier."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    eq = _make_arcane_barrier_equipment(barrier_value=2)
    game.state.players[1].equipment[EquipmentSlot.CHEST] = eq

    # Player 1 has a pitchable card but no floating resources
    pitch_card = make_pitch_card(instance_id=201, owner_index=1, pitch=3)
    game.state.players[1].hand = [pitch_card]

    # Mock: choose barrier_2, then pitch_201 for resources
    calls = iter([
        PlayerResponse(selected_option_ids=["barrier_2"]),
        PlayerResponse(selected_option_ids=["pitch_201"]),
    ])
    game._ask = lambda d: next(calls)

    game._deal_arcane_damage(_make_arcane_weapon(), 1, 3)

    # 3 - 2 prevented = 1 damage
    assert game.state.players[1].life_total == 19


# ---------------------------------------------------------------------------
# Arcane weapon activation
# ---------------------------------------------------------------------------


def test_arcane_weapon_deals_arcane_damage():
    """Activating an arcane weapon should deal arcane damage, not create attack proxy."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    staff = _make_arcane_weapon(arcane=2)
    game.state.players[0].weapons.append(staff)

    # Give player 0 resources to pay activation cost
    game.state.resource_points[0] = 2

    game._activate_weapon(0, staff)

    # No combat chain opened (arcane damage is direct)
    assert game.state.combat_chain.is_open is False
    # Stack should be empty (no proxy)
    assert game.stack_mgr.is_empty(game.state)
    # Damage dealt to opponent
    assert game.state.players[1].life_total == 18
    # Weapon tapped
    assert staff.is_tapped is True


def test_arcane_weapon_go_again():
    """Arcane weapon with Go Again should grant an action point."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    staff = _make_arcane_weapon(
        arcane=1,
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="**Once per Turn Action** - {r}{r}: Deal 1 arcane damage. **Go again**",
    )
    game.state.players[0].weapons.append(staff)
    game.state.resource_points[0] = 2

    # Activation costs 1 AP, but Go Again gives 1 back
    game._activate_weapon(0, staff)

    assert game.state.action_points[0] == 1


def test_arcane_weapon_activation_cost_from_text():
    """Weapon activation cost should be parsed from {r} tokens in functional text."""
    staff = _make_arcane_weapon(
        functional_text="**Once per Turn Action** - {r}{r}{r}: Deal 2 arcane damage.",
    )
    assert Game._weapon_activation_cost(staff) == 3


def test_arcane_weapon_activation_cost_from_field():
    """If cost field is set, use it instead of text parsing."""
    staff = _make_arcane_weapon(cost=5, functional_text="irrelevant")
    assert Game._weapon_activation_cost(staff) == 5


# ---------------------------------------------------------------------------
# Arcane action cards
# ---------------------------------------------------------------------------


def test_arcane_action_card_deals_damage_on_resolve():
    """Non-attack action card with arcane value should deal arcane damage when resolved."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    card = _make_arcane_action(arcane=3, cost=0)

    # Put card on stack and resolve
    layer = game.stack_mgr.add_card_layer(game.state, card, 0)
    game._resolve_stack()

    assert game.state.players[1].life_total == 17
    assert card.zone == Zone.GRAVEYARD


def test_arcane_action_card_with_barrier():
    """Arcane Barrier should apply when arcane action card resolves."""
    game = make_game_shell(action_points={0: 1, 1: 0})

    eq = _make_arcane_barrier_equipment(barrier_value=2)
    game.state.players[1].equipment[EquipmentSlot.CHEST] = eq
    game.state.resource_points[1] = 2

    game._ask = lambda d: PlayerResponse(selected_option_ids=["barrier_2"])

    card = _make_arcane_action(arcane=3, cost=0)
    layer = game.stack_mgr.add_card_layer(game.state, card, 0)
    game._resolve_stack()

    # 3 - 2 prevented = 1
    assert game.state.players[1].life_total == 19
