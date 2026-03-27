"""Tests for Phantasm keyword (8.3.11).

Phantasm: if defended by a non-Illusionist attack action card with 6+ power,
destroy the Phantasm attack.
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.continuous import make_power_modifier
from htc.engine.game import Game
from htc.enums import CardType, Keyword, SubType, SuperType, Zone
from tests.conftest import make_card, make_equipment, make_game_shell


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
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is True
    assert attack.zone == Zone.GRAVEYARD
    assert game.state.combat_chain.is_open is False


def test_phantasm_not_triggered_by_5_power():
    """Attack action with only 5 power does NOT trigger Phantasm."""
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=5)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False
    assert game.state.combat_chain.is_open is True


def test_phantasm_not_triggered_by_illusionist():
    """Illusionist attack action with 6+ power does NOT trigger Phantasm."""
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(
        power=7, supertypes=frozenset({SuperType.ILLUSIONIST}),
    )
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_not_triggered_by_non_attack_action():
    """Non-attack action card (even with 6+ power) does NOT trigger Phantasm."""
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=8, is_attack_action=False)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_not_triggered_without_keyword():
    """Attack without Phantasm keyword is not affected."""
    game = make_game_shell()
    attack = make_card(instance_id=1, power=5)  # no Phantasm
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_triggered_by_any_qualifying_defender():
    """If ANY defender meets the criteria, Phantasm triggers."""
    game = make_game_shell()
    attack = _make_phantasm_attack()
    small_def = _make_defender(instance_id=10, name="Small", power=3)
    big_def = _make_defender(instance_id=11, name="Big", power=7)
    _setup_combat(game, attack, [small_def, big_def])

    result = game._check_phantasm()

    assert result is True
    assert attack.zone == Zone.GRAVEYARD


def test_phantasm_exact_6_power_triggers():
    """Exactly 6 power should trigger (>= 6, not > 6)."""
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=6)
    _setup_combat(game, attack, [defender])

    result = game._check_phantasm()

    assert result is True


def test_phantasm_no_defenders():
    """No defenders means Phantasm doesn't trigger."""
    game = make_game_shell()
    attack = _make_phantasm_attack()
    _setup_combat(game, attack, [])

    result = game._check_phantasm()

    assert result is False


def test_phantasm_defending_cards_cleaned_up():
    """When Phantasm triggers, defending cards should also be cleaned up by close_chain."""
    game = make_game_shell()
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
    game = make_game_shell()
    attack = _make_phantasm_attack()

    eq = make_equipment(
        instance_id=50, name="Big Shield", defense=6,
        subtype=SubType.ARMS, zone=Zone.COMBAT_CHAIN,
    )
    _setup_combat(game, attack, [eq])

    result = game._check_phantasm()

    assert result is False


# ---------------------------------------------------------------------------
# Phantasm uses modified power (continuous effects)
# ---------------------------------------------------------------------------


def test_phantasm_not_triggered_when_power_reduced_below_6():
    """Defender has 7 base power, but a continuous effect reduces it below 6.

    Phantasm checks get_modified_power(), so the -2 modifier should bring the
    effective power to 5, and Phantasm should NOT trigger.
    """
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=7)
    _setup_combat(game, attack, [defender])

    # Add a continuous effect that reduces power by 2 (7 - 2 = 5, below 6)
    effect = make_power_modifier(-2, controller_index=0)
    game.effect_engine.add_continuous_effect(game.state, effect)

    # Sanity check: modified power should be 5
    assert game.effect_engine.get_modified_power(game.state, defender) == 5

    result = game._check_phantasm()

    assert result is False
    assert game.state.combat_chain.is_open is True


def test_phantasm_triggered_when_power_boosted_to_6():
    """Defender has 5 base power, but a continuous effect boosts it to 6+.

    Phantasm checks get_modified_power(), so the +1 modifier should bring the
    effective power to 6, and Phantasm SHOULD trigger.
    """
    game = make_game_shell()
    attack = _make_phantasm_attack()
    defender = _make_defender(power=5)
    _setup_combat(game, attack, [defender])

    # Add a continuous effect that boosts power by 1 (5 + 1 = 6, meets threshold)
    effect = make_power_modifier(1, controller_index=0)
    game.effect_engine.add_continuous_effect(game.state, effect)

    # Sanity check: modified power should be 6
    assert game.effect_engine.get_modified_power(game.state, defender) == 6

    result = game._check_phantasm()

    assert result is True
    assert attack.zone == Zone.GRAVEYARD
    assert game.state.combat_chain.is_open is False
