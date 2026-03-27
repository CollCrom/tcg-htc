"""Tests for Rupture keyword infrastructure (8.3).

Rupture: If this is played at chain link 4 or higher, bonus effects apply.
This tests the infrastructure check; per-card bonus effects are Phase 5.
"""
from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.enums import CardType, Keyword, SubType, Zone
from tests.conftest import make_card, make_game_shell


def _make_rupture_attack(instance_id: int = 1, power: int = 4) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"rupture-{instance_id}",
        name="Rupture Attack",
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
        supertypes=frozenset(),
        keywords=frozenset({Keyword.RUPTURE}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id, definition=defn, owner_index=0, zone=Zone.COMBAT_CHAIN,
    )


def test_rupture_active_at_chain_link_4():
    """Rupture is active at chain link 4."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # Add 3 dummy links
    for i in range(3):
        dummy = make_card(instance_id=100 + i, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.add_chain_link(game.state, dummy, 1)

    # Add the rupture attack as link 4
    attack = _make_rupture_attack()
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    assert link.link_number == 4
    assert game._check_rupture_active(link) is True


def test_rupture_active_at_chain_link_5():
    """Rupture is active at chain link 5 (>= 4)."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    for i in range(4):
        dummy = make_card(instance_id=100 + i, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.add_chain_link(game.state, dummy, 1)

    attack = _make_rupture_attack()
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    assert link.link_number == 5
    assert game._check_rupture_active(link) is True


def test_rupture_not_active_at_chain_link_3():
    """Rupture is NOT active at chain link 3."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    for i in range(2):
        dummy = make_card(instance_id=100 + i, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.add_chain_link(game.state, dummy, 1)

    attack = _make_rupture_attack()
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    assert link.link_number == 3
    assert game._check_rupture_active(link) is False


def test_rupture_not_active_at_chain_link_1():
    """Rupture is NOT active at chain link 1."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    attack = _make_rupture_attack()
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    assert link.link_number == 1
    assert game._check_rupture_active(link) is False


def test_rupture_without_keyword():
    """Non-Rupture attack is never 'rupture active' even at link 4+."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    for i in range(3):
        dummy = make_card(instance_id=100 + i, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.add_chain_link(game.state, dummy, 1)

    normal_attack = make_card(instance_id=1, zone=Zone.COMBAT_CHAIN)
    link = game.combat_mgr.add_chain_link(game.state, normal_attack, 1)

    assert link.link_number == 4
    assert game._check_rupture_active(link) is False
