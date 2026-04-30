"""Tests for remaining infrastructure TODOs.

Covers:
1. Pain in the Backside — stale TODO removed (verify implementation still works)
2. Authority of Ataya — pitch trigger increases defense reaction cost for opponents
3. Shelter from the Storm — instant discard damage prevention (3 uses of 1 prevention)
4. Take Up the Mantle — copy effect via definition_override
"""

from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.rules.abilities import AbilityContext, AbilityRegistry
from engine.rules.actions import ActionOption, Decision, PlayerResponse
from engine.rules.continuous import EffectDuration, make_power_modifier
from engine.rules.events import EventBus, EventType, GameEvent, ReplacementEffect
from engine.enums import (
    ActionType,
    CardType,
    Color,
    DecisionType,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import (
    make_card,
    make_game_shell,
    make_mock_ask,
    make_pitch_card,
)
from tests.abilities.conftest import (
    make_attack_reaction,
    make_defense_reaction,
    make_dagger_weapon,
    make_stealth_attack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_authority_of_ataya(instance_id: int = 50, owner_index: int = 0) -> CardInstance:
    """Create an Authority of Ataya card."""
    defn = CardDefinition(
        unique_id=f"ataya-{instance_id}",
        name="Authority of Ataya",
        color=Color.BLUE,
        pitch=3,
        cost=None,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.RESOURCE}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.LEGENDARY}),
        functional_text="Legendary. When this is pitched, defense reaction cards cost opponents an additional {r} to play this turn.",
        type_text="Generic Resource - Gem",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_shelter(instance_id: int = 60, owner_index: int = 0) -> CardInstance:
    """Create a Shelter from the Storm card."""
    defn = CardDefinition(
        unique_id=f"shelter-{instance_id}",
        name="Shelter from the Storm",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=4,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEFENSE_REACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="Instant - Discard this: The next 3 times you would be dealt damage this turn, prevent 1 of that damage.",
        type_text="Generic Defense Reaction",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_stealth_attack_in_gy(
    instance_id: int = 70,
    name: str = "Stealth Graveyard Card",
    power: int = 5,
    owner_index: int = 0,
) -> CardInstance:
    """Create a stealth attack action in the graveyard for copy testing."""
    defn = CardDefinition(
        unique_id=f"gy-stealth-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=0,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="",
        type_text="Assassin Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.GRAVEYARD,
    )


# ---------------------------------------------------------------------------
# 1. Pain in the Backside — verify implementation still works
# ---------------------------------------------------------------------------


def test_pain_in_the_backside_deals_dagger_damage():
    """Pain in the Backside: dagger deals 1 damage on hit, dagger gets HIT event."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    game.state.players[1].life_total = 20

    dagger = make_dagger_weapon(instance_id=100, owner_index=0)
    game.state.players[0].weapons = [dagger]

    # Must use the actual card name so ability registry finds the handler
    defn = CardDefinition(
        unique_id="pitb-1",
        name="Pain in the Backside",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=2,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="",
        type_text="",
    )
    attack = CardInstance(instance_id=1, definition=defn, owner_index=0, zone=Zone.COMBAT_CHAIN)

    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    # Track HIT events on the dagger
    hit_events = []
    game.events.register_handler(EventType.HIT, lambda e: hit_events.append(e))

    ask = make_mock_ask({"dagger": [f"dagger_{dagger.instance_id}"]})
    game._ask = ask
    game._apply_card_ability(attack, 0, "on_hit")

    assert game.state.players[1].life_total == 19
    assert len(hit_events) == 1
    assert hit_events[0].source.instance_id == dagger.instance_id


def test_pain_in_the_backside_no_dagger_no_damage():
    """Pain in the Backside: no daggers → no damage dealt."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    game.state.players[1].life_total = 20

    # No daggers
    game.state.players[0].weapons = []

    # Create a card named "Pain in the Backside" explicitly
    defn = CardDefinition(
        unique_id="pitb-1",
        name="Pain in the Backside",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=2,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="",
        type_text="",
    )
    attack = CardInstance(instance_id=1, definition=defn, owner_index=0, zone=Zone.COMBAT_CHAIN)

    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    game._ask = make_mock_ask({})
    game._apply_card_ability(attack, 0, "on_hit")

    # No damage dealt
    assert game.state.players[1].life_total == 20


# ---------------------------------------------------------------------------
# 2. Authority of Ataya — pitch trigger
# ---------------------------------------------------------------------------


def test_authority_of_ataya_pitch_increases_dr_cost():
    """Pitching Authority of Ataya increases defense reaction cost for opponents."""
    game = make_game_shell()
    ataya = _make_authority_of_ataya(instance_id=50, owner_index=0)
    game.state.players[0].hand.append(ataya)

    game._ask = make_mock_ask({})

    # Pitch the card
    from engine.rules.cost import pitch_card
    pitch_card(game.state, 0, ataya, game.events)

    # Check that defense reactions for opponent (player 1) cost +1
    dr = make_defense_reaction(instance_id=20, owner_index=1)
    modified_cost = game.effect_engine.get_modified_cost(game.state, dr)
    assert modified_cost == 1  # base 0 + 1 from Authority


def test_authority_of_ataya_does_not_affect_controller_dr():
    """Authority of Ataya only affects opponents, not the controller."""
    game = make_game_shell()
    ataya = _make_authority_of_ataya(instance_id=50, owner_index=0)
    game.state.players[0].hand.append(ataya)

    game._ask = make_mock_ask({})

    from engine.rules.cost import pitch_card
    pitch_card(game.state, 0, ataya, game.events)

    # Controller's defense reactions are unaffected
    dr = make_defense_reaction(instance_id=21, owner_index=0)
    modified_cost = game.effect_engine.get_modified_cost(game.state, dr)
    assert modified_cost == 0  # base cost, no increase


def test_authority_of_ataya_does_not_affect_non_dr():
    """Authority of Ataya only affects defense reactions, not other cards."""
    game = make_game_shell()
    ataya = _make_authority_of_ataya(instance_id=50, owner_index=0)
    game.state.players[0].hand.append(ataya)

    game._ask = make_mock_ask({})

    from engine.rules.cost import pitch_card
    pitch_card(game.state, 0, ataya, game.events)

    # Attack reaction for opponent — should not be affected
    ar = make_attack_reaction(instance_id=22, owner_index=1, cost=1)
    modified_cost = game.effect_engine.get_modified_cost(game.state, ar)
    assert modified_cost == 1  # unchanged


def test_pitch_card_emits_event():
    """pitch_card emits PITCH_CARD event when event_bus is provided."""
    events = EventBus()
    from engine.state.game_state import GameState
    from engine.state.player_state import PlayerState

    state = GameState()
    state.players = [PlayerState(index=0, life_total=20), PlayerState(index=1, life_total=20)]
    state.resource_points = {0: 0, 1: 0}

    card = make_pitch_card(instance_id=200, owner_index=0, pitch=3)
    state.players[0].hand.append(card)

    emitted = []
    events.register_handler(EventType.PITCH_CARD, lambda e: emitted.append(e))

    from engine.rules.cost import pitch_card
    gained = pitch_card(state, 0, card, events)

    assert gained == 3
    assert len(emitted) == 1
    assert emitted[0].card.instance_id == card.instance_id
    assert emitted[0].amount == 3


def test_pitch_card_no_event_without_bus():
    """pitch_card does NOT emit events when event_bus is None (backward compat)."""
    from engine.state.game_state import GameState
    from engine.state.player_state import PlayerState

    state = GameState()
    state.players = [PlayerState(index=0, life_total=20), PlayerState(index=1, life_total=20)]
    state.resource_points = {0: 0, 1: 0}

    card = make_pitch_card(instance_id=200, owner_index=0, pitch=2)
    state.players[0].hand.append(card)

    from engine.rules.cost import pitch_card
    gained = pitch_card(state, 0, card)  # no event bus

    assert gained == 2


# ---------------------------------------------------------------------------
# 3. Shelter from the Storm — instant discard damage prevention
# ---------------------------------------------------------------------------


def test_shelter_prevents_1_damage_per_instance():
    """Shelter prevents 1 damage each of the next 3 damage events."""
    game = make_game_shell()
    shelter = _make_shelter(instance_id=60, owner_index=0)
    game.state.players[0].hand.append(shelter)
    game.state.players[0].life_total = 20

    game._ask = make_mock_ask({})
    game._activate_instant_discard(0, shelter)

    # Take 3 damage — should be reduced to 2 each time
    for _ in range(3):
        game.events.emit(GameEvent(
            event_type=EventType.DEAL_DAMAGE,
            source=None,
            target_player=0,
            amount=3,
        ))

    # 3 hits of 2 damage each = 6 damage total
    assert game.state.players[0].life_total == 14


def test_shelter_expires_after_3_uses():
    """After 3 prevention uses, Shelter has no effect on the 4th damage event."""
    game = make_game_shell()
    shelter = _make_shelter(instance_id=60, owner_index=0)
    game.state.players[0].hand.append(shelter)
    game.state.players[0].life_total = 20

    game._ask = make_mock_ask({})
    game._activate_instant_discard(0, shelter)

    # Use up all 3 prevention uses
    for _ in range(3):
        game.events.emit(GameEvent(
            event_type=EventType.DEAL_DAMAGE,
            source=None,
            target_player=0,
            amount=2,
        ))

    # Life: 20 - 3*(2-1) = 17
    assert game.state.players[0].life_total == 17

    # 4th damage event — no prevention
    game.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=None,
        target_player=0,
        amount=5,
    ))
    assert game.state.players[0].life_total == 12  # 17 - 5


def test_shelter_only_affects_controller():
    """Shelter only prevents damage to the controller, not the opponent."""
    game = make_game_shell()
    shelter = _make_shelter(instance_id=60, owner_index=0)
    game.state.players[0].hand.append(shelter)
    game.state.players[0].life_total = 20
    game.state.players[1].life_total = 20

    game._ask = make_mock_ask({})
    game._activate_instant_discard(0, shelter)

    # Damage to opponent (player 1) — not affected
    game.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=None,
        target_player=1,
        amount=5,
    ))
    assert game.state.players[1].life_total == 15  # full damage


def test_shelter_prevents_1_even_for_1_damage():
    """Shelter prevents exactly 1, reducing 1 damage to 0."""
    game = make_game_shell()
    shelter = _make_shelter(instance_id=60, owner_index=0)
    game.state.players[0].hand.append(shelter)
    game.state.players[0].life_total = 20

    game._ask = make_mock_ask({})
    game._activate_instant_discard(0, shelter)

    game.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=None,
        target_player=0,
        amount=1,
    ))
    # 1 - 1 = 0 damage dealt
    assert game.state.players[0].life_total == 20


def test_shelter_is_registered_as_instant_discard():
    """Shelter from the Storm is registered in the ability registry."""
    game = make_game_shell()
    handler = game.ability_registry.lookup("instant_discard_effect", "Shelter from the Storm")
    assert handler is not None


def test_shelter_emits_damage_prevented_event():
    """When Shelter prevents damage, the engine emits a DAMAGE_PREVENTED
    event carrying the original damage source, the prevented amount, and
    the prevention source name in ``data['prevention_source']``.

    Regression for replays/cindra-blue-vs-arakni-002 lessons.md (Bug 3):
    analysts could only infer prevention from a bare ``modified=True``
    flag on DEAL_DAMAGE. The DAMAGE_PREVENTED event makes the prevention
    a first-class fact in the events stream.
    """
    game = make_game_shell()
    shelter = _make_shelter(instance_id=60, owner_index=0)
    game.state.players[0].hand.append(shelter)
    game.state.players[0].life_total = 20

    game._ask = make_mock_ask({})
    game._activate_instant_discard(0, shelter)

    # Capture both DEAL_DAMAGE and DAMAGE_PREVENTED events.
    deal_events: list[GameEvent] = []
    prevented_events: list[GameEvent] = []
    game.events.register_handler(EventType.DEAL_DAMAGE, deal_events.append)
    game.events.register_handler(EventType.DAMAGE_PREVENTED, prevented_events.append)

    # Build a fake source so the event can identify *who* dealt the damage.
    src = make_card(name="Hunter's Klaive", power=4)

    game.events.emit(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=src,
        target_player=0,
        amount=4,
    ))

    # DEAL_DAMAGE was reduced 4 -> 3, modified flag set, in-band prevention data attached.
    assert len(deal_events) == 1
    deal = deal_events[0]
    assert deal.amount == 3
    assert deal.modified is True
    assert "prevention" in deal.data
    assert deal.data["prevention"][0]["source_name"] == "Shelter from the Storm"
    assert deal.data["prevention"][0]["amount_prevented"] == 1

    # And a separate DAMAGE_PREVENTED event was emitted carrying the
    # original source and the prevention source name.
    assert len(prevented_events) == 1
    prev = prevented_events[0]
    assert prev.source is src
    assert prev.target_player == 0
    assert prev.amount == 1
    assert prev.data["prevention_source"] == "Shelter from the Storm"
    assert prev.data["original_amount"] == 4
    assert prev.data["remaining_amount"] == 3

    # Net life change: 4 - 1 prevented = 3 damage dealt.
    assert game.state.players[0].life_total == 17


# ---------------------------------------------------------------------------
# 4. Take Up the Mantle — copy effect
# ---------------------------------------------------------------------------


def test_take_up_the_mantle_unmarked_plus2():
    """Take Up the Mantle: +2 power when target is not marked."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    game.state.players[1].is_marked = False

    attack = make_stealth_attack(instance_id=1, power=3, owner_index=0)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    reaction = make_attack_reaction(
        name="Take Up the Mantle",
        instance_id=10,
        owner_index=0,
    )
    game._ask = make_mock_ask({})
    game._apply_card_ability(reaction, 0, "attack_reaction_effect")

    modified_power = game.effect_engine.get_modified_power(game.state, attack)
    assert modified_power == 5  # 3 base + 2


def test_take_up_the_mantle_marked_plus3():
    """Take Up the Mantle: +3 power when target is marked."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    game.state.players[1].is_marked = True

    attack = make_stealth_attack(instance_id=1, power=3, owner_index=0)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    reaction = make_attack_reaction(
        name="Take Up the Mantle",
        instance_id=10,
        owner_index=0,
    )
    # Pass on the banish option
    game._ask = make_mock_ask({"banish": ["pass"]})
    game._apply_card_ability(reaction, 0, "attack_reaction_effect")

    modified_power = game.effect_engine.get_modified_power(game.state, attack)
    assert modified_power == 6  # 3 base + 3


def test_take_up_the_mantle_copy_effect():
    """Take Up the Mantle: banish stealth card, attack becomes a copy."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    game.state.players[1].is_marked = True

    attack = make_stealth_attack(
        instance_id=1, power=3, name="Original Attack", owner_index=0,
    )
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    # Put a stealth attack in graveyard
    gy_card = _make_stealth_attack_in_gy(
        instance_id=70, name="Copied Card", power=7, owner_index=0,
    )
    game.state.players[0].graveyard.append(gy_card)

    reaction = make_attack_reaction(
        name="Take Up the Mantle",
        instance_id=10,
        owner_index=0,
    )

    # Choose to banish the graveyard card
    game._ask = make_mock_ask({"banish": [f"banish_{gy_card.instance_id}"]})
    game._apply_card_ability(reaction, 0, "attack_reaction_effect")

    # Attack should now be a copy of the banished card
    assert attack.name == "Copied Card"
    assert attack.definition_override is not None
    assert attack.definition_override.name == "Copied Card"
    assert attack.definition_override.power == 7
    # Original definition is preserved
    assert attack.definition.name == "Original Attack"
    # Power via effect engine: base 7 (from copy) + 3 (from Take Up the Mantle bonus)
    modified_power = game.effect_engine.get_modified_power(game.state, attack)
    assert modified_power == 10  # 7 base (copy) + 3 bonus


def test_take_up_the_mantle_copy_banishes_card():
    """Take Up the Mantle: the chosen card is actually banished from graveyard."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    game.state.players[1].is_marked = True

    attack = make_stealth_attack(instance_id=1, power=3, owner_index=0)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    gy_card = _make_stealth_attack_in_gy(instance_id=70, owner_index=0)
    game.state.players[0].graveyard.append(gy_card)

    reaction = make_attack_reaction(
        name="Take Up the Mantle",
        instance_id=10,
        owner_index=0,
    )
    game._ask = make_mock_ask({"banish": [f"banish_{gy_card.instance_id}"]})
    game._apply_card_ability(reaction, 0, "attack_reaction_effect")

    # Card should be banished, not in graveyard
    assert gy_card not in game.state.players[0].graveyard
    assert gy_card in game.state.players[0].banished


def test_take_up_the_mantle_no_stealth_no_effect():
    """Take Up the Mantle: no effect if attack doesn't have Stealth."""
    from engine.state.combat_state import ChainLink

    game = make_game_shell()
    non_stealth = make_card(instance_id=1, name="Non-Stealth Attack", power=3)
    non_stealth.zone = Zone.COMBAT_CHAIN
    link = ChainLink(
        link_number=1,
        active_attack=non_stealth,
        attack_target_index=1,
    )
    game.state.combat_chain.chain_links.append(link)

    reaction = make_attack_reaction(
        name="Take Up the Mantle",
        instance_id=10,
        owner_index=0,
    )
    game._ask = make_mock_ask({})
    game._apply_card_ability(reaction, 0, "attack_reaction_effect")

    modified_power = game.effect_engine.get_modified_power(game.state, non_stealth)
    assert modified_power == 3  # unchanged


# ---------------------------------------------------------------------------
# definition_override infrastructure
# ---------------------------------------------------------------------------


def test_definition_override_changes_name():
    """definition_override makes name delegate to the override."""
    card = make_card(instance_id=1, name="Original")
    override_defn = CardDefinition(
        unique_id="override-1",
        name="Overridden",
        color=Color.RED,
        pitch=1,
        cost=2,
        power=9,
        defense=5,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="",
        type_text="",
    )

    assert card.name == "Original"
    card.definition_override = override_defn
    assert card.name == "Overridden"
    assert card.base_power == 9
    assert card.base_defense == 5
    assert card.cost == 2


def test_definition_override_affects_effect_engine_keywords():
    """EffectEngine reads keywords from _effective_definition."""
    from engine.rules.effects import EffectEngine
    from engine.state.game_state import GameState
    from engine.state.player_state import PlayerState

    state = GameState()
    state.players = [PlayerState(index=0, life_total=20)]
    engine = EffectEngine()

    card = make_card(instance_id=1, name="Original", keywords=frozenset())
    assert Keyword.STEALTH not in engine.get_modified_keywords(state, card)

    override_defn = CardDefinition(
        unique_id="override-2",
        name="Override",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=5,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="",
        type_text="",
    )
    card.definition_override = override_defn
    assert Keyword.STEALTH in engine.get_modified_keywords(state, card)


def test_definition_override_preserves_zone_and_counters():
    """definition_override only changes definition-level properties, not game state."""
    card = make_card(instance_id=1, name="Original")
    card.zone = Zone.COMBAT_CHAIN
    card.counters["power"] = 2

    override_defn = CardDefinition(
        unique_id="override-3",
        name="Copy",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=10,
        defense=5,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    card.definition_override = override_defn

    # Game state preserved
    assert card.zone == Zone.COMBAT_CHAIN
    assert card.counters["power"] == 2
    assert card.instance_id == 1
    # Definition properties come from override
    assert card.name == "Copy"
    assert card.base_power == 10
