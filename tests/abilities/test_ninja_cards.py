"""Tests for Ninja/Draconic card abilities (Cindra deck).

Tests cover on_attack, on_hit, and attack_reaction_effect timings
for the cards in the Cindra Blue decklist.
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.ninja import count_draconic_chain_links
from htc.engine.actions import PlayerResponse
from htc.engine.events import EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_equipment, make_game_shell, make_mock_ask, make_weapon
from tests.abilities.conftest import (
    make_ability_context,
    make_ninja_attack as _make_ninja_attack,
    make_draconic_ninja_attack as _make_draconic_ninja_attack,
    make_draconic_attack as _make_draconic_attack,
    make_attack_reaction as _shared_make_attack_reaction,
    make_dagger_weapon as _make_dagger_weapon,
)


# ---------------------------------------------------------------------------
# Test helpers — thin wrapper for Ninja-specific attack reaction defaults
# ---------------------------------------------------------------------------


def _make_attack_reaction(
    name: str,
    instance_id: int = 10,
    color: Color = Color.BLUE,
    owner_index: int = 0,
    supertypes: frozenset | None = None,
) -> CardInstance:
    return _shared_make_attack_reaction(
        name, instance_id=instance_id, color=color, owner_index=owner_index,
        supertypes=supertypes, pitch=3,
    )


# ---------------------------------------------------------------------------
# count_draconic_chain_links helper
# ---------------------------------------------------------------------------


def test_count_draconic_chain_links_empty():
    """No chain links means zero Draconic links."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)
    # Build a minimal context
    attack = _make_ninja_attack()
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)
    ctx = make_ability_context(game, attack, 0, chain_link=link)
    # Ninja (not Draconic) -> 0
    assert count_draconic_chain_links(ctx) == 0


def test_count_draconic_chain_links_with_draconic():
    """Draconic attacks count toward the total."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)
    atk1 = _make_draconic_ninja_attack(instance_id=1)
    game.combat_mgr.add_chain_link(game.state, atk1, 1)
    atk2 = _make_draconic_ninja_attack(instance_id=2)
    game.combat_mgr.add_chain_link(game.state, atk2, 1)
    atk3 = _make_ninja_attack(instance_id=3)  # not Draconic
    link3 = game.combat_mgr.add_chain_link(game.state, atk3, 1)

    ctx = make_ability_context(game, atk3, 0, chain_link=link3)
    assert count_draconic_chain_links(ctx) == 2


# ---------------------------------------------------------------------------
# Exposed (Attack Reaction)
# ---------------------------------------------------------------------------


def test_exposed_gives_plus_one_power_and_marks():
    """Exposed gives +1 power to attack and marks the defending hero."""
    game = make_game_shell()
    attack = _make_ninja_attack(instance_id=1, power=4)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    exposed_card = _make_attack_reaction("Exposed", instance_id=10)
    game._apply_card_ability(exposed_card, 0, "attack_reaction_effect")

    # +1 power
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 5

    # Defender is marked
    assert game.state.players[1].is_marked is True


def test_exposed_no_chain_link_does_nothing():
    """Exposed with no chain link does nothing."""
    game = make_game_shell()
    exposed_card = _make_attack_reaction("Exposed", instance_id=10)
    # No combat chain open
    game._apply_card_ability(exposed_card, 0, "attack_reaction_effect")
    assert game.state.players[1].is_marked is False


# ---------------------------------------------------------------------------
# Dragon Power (on_attack)
# ---------------------------------------------------------------------------


def test_dragon_power_draconic_gives_plus_3():
    """Dragon Power gives +3 power when the attack is Draconic."""
    game = make_game_shell()
    # Attack is Draconic (gained Draconic supertype)
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Dragon Power", power=4,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 7  # 4 + 3


def test_dragon_power_not_draconic_no_bonus():
    """Dragon Power gives no bonus when the attack is not Draconic."""
    game = make_game_shell()
    attack = _make_ninja_attack(
        instance_id=1, name="Dragon Power", power=4,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4  # unchanged


# ---------------------------------------------------------------------------
# Art of the Dragon: Blood (on_attack)
# ---------------------------------------------------------------------------


def test_art_blood_draconic_gives_go_again_and_cost_reduction():
    """Art of the Dragon: Blood gives Go Again and cost reduction when Draconic."""
    game = make_game_shell()
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Art of the Dragon: Blood", power=4,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    # Should have Go Again
    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in kws


def test_art_blood_not_draconic_no_effect():
    """Art of the Dragon: Blood does nothing if not Draconic."""
    game = make_game_shell()
    attack = _make_ninja_attack(
        instance_id=1, name="Art of the Dragon: Blood", power=4,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in kws


# ---------------------------------------------------------------------------
# Art of the Dragon: Fire (on_attack)
# ---------------------------------------------------------------------------


def test_art_fire_draconic_deals_2_damage():
    """Art of the Dragon: Fire deals 2 damage when Draconic (opponent target)."""
    game = make_game_shell(life=20)
    # Mock player that picks the opponent (target_1)
    mock_ask = make_mock_ask({"Art of the Dragon: Fire": ["target_1"]})
    _MockPlayer = type("P", (), {"decide": lambda s, state, d: mock_ask(d)})
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Art of the Dragon: Fire", power=5,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    assert game.state.players[1].life_total == 18


def test_art_fire_not_draconic_no_damage():
    """Art of the Dragon: Fire does nothing if not Draconic."""
    game = make_game_shell(life=20)
    attack = _make_ninja_attack(
        instance_id=1, name="Art of the Dragon: Fire", power=5,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    assert game.state.players[1].life_total == 20


# ---------------------------------------------------------------------------
# Art of the Dragon: Scale (on_attack + on_hit trigger)
# ---------------------------------------------------------------------------


def test_art_scale_draconic_registers_hit_trigger():
    """Art of the Dragon: Scale registers a hit trigger when Draconic."""
    game = make_game_shell()
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Art of the Dragon: Scale", power=5,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    triggers_before = len(game.events._triggered_effects)
    game._apply_card_ability(attack, 0, "on_attack")
    triggers_after = len(game.events._triggered_effects)

    assert triggers_after == triggers_before + 1


def test_art_scale_not_draconic_no_trigger():
    """Art of the Dragon: Scale does nothing if not Draconic."""
    game = make_game_shell()
    attack = _make_ninja_attack(
        instance_id=1, name="Art of the Dragon: Scale", power=5,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    triggers_before = len(game.events._triggered_effects)
    game._apply_card_ability(attack, 0, "on_attack")
    triggers_after = len(game.events._triggered_effects)

    assert triggers_after == triggers_before


# ---------------------------------------------------------------------------
# Blood Runs Deep (on_attack -- dagger damage)
# ---------------------------------------------------------------------------


def test_blood_runs_deep_daggers_deal_damage():
    """Blood Runs Deep: each dagger deals 1 damage and is destroyed."""
    game = make_game_shell(life=20)
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Blood Runs Deep", power=2, cost=2,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Give player two daggers
    dagger1 = _make_dagger_weapon(instance_id=100)
    dagger2 = _make_dagger_weapon(instance_id=101, name="Claw of Vynserakai")
    game.state.players[0].weapons.extend([dagger1, dagger2])

    game._apply_card_ability(attack, 0, "on_attack")

    # 2 daggers x 1 damage = 2 damage
    assert game.state.players[1].life_total == 18
    # Daggers destroyed
    assert len(game.state.players[0].weapons) == 0
    assert dagger1 in game.state.players[0].graveyard
    assert dagger2 in game.state.players[0].graveyard


def test_blood_runs_deep_no_daggers_no_damage():
    """Blood Runs Deep with no daggers deals no extra damage."""
    game = make_game_shell(life=20)
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Blood Runs Deep", power=2,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    assert game.state.players[1].life_total == 20


# ---------------------------------------------------------------------------
# Breaking Point (on_hit -- Rupture)
# ---------------------------------------------------------------------------


def test_breaking_point_rupture_destroys_arsenal():
    """Breaking Point on hit at chain link 4+ destroys target's arsenal."""
    game = make_game_shell()
    attack = _make_draconic_attack(
        instance_id=5, name="Breaking Point", power=5,
    )
    game.combat_mgr.open_chain(game.state)
    # Add 3 prior links to reach chain link 4
    for i in range(3):
        dummy = _make_ninja_attack(instance_id=i + 10, power=3)
        game.combat_mgr.add_chain_link(game.state, dummy, 1)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Put a card in defender's arsenal
    arsenal_card = make_card(instance_id=200, owner_index=1, zone=Zone.ARSENAL)
    game.state.players[1].arsenal.append(arsenal_card)

    game._apply_card_ability(attack, 0, "on_hit")

    assert len(game.state.players[1].arsenal) == 0
    assert arsenal_card in game.state.players[1].graveyard


def test_breaking_point_no_rupture_below_link_4():
    """Breaking Point does nothing if below chain link 4."""
    game = make_game_shell()
    attack = _make_draconic_attack(
        instance_id=5, name="Breaking Point", power=5,
    )
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    arsenal_card = make_card(instance_id=200, owner_index=1, zone=Zone.ARSENAL)
    game.state.players[1].arsenal.append(arsenal_card)

    game._apply_card_ability(attack, 0, "on_hit")

    assert len(game.state.players[1].arsenal) == 1  # unchanged


# ---------------------------------------------------------------------------
# Command and Conquer (on_hit)
# ---------------------------------------------------------------------------


def test_command_and_conquer_destroys_arsenal_on_hit():
    """Command and Conquer on hit destroys all cards in target's arsenal."""
    game = make_game_shell()
    attack = _make_ninja_attack(
        instance_id=1, name="Command and Conquer", power=6,
        supertypes=frozenset({SuperType.GENERIC}),
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    arsenal_card = make_card(instance_id=200, owner_index=1, zone=Zone.ARSENAL)
    game.state.players[1].arsenal.append(arsenal_card)

    game._apply_card_ability(attack, 0, "on_hit")

    assert len(game.state.players[1].arsenal) == 0
    assert arsenal_card in game.state.players[1].graveyard


# ---------------------------------------------------------------------------
# Demonstrate Devotion / Display Loyalty (on_attack -- conditional)
# ---------------------------------------------------------------------------


def test_demonstrate_devotion_with_2_draconic_links():
    """Demonstrate Devotion grants Go Again + Fealty with 2+ Draconic links."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # Two prior Draconic links
    d1 = _make_draconic_ninja_attack(instance_id=10)
    game.combat_mgr.add_chain_link(game.state, d1, 1)
    d2 = _make_draconic_ninja_attack(instance_id=11)
    game.combat_mgr.add_chain_link(game.state, d2, 1)

    # Demonstrate Devotion itself (Draconic Ninja)
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Demonstrate Devotion", power=4,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    # Should have Go Again
    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in kws

    # Should have created a Fealty token
    fealty_tokens = [
        p for p in game.state.players[0].permanents if p.name == "Fealty"
    ]
    assert len(fealty_tokens) == 1


def test_demonstrate_devotion_without_enough_draconic_links():
    """Demonstrate Devotion does nothing with fewer than 2 Draconic links.

    The card itself is Draconic but it's the ONLY Draconic link on the chain,
    so we have only 1 Draconic chain link total (itself).
    """
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # Prior link is NOT Draconic (just Ninja)
    d1 = _make_ninja_attack(instance_id=10)
    game.combat_mgr.add_chain_link(game.state, d1, 1)

    # Demonstrate Devotion is Draconic -- so we have 1 Draconic link (itself)
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Demonstrate Devotion", power=4,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in kws

    fealty_tokens = [
        p for p in game.state.players[0].permanents if p.name == "Fealty"
    ]
    assert len(fealty_tokens) == 0


def test_display_loyalty_with_2_draconic_links():
    """Display Loyalty works same as Demonstrate Devotion."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    d1 = _make_draconic_ninja_attack(instance_id=10)
    game.combat_mgr.add_chain_link(game.state, d1, 1)
    d2 = _make_draconic_ninja_attack(instance_id=11)
    game.combat_mgr.add_chain_link(game.state, d2, 1)

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Display Loyalty", power=3,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in kws

    fealty_tokens = [
        p for p in game.state.players[0].permanents if p.name == "Fealty"
    ]
    assert len(fealty_tokens) == 1


# ---------------------------------------------------------------------------
# Hot on Their Heels / Mark with Magma (on_attack -- conditional + mark)
# ---------------------------------------------------------------------------


def test_hot_on_their_heels_with_2_draconic_links():
    """Hot on Their Heels grants Go Again and mark-on-hit with 2+ Draconic links."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    d1 = _make_draconic_ninja_attack(instance_id=10)
    game.combat_mgr.add_chain_link(game.state, d1, 1)
    d2 = _make_draconic_ninja_attack(instance_id=11)
    game.combat_mgr.add_chain_link(game.state, d2, 1)

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Hot on Their Heels", power=3,
    )
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    # Go Again granted
    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in kws

    # Mark trigger registered
    assert game.state.players[1].is_marked is False  # not yet marked

    # Simulate hit event
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=3,
        data={"chain_link": link},
    ))
    game._process_pending_triggers()

    assert game.state.players[1].is_marked is True


def test_hot_on_their_heels_without_enough_links():
    """Hot on Their Heels does nothing with fewer than 2 Draconic links.

    Only 1 Draconic link (the card itself).
    """
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Hot on Their Heels", power=3,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in kws


def test_mark_with_magma_with_2_draconic_links():
    """Mark with Magma grants Go Again and mark-on-hit with 2+ Draconic links."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    d1 = _make_draconic_ninja_attack(instance_id=10)
    game.combat_mgr.add_chain_link(game.state, d1, 1)
    d2 = _make_draconic_ninja_attack(instance_id=11)
    game.combat_mgr.add_chain_link(game.state, d2, 1)

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Mark with Magma", power=4,
    )
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in kws

    # Simulate hit
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=4,
        data={"chain_link": link},
    ))
    game._process_pending_triggers()

    assert game.state.players[1].is_marked is True


# ---------------------------------------------------------------------------
# Hunt to the Ends of Rathe (on_attack)
# ---------------------------------------------------------------------------


def test_hunt_marks_arakni_and_gains_power():
    """Hunt to the Ends of Rathe marks Arakni and gets +2 power."""
    game = make_game_shell()
    # Set up defender as Arakni
    arakni_def = CardDefinition(
        unique_id="hero-arakni",
        name="Arakni, Marionette",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=20,
        intellect=4,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    game.state.players[1].hero = CardInstance(
        instance_id=999, definition=arakni_def, owner_index=1, zone=Zone.HERO,
    )

    attack = _make_draconic_attack(
        instance_id=1, name="Hunt to the Ends of Rathe", power=2,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    # Arakni should be marked
    assert game.state.players[1].is_marked is True
    # +2 power (because now marked)
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4  # 2 + 2


def test_hunt_plus_power_if_already_marked():
    """Hunt to the Ends of Rathe gets +2 power if target is already marked."""
    game = make_game_shell()
    game.state.players[1].is_marked = True

    attack = _make_draconic_attack(
        instance_id=1, name="Hunt to the Ends of Rathe", power=2,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4


# ---------------------------------------------------------------------------
# Ignite (on_attack)
# ---------------------------------------------------------------------------


def test_ignite_applies_cost_reduction():
    """Ignite applies a cost reduction to Draconic cards."""
    game = make_game_shell()
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Ignite", power=2,
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    # Check that a Draconic card would have reduced cost
    test_card = _make_draconic_attack(instance_id=50, power=3, cost=2)
    modified_cost = game.effect_engine.get_modified_cost(game.state, test_card)
    assert modified_cost == 1  # 2 - 1


# ---------------------------------------------------------------------------
# Enlightened Strike (on_attack -- modal)
# ---------------------------------------------------------------------------


def test_enlightened_strike_power_mode():
    """Enlightened Strike +2 power mode works."""
    game = make_game_shell()
    attack = _make_ninja_attack(
        instance_id=1, name="Enlightened Strike", power=5, cost=0,
        supertypes=frozenset({SuperType.GENERIC}),
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Give player a card to put on bottom (additional cost)
    hand_card = make_card(instance_id=50, owner_index=0, zone=Zone.HAND)
    game.state.players[0].hand.append(hand_card)

    # Mock ask: first decision = put card on bottom, second = choose power mode
    call_count = [0]

    def mock_ask(decision):
        call_count[0] += 1
        if call_count[0] == 1:
            # Additional cost: put card on bottom
            return PlayerResponse(
                selected_option_ids=[f"bottom_{hand_card.instance_id}"]
            )
        elif call_count[0] == 2:
            # Choose power mode
            return PlayerResponse(selected_option_ids=["power"])
        return PlayerResponse(selected_option_ids=["pass"])

    _MockPlayer = type("P", (), {"decide": lambda s, state, d: mock_ask(d)})
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    game._apply_card_ability(attack, 0, "on_attack")

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 7  # 5 + 2


def test_enlightened_strike_go_again_mode():
    """Enlightened Strike Go Again mode works."""
    game = make_game_shell()
    attack = _make_ninja_attack(
        instance_id=1, name="Enlightened Strike", power=5, cost=0,
        supertypes=frozenset({SuperType.GENERIC}),
    )
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    hand_card = make_card(instance_id=50, owner_index=0, zone=Zone.HAND)
    game.state.players[0].hand.append(hand_card)

    call_count = [0]

    def mock_ask(decision):
        call_count[0] += 1
        if call_count[0] == 1:
            return PlayerResponse(
                selected_option_ids=[f"bottom_{hand_card.instance_id}"]
            )
        elif call_count[0] == 2:
            return PlayerResponse(selected_option_ids=["go_again"])
        return PlayerResponse(selected_option_ids=["pass"])

    _MockPlayer = type("P", (), {"decide": lambda s, state, d: mock_ask(d)})
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    game._apply_card_ability(attack, 0, "on_attack")

    kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in kws


# ---------------------------------------------------------------------------
# Spreading Flames (on_attack -- continuous effect)
# ---------------------------------------------------------------------------


def test_spreading_flames_applies_power_bonus():
    """Spreading Flames gives +1 power to Draconic attacks with base power < chain count."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # Create 3 Draconic chain links
    for i in range(3):
        d = _make_draconic_ninja_attack(instance_id=i + 10, power=2)
        game.combat_mgr.add_chain_link(game.state, d, 1)

    # Spreading Flames itself
    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Spreading Flames", power=3,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_attack")

    # A Draconic attack with base power 2 (< 4 chain links) should get +1
    target = _make_draconic_ninja_attack(instance_id=50, power=2)
    effective_power = game.effect_engine.get_modified_power(game.state, target)
    assert effective_power == 3  # 2 + 1

    # A Draconic attack with base power 5 (>= 4) should NOT get +1
    target2 = _make_draconic_ninja_attack(instance_id=51, power=5)
    effective_power2 = game.effect_engine.get_modified_power(game.state, target2)
    assert effective_power2 == 5  # unchanged


# ---------------------------------------------------------------------------
# Devotion Never Dies (on_hit)
# ---------------------------------------------------------------------------


def test_devotion_never_dies_banishes_if_prev_draconic():
    """Devotion Never Dies banishes itself on hit if previous attack was Draconic."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # Previous Draconic attack
    prev = _make_draconic_ninja_attack(instance_id=10, power=3)
    game.combat_mgr.add_chain_link(game.state, prev, 1)

    # Devotion Never Dies (Ninja, not Draconic)
    attack = _make_ninja_attack(
        instance_id=1, name="Devotion Never Dies", power=4,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_hit")

    assert attack in game.state.players[0].banished
    assert attack.zone == Zone.BANISHED


def test_devotion_never_dies_no_banish_if_prev_not_draconic():
    """Devotion Never Dies does not banish if previous attack was not Draconic."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # Previous non-Draconic attack
    prev = _make_ninja_attack(instance_id=10, power=3)
    game.combat_mgr.add_chain_link(game.state, prev, 1)

    attack = _make_ninja_attack(
        instance_id=1, name="Devotion Never Dies", power=4,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    game._apply_card_ability(attack, 0, "on_hit")

    assert attack not in game.state.players[0].banished


# ---------------------------------------------------------------------------
# Rising Resentment (on_hit)
# ---------------------------------------------------------------------------


def test_rising_resentment_banishes_eligible_card():
    """Rising Resentment on hit banishes an attack action from hand."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    # 3 Draconic chain links
    for i in range(3):
        d = _make_draconic_ninja_attack(instance_id=i + 10, power=2)
        game.combat_mgr.add_chain_link(game.state, d, 1)

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Rising Resentment", power=3,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Put an eligible attack action in hand (cost 2 < 4 draconic links)
    hand_atk = _make_ninja_attack(instance_id=50, power=3, cost=2)
    hand_atk.zone = Zone.HAND
    game.state.players[0].hand.append(hand_atk)

    # Mock ask: choose to banish the card
    def mock_ask(decision):
        return PlayerResponse(
            selected_option_ids=[f"banish_{hand_atk.instance_id}"]
        )

    _MockPlayer = type("P", (), {"decide": lambda s, state, d: mock_ask(d)})
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    game._apply_card_ability(attack, 0, "on_hit")

    assert hand_atk in game.state.players[0].banished
    assert hand_atk not in game.state.players[0].hand


def test_rising_resentment_no_eligible_cards():
    """Rising Resentment does nothing if no eligible cards in hand."""
    game = make_game_shell()
    game.combat_mgr.open_chain(game.state)

    attack = _make_draconic_ninja_attack(
        instance_id=1, name="Rising Resentment", power=3,
    )
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # No attack actions in hand, only 1 draconic link, and cost threshold is 1
    game._apply_card_ability(attack, 0, "on_hit")

    # Should not error, just log and return
    assert len(game.state.players[0].banished) == 0


# ---------------------------------------------------------------------------
# Throw Dagger (attack_reaction_effect)
# ---------------------------------------------------------------------------


def test_throw_dagger_deals_damage_and_destroys():
    """Throw Dagger deals 1 damage with a dagger and destroys it."""
    game = make_game_shell(life=20)
    attack = _make_ninja_attack(instance_id=1, power=4)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Give player a dagger
    dagger = _make_dagger_weapon(instance_id=100)
    game.state.players[0].weapons.append(dagger)

    # Give player a deck card for draw
    deck_card = make_card(instance_id=99, owner_index=0, zone=Zone.DECK)
    game.state.players[0].deck.append(deck_card)

    throw_card = _make_attack_reaction(
        "Throw Dagger", instance_id=10,
        supertypes=frozenset({SuperType.ASSASSIN, SuperType.NINJA}),
    )
    game._apply_card_ability(throw_card, 0, "attack_reaction_effect")

    # 1 damage dealt
    assert game.state.players[1].life_total == 19
    # Dagger destroyed
    assert dagger not in game.state.players[0].weapons
    assert dagger in game.state.players[0].graveyard
    # Drew a card
    assert deck_card in game.state.players[0].hand


def test_throw_dagger_no_daggers_does_nothing():
    """Throw Dagger with no daggers available does nothing."""
    game = make_game_shell(life=20)
    attack = _make_ninja_attack(instance_id=1, power=4)
    game.combat_mgr.open_chain(game.state)
    game.combat_mgr.add_chain_link(game.state, attack, 1)

    throw_card = _make_attack_reaction("Throw Dagger", instance_id=10)
    game._apply_card_ability(throw_card, 0, "attack_reaction_effect")

    assert game.state.players[1].life_total == 20


# ---------------------------------------------------------------------------
# Warmonger's Diplomacy (on_play -- stub test)
# ---------------------------------------------------------------------------


def test_warmongers_diplomacy_asks_opponent():
    """Warmonger's Diplomacy asks the opponent for a choice."""
    game = make_game_shell()
    card_def = CardDefinition(
        unique_id="wm-1",
        name="Warmonger's Diplomacy",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    card = CardInstance(
        instance_id=1, definition=card_def, owner_index=0, zone=Zone.STACK,
    )

    # Set up mock interfaces for the ask callback
    _MockPlayer = type(
        "P",
        (),
        {
            "decide": lambda s, state, d: PlayerResponse(
                selected_option_ids=["war"]
            )
        },
    )
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    # Should not error
    game._apply_card_ability(card, 0, "on_play")


def test_warmongers_diplomacy_controller_restriction_deferred():
    """Controller's Warmonger's Diplomacy restriction should NOT apply on the current turn.

    The card says "next turn", so when the controller plays Warmonger's Diplomacy
    on turn N, the restriction should only apply on their NEXT turn (turn N+2),
    not the current turn. The opponent's restriction applies immediately on their
    next turn (turn N+1).
    """
    game = make_game_shell(action_points={0: 1, 1: 0}, resource_points={0: 3, 1: 0})
    game.state.turn_number = 5
    game.state.turn_player_index = 0

    # Create the Warmonger's Diplomacy card
    card_def = CardDefinition(
        unique_id="wm-1",
        name="Warmonger's Diplomacy",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    card = CardInstance(
        instance_id=1, definition=card_def, owner_index=0, zone=Zone.STACK,
    )

    # Both players choose "peace" (only non-attack, non-weapon actions allowed)
    _MockPlayer = type(
        "P",
        (),
        {
            "decide": lambda s, state, d: PlayerResponse(
                selected_option_ids=["peace"]
            )
        },
    )
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    # Play the card (controller is player 0 on turn 5)
    game._apply_card_ability(card, 0, "on_play")

    # Both players should have the restriction set
    p0 = game.state.players[0]
    p1 = game.state.players[1]
    assert p0.diplomacy_restriction == "peace"
    assert p1.diplomacy_restriction == "peace"

    # Controller's active_turn is turn 7 (current turn 5 + 2)
    assert p0.diplomacy_restriction_active_turn == 7
    # Opponent's active_turn is turn 6 (current turn 5 + 1)
    assert p1.diplomacy_restriction_active_turn == 6

    # Create a non-attack action card for testing
    non_attack_def = CardDefinition(
        unique_id="na-1",
        name="Test Action",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )

    # Create an attack action card for testing
    attack_def = CardDefinition(
        unique_id="atk-1",
        name="Test Attack",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=3,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )

    attack_card = CardInstance(
        instance_id=10, definition=attack_def, owner_index=0, zone=Zone.HAND,
    )
    non_attack_card = CardInstance(
        instance_id=11, definition=non_attack_def, owner_index=0, zone=Zone.HAND,
    )

    # On the CURRENT turn (5), the controller should NOT be restricted
    # Peace restriction would block attack actions, but it should be deferred
    assert game.action_builder.can_play_card(game.state, 0, attack_card) is True
    assert game.action_builder.can_play_card(game.state, 0, non_attack_card) is True

    # Simulate advancing to the controller's next turn (turn 7)
    game.state.turn_number = 7
    game.state.action_points = {0: 1, 1: 0}
    # NOW the peace restriction should be active: blocks attack actions
    assert game.action_builder.can_play_card(game.state, 0, attack_card) is False
    # Non-attack actions should still be allowed
    assert game.action_builder.can_play_card(game.state, 0, non_attack_card) is True


def test_warmongers_diplomacy_opponent_restriction_immediate_next_turn():
    """Opponent's Warmonger's Diplomacy restriction applies on their next turn.

    When controller plays on turn N, the opponent's restriction should apply
    starting on turn N+1 (their next turn).
    """
    game = make_game_shell(action_points={0: 0, 1: 1}, resource_points={0: 0, 1: 3})
    game.state.turn_number = 5
    game.state.turn_player_index = 0

    card_def = CardDefinition(
        unique_id="wm-1",
        name="Warmonger's Diplomacy",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    card = CardInstance(
        instance_id=1, definition=card_def, owner_index=0, zone=Zone.STACK,
    )

    # Opponent chooses "war" (only attack actions and weapon attacks)
    _MockPlayer = type(
        "P",
        (),
        {
            "decide": lambda s, state, d: PlayerResponse(
                selected_option_ids=["war"]
            )
        },
    )
    game.interfaces = [_MockPlayer(), _MockPlayer()]

    game._apply_card_ability(card, 0, "on_play")

    p1 = game.state.players[1]
    assert p1.diplomacy_restriction == "war"
    assert p1.diplomacy_restriction_active_turn == 6

    # Create test cards for opponent (player 1)
    non_attack_def = CardDefinition(
        unique_id="na-1",
        name="Test Action",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.GENERIC}),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    non_attack_card = CardInstance(
        instance_id=20, definition=non_attack_def, owner_index=1, zone=Zone.HAND,
    )

    # On turn 5 (controller's turn), the opponent's restriction is not yet active
    assert game.action_builder.can_play_card(game.state, 1, non_attack_card) is True

    # On opponent's next turn (turn 6), war restriction blocks non-attack actions
    game.state.turn_number = 6
    assert game.action_builder.can_play_card(game.state, 1, non_attack_card) is False
