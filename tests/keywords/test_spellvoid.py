"""Tests for Spellvoid N keyword (8.3).

Spellvoid N: If you would be dealt arcane damage, you may destroy this
to prevent N of that damage.
"""
from htc.engine.actions import ActionOption, PlayerResponse
from htc.enums import EquipmentSlot, Keyword, SubType, Zone
from tests.conftest import make_card, make_equipment, make_game_shell


def _mock_spellvoid_ask(use_spellvoid: bool = True):
    """Return response to use or decline Spellvoid."""
    def _ask(decision):
        if decision.prompt and "Spellvoid" in decision.prompt:
            if use_spellvoid:
                for opt in decision.options:
                    if opt.action_id.startswith("spellvoid_"):
                        return PlayerResponse(selected_option_ids=[opt.action_id])
            return PlayerResponse(selected_option_ids=["pass"])
        return PlayerResponse(selected_option_ids=["pass"])
    return _ask


def test_spellvoid_prevents_arcane_damage():
    """Spellvoid destroys equipment to prevent arcane damage."""
    game = make_game_shell()
    state = game.state

    eq = make_equipment(
        name="Nullrune Hood", defense=1, subtype=SubType.HEAD,
        keywords=frozenset({Keyword.SPELLVOID}),
        keyword_values={Keyword.SPELLVOID: 3},
    )
    state.players[1].equipment[EquipmentSlot.HEAD] = eq

    game._ask = _mock_spellvoid_ask(use_spellvoid=True)

    source = make_card(instance_id=1, owner_index=0)
    remaining = game._apply_spellvoid(1, 3)

    # Should prevent all 3 damage
    assert remaining == 0
    # Equipment should be destroyed
    assert state.players[1].equipment[EquipmentSlot.HEAD] is None
    assert eq.zone == Zone.GRAVEYARD


def test_spellvoid_partial_prevention():
    """Spellvoid prevents up to N damage, rest goes through."""
    game = make_game_shell()
    state = game.state

    eq = make_equipment(
        name="Nullrune Hood", defense=1, subtype=SubType.HEAD,
        keywords=frozenset({Keyword.SPELLVOID}),
        keyword_values={Keyword.SPELLVOID: 2},
    )
    state.players[1].equipment[EquipmentSlot.HEAD] = eq

    game._ask = _mock_spellvoid_ask(use_spellvoid=True)

    remaining = game._apply_spellvoid(1, 5)

    # Should prevent 2 of 5
    assert remaining == 3
    assert eq.zone == Zone.GRAVEYARD


def test_spellvoid_declined():
    """Player can decline to use Spellvoid."""
    game = make_game_shell()
    state = game.state

    eq = make_equipment(
        name="Nullrune Hood", defense=1, subtype=SubType.HEAD,
        keywords=frozenset({Keyword.SPELLVOID}),
        keyword_values={Keyword.SPELLVOID: 3},
    )
    state.players[1].equipment[EquipmentSlot.HEAD] = eq

    game._ask = _mock_spellvoid_ask(use_spellvoid=False)

    remaining = game._apply_spellvoid(1, 3)

    # Damage not prevented
    assert remaining == 3
    # Equipment still exists
    assert state.players[1].equipment[EquipmentSlot.HEAD] is eq
    assert eq.zone == Zone.HEAD


def test_spellvoid_no_equipment():
    """No Spellvoid equipment means no prevention."""
    game = make_game_shell()

    remaining = game._apply_spellvoid(1, 5)
    assert remaining == 5


def test_spellvoid_zero_damage():
    """Spellvoid with 0 damage does nothing."""
    game = make_game_shell()
    state = game.state

    eq = make_equipment(
        name="Nullrune Hood", defense=1, subtype=SubType.HEAD,
        keywords=frozenset({Keyword.SPELLVOID}),
        keyword_values={Keyword.SPELLVOID: 3},
    )
    state.players[1].equipment[EquipmentSlot.HEAD] = eq

    remaining = game._apply_spellvoid(1, 0)
    assert remaining == 0
    # Equipment not destroyed
    assert state.players[1].equipment[EquipmentSlot.HEAD] is eq
