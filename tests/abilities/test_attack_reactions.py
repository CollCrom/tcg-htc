"""Tests for attack reaction ability effects.

Covers Ancestral Empowerment and Razor Reflex.
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.abilities import AbilityContext
from htc.engine.actions import PlayerResponse
from htc.enums import (
    CardType,
    Color,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_game_shell


def _make_ninja_attack(
    instance_id: int = 1,
    power: int = 4,
    cost: int = 1,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Ninja attack action card for testing."""
    defn = CardDefinition(
        unique_id=f"ninja-{instance_id}",
        name="Ninja Strike",
        color=Color.RED,
        pitch=1,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.NINJA}),
        keywords=frozenset(),
        functional_text="",
        type_text="Ninja Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def _make_attack_reaction(
    name: str = "Ancestral Empowerment",
    instance_id: int = 10,
    color: Color = Color.RED,
    defense: int = 3,
    owner_index: int = 0,
    cost: int = 0,
    supertypes: frozenset | None = None,
) -> CardInstance:
    """Create an attack reaction card for testing."""
    if supertypes is None:
        supertypes = frozenset()
    defn = CardDefinition(
        unique_id=f"ar-{instance_id}",
        name=name,
        color=color,
        pitch=1,
        cost=cost,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ATTACK_REACTION}),
        subtypes=frozenset(),
        supertypes=supertypes,
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


# ---------------------------------------------------------------------------
# Ancestral Empowerment
# ---------------------------------------------------------------------------


def test_ancestral_empowerment_gives_plus_one_power():
    """Ancestral Empowerment gives +1 power to a Ninja attack action card."""
    game = make_game_shell()
    attack = _make_ninja_attack(instance_id=1, power=4)

    # Set up combat chain with the attack
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Give the player a deck card so draw works
    deck_card = make_card(instance_id=99, owner_index=0, zone=Zone.DECK)
    game.state.players[0].deck.append(deck_card)

    # Apply ability
    ae_card = _make_attack_reaction("Ancestral Empowerment", instance_id=10)
    game._apply_card_ability(ae_card, 0, "attack_reaction_effect")

    # Attack should now have +1 power (4 + 1 = 5)
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 5


def test_ancestral_empowerment_draws_card():
    """Ancestral Empowerment draws a card after granting +1 power."""
    game = make_game_shell()
    attack = _make_ninja_attack(instance_id=1, power=4)

    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Put a card in the deck
    deck_card = make_card(instance_id=99, owner_index=0, zone=Zone.DECK)
    game.state.players[0].deck.append(deck_card)

    ae_card = _make_attack_reaction("Ancestral Empowerment", instance_id=10)
    game._apply_card_ability(ae_card, 0, "attack_reaction_effect")

    # Player should have drawn the card
    assert deck_card in game.state.players[0].hand
    assert deck_card not in game.state.players[0].deck


def test_ancestral_empowerment_no_effect_on_non_ninja():
    """Ancestral Empowerment does nothing if the attack is not a Ninja card."""
    game = make_game_shell()
    # Generic attack (not Ninja)
    attack = make_card(instance_id=1, power=4, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    ae_card = _make_attack_reaction("Ancestral Empowerment", instance_id=10)
    game._apply_card_ability(ae_card, 0, "attack_reaction_effect")

    # Power should be unchanged
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4


# ---------------------------------------------------------------------------
# Razor Reflex
# ---------------------------------------------------------------------------


def test_razor_reflex_mode2_gives_power_and_go_again_on_hit():
    """Razor Reflex mode 2 gives +N power immediately, and go again on hit."""
    from htc.engine.events import EventType, GameEvent

    game = make_game_shell()
    # Attack action with cost 1 (eligible for mode 2)
    attack = _make_ninja_attack(instance_id=1, power=3, cost=1)

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    rr_card = _make_attack_reaction(
        "Razor Reflex", instance_id=10, color=Color.RED, cost=1,
    )
    game._apply_card_ability(rr_card, 0, "attack_reaction_effect")

    # Red Razor Reflex = +3 power (immediate)
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 6  # 3 + 3

    # Go Again should NOT be present yet (it's granted on hit, not immediately)
    modified_kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in modified_kws

    # Simulate a hit event — this should trigger the on-hit Go Again grant
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=6,
        data={"chain_link": link},
    ))
    # Process the pending triggers (in a real game, _process_pending_triggers
    # does this; here we call it manually or process inline)
    game._process_pending_triggers()

    # Now Go Again should be granted
    modified_kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in modified_kws


def test_razor_reflex_yellow_gives_plus_two():
    """Yellow Razor Reflex gives +2 power."""
    game = make_game_shell()
    attack = _make_ninja_attack(instance_id=1, power=3, cost=0)

    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    rr_card = _make_attack_reaction(
        "Razor Reflex", instance_id=10, color=Color.YELLOW, cost=1,
    )
    game._apply_card_ability(rr_card, 0, "attack_reaction_effect")

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 5  # 3 + 2


def test_razor_reflex_no_effect_on_expensive_non_weapon():
    """Razor Reflex does nothing if attack is not a weapon and cost > 1."""
    game = make_game_shell()
    # Attack action with cost 2 (not eligible for mode 2, not a weapon)
    attack = _make_ninja_attack(instance_id=1, power=3, cost=2)

    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    rr_card = _make_attack_reaction(
        "Razor Reflex", instance_id=10, color=Color.RED, cost=1,
    )
    game._apply_card_ability(rr_card, 0, "attack_reaction_effect")

    # Power should be unchanged — neither mode is valid
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 3


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_attack_reaction_no_ability_does_nothing():
    """An attack reaction with no registered ability does nothing."""
    game = make_game_shell()
    attack = make_card(instance_id=1, power=4, zone=Zone.COMBAT_CHAIN)

    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Unknown card — no ability registered
    unknown_card = _make_attack_reaction(
        "Unknown Reaction", instance_id=10,
    )
    game._apply_card_ability(unknown_card, 0, "attack_reaction_effect")

    # Power should be unchanged
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4
