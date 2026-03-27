"""Tests for equipment degradation: Battleworn, Blade Break, Temper."""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.game import Game
from htc.enums import CardType, EquipmentSlot, Keyword, SubType, Zone
from tests.conftest import make_card, make_game_shell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_equipment(
    instance_id: int = 50,
    name: str = "Test Armor",
    defense: int = 2,
    subtype: SubType = SubType.CHEST,
    keywords: frozenset = frozenset(),
    owner_index: int = 0,
) -> CardInstance:
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
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone(EquipmentSlot.CHEST.value),
    )




def _setup_defending_equipment(game: Game, equipment: CardInstance) -> None:
    """Set up a combat chain where equipment defended."""
    owner = game.state.players[equipment.owner_index]
    slot_map = {
        SubType.HEAD: EquipmentSlot.HEAD,
        SubType.CHEST: EquipmentSlot.CHEST,
        SubType.ARMS: EquipmentSlot.ARMS,
        SubType.LEGS: EquipmentSlot.LEGS,
    }
    for sub in equipment.definition.subtypes:
        if sub in slot_map:
            owner.equipment[slot_map[sub]] = equipment
            break

    attack = make_card(instance_id=1, power=5)
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, equipment.owner_index)
    game.combat_mgr.add_defender(game.state, link, equipment)


# ---------------------------------------------------------------------------
# Battleworn
# ---------------------------------------------------------------------------


def test_battleworn_loses_defense_counter():
    """Battleworn equipment should lose 1 defense counter after defending."""
    game = make_game_shell()
    eq = _make_equipment(defense=2, keywords=frozenset({Keyword.BATTLEWORN}))
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()

    assert eq.counters.get("defense", 0) == -1
    # Effective defense: base 2 + counter -1 = 1
    eff = game.effect_engine.get_modified_defense(game.state, eq)
    assert eff == 1


def test_battleworn_stacks_over_multiple_combats():
    """Multiple defenses should accumulate Battleworn counters."""
    game = make_game_shell()
    eq = _make_equipment(defense=3, keywords=frozenset({Keyword.BATTLEWORN}))

    # First combat
    _setup_defending_equipment(game, eq)
    game._apply_equipment_degradation()
    game.combat_mgr.close_chain(game.state)

    assert eq.counters["defense"] == -1
    assert game.effect_engine.get_modified_defense(game.state, eq) == 2

    # Second combat
    _setup_defending_equipment(game, eq)
    game._apply_equipment_degradation()

    assert eq.counters["defense"] == -2
    assert game.effect_engine.get_modified_defense(game.state, eq) == 1


def test_battleworn_defense_floors_at_zero():
    """Battleworn can reduce effective defense to 0 but not below (clamped by engine)."""
    game = make_game_shell()
    eq = _make_equipment(defense=1, keywords=frozenset({Keyword.BATTLEWORN}))
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()

    # base 1 + counter -1 = 0, clamped to 0
    eff = game.effect_engine.get_modified_defense(game.state, eq)
    assert eff == 0


# ---------------------------------------------------------------------------
# Blade Break
# ---------------------------------------------------------------------------


def test_blade_break_destroys_equipment():
    """Blade Break equipment should be destroyed after defending."""
    game = make_game_shell()
    eq = _make_equipment(defense=2, keywords=frozenset({Keyword.BLADE_BREAK}))
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()

    assert eq.zone == Zone.GRAVEYARD
    owner = game.state.players[eq.owner_index]
    assert owner.equipment[EquipmentSlot.CHEST] is None


def test_blade_break_skips_other_degradation():
    """If Blade Break destroys, Battleworn should not also apply."""
    game = make_game_shell()
    eq = _make_equipment(
        defense=2,
        keywords=frozenset({Keyword.BLADE_BREAK, Keyword.BATTLEWORN}),
    )
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()

    # Should be destroyed, not just worn
    assert eq.zone == Zone.GRAVEYARD
    # No defense counter should have been applied
    assert eq.counters.get("defense", 0) == 0


# ---------------------------------------------------------------------------
# Temper
# ---------------------------------------------------------------------------


def test_temper_loses_counter():
    """Temper equipment loses 1 defense counter per defend."""
    game = make_game_shell()
    eq = _make_equipment(defense=3, keywords=frozenset({Keyword.TEMPER}))
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()

    assert eq.counters["defense"] == -1
    assert game.effect_engine.get_modified_defense(game.state, eq) == 2


def test_temper_destroys_at_zero_defense():
    """Temper equipment is destroyed when effective defense reaches 0."""
    game = make_game_shell()
    eq = _make_equipment(defense=1, keywords=frozenset({Keyword.TEMPER}))
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()

    assert eq.zone == Zone.GRAVEYARD
    owner = game.state.players[eq.owner_index]
    assert owner.equipment[EquipmentSlot.CHEST] is None


def test_temper_progressive_destruction():
    """Temper equipment survives multiple defenses then breaks."""
    game = make_game_shell()
    eq = _make_equipment(defense=2, keywords=frozenset({Keyword.TEMPER}))

    # First combat: defense goes from 2 to 1
    _setup_defending_equipment(game, eq)
    game._apply_equipment_degradation()
    game.combat_mgr.close_chain(game.state)

    assert eq.zone != Zone.GRAVEYARD
    assert game.effect_engine.get_modified_defense(game.state, eq) == 1

    # Second combat: defense goes from 1 to 0 → destroyed
    _setup_defending_equipment(game, eq)
    game._apply_equipment_degradation()

    assert eq.zone == Zone.GRAVEYARD


# ---------------------------------------------------------------------------
# Non-equipment should not be affected
# ---------------------------------------------------------------------------


def test_non_equipment_not_degraded():
    """Regular hand cards used to defend should not be affected by degradation."""
    game = make_game_shell()
    card = make_card(instance_id=10, defense=3)

    attack = make_card(instance_id=1, power=5)
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 0)
    game.combat_mgr.add_defender(game.state, link, card)

    game._apply_equipment_degradation()

    # Card should be unaffected
    assert card.counters.get("defense", 0) == 0


# ---------------------------------------------------------------------------
# Close chain skips already-destroyed equipment
# ---------------------------------------------------------------------------


def test_close_chain_skips_destroyed_equipment():
    """Equipment destroyed by degradation should not be restored to slot."""
    game = make_game_shell()
    eq = _make_equipment(defense=1, keywords=frozenset({Keyword.BLADE_BREAK}))
    _setup_defending_equipment(game, eq)

    game._apply_equipment_degradation()
    assert eq.zone == Zone.GRAVEYARD

    game.combat_mgr.close_chain(game.state)
    # Should still be in graveyard, not restored
    assert eq.zone == Zone.GRAVEYARD
