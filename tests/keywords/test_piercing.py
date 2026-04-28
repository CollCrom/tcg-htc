"""Tests for Piercing N keyword (8.3).

Piercing N: If this is defended by an equipment, it gets +N power.
"""
from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.enums import CardType, Keyword, SubType, Zone
from tests.conftest import make_card, make_equipment, make_game_shell


def _make_piercing_attack(
    instance_id: int = 1, power: int = 5, piercing: int = 1
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"piercing-{instance_id}",
        name="Piercing Attack",
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
        keywords=frozenset({Keyword.PIERCING}),
        functional_text="",
        type_text="",
        keyword_values={Keyword.PIERCING: piercing},
    )
    return CardInstance(
        instance_id=instance_id, definition=defn, owner_index=0, zone=Zone.COMBAT_CHAIN,
    )


def test_piercing_adds_power_vs_equipment():
    """Piercing N adds +N power when defended by equipment."""
    game = make_game_shell()
    attack = _make_piercing_attack(power=5, piercing=1)
    equipment = make_equipment(defense=2, subtype=SubType.ARMS, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    game.combat_mgr.add_defender(game.state, link, equipment)

    game._apply_piercing(link)

    # After piercing, effective power should be 5 + 1 = 6
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 6


def test_piercing_no_equipment_no_bonus():
    """Piercing does NOT add power when defended only by non-equipment cards."""
    game = make_game_shell()
    attack = _make_piercing_attack(power=5, piercing=1)
    hand_card = make_card(instance_id=10, defense=3, owner_index=1, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    game.combat_mgr.add_defender(game.state, link, hand_card)

    game._apply_piercing(link)

    # No equipment defender, so no piercing bonus
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 5


def test_piercing_higher_value():
    """Piercing 3 adds +3 power when defended by equipment."""
    game = make_game_shell()
    attack = _make_piercing_attack(power=4, piercing=3)
    equipment = make_equipment(defense=2, subtype=SubType.ARMS, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    game.combat_mgr.add_defender(game.state, link, equipment)

    game._apply_piercing(link)

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 7  # 4 + 3


def test_piercing_with_mixed_defenders():
    """Piercing triggers if ANY defender is equipment, even if others aren't."""
    game = make_game_shell()
    attack = _make_piercing_attack(power=5, piercing=2)
    hand_card = make_card(instance_id=10, defense=3, owner_index=1, zone=Zone.COMBAT_CHAIN)
    equipment = make_equipment(defense=2, subtype=SubType.ARMS, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    game.combat_mgr.add_defender(game.state, link, hand_card)
    game.combat_mgr.add_defender(game.state, link, equipment)

    game._apply_piercing(link)

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 7  # 5 + 2


def test_no_piercing_no_bonus():
    """Attack without Piercing keyword is unaffected."""
    game = make_game_shell()
    attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)
    equipment = make_equipment(defense=2, subtype=SubType.ARMS, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    game.combat_mgr.add_defender(game.state, link, equipment)

    game._apply_piercing(link)

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 5  # no change


def test_piercing_no_defenders():
    """Piercing does nothing with no defenders."""
    game = make_game_shell()
    attack = _make_piercing_attack(power=5, piercing=1)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_piercing(link)

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 5
