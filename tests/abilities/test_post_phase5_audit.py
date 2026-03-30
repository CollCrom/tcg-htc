"""Tests for post-Phase 5 audit fixes.

Covers:
- CRITICAL 1: Throw Dagger / Art of the Dragon: Fire / Blood Runs Deep
  damage goes through event system (DEAL_DAMAGE + HIT events).
- CRITICAL 2: Art of the Dragon: Scale counter visible to effect engine.
- CRITICAL 3: Ambush from arsenal not restricted by Dominate.
- Damage prevention edge cases: LOSE_LIFE vs DEAL_DAMAGE distinction,
  prevention paths for Throw Dagger, Blood Runs Deep, Art of Dragon: Fire.
- Ambush + Overpower interaction from arsenal.
"""

from __future__ import annotations

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import PlayerResponse
from htc.engine.events import EventType, GameEvent, ReplacementEffect
from htc.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.combat_state import ChainLink, CombatChainState
from tests.conftest import make_card, make_equipment, make_game_shell, make_state
from tests.abilities.conftest import (
    make_ability_context,
    make_dagger_attack,
    make_draconic_ninja_attack,
    make_dagger_weapon,
    make_ninja_attack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(game, source_card, link, controller_index=0):
    """Build an AbilityContext wired to the game shell."""
    return make_ability_context(game, source_card, controller_index, chain_link=link)


# ---------------------------------------------------------------------------
# CRITICAL 1: Throw Dagger emits DEAL_DAMAGE + HIT events
# ---------------------------------------------------------------------------


def test_throw_dagger_emits_damage_event():
    """Throw Dagger should deal damage via DEAL_DAMAGE event, not direct subtraction."""
    from htc.cards.abilities.ninja import _throw_dagger

    game = make_game_shell(life=20)
    state = game.state

    # Set up combat chain with an active dagger attack
    game.combat_mgr.open_chain(state)
    active_attack = make_draconic_ninja_attack(
        instance_id=1, name="Active Dagger Attack",
    )
    link = game.combat_mgr.add_chain_link(state, active_attack, 1)
    link.attack_source = active_attack  # weapon source for exclusion

    # Add a separate off-chain dagger weapon to throw
    off_dagger = make_dagger_weapon(instance_id=200, name="Off-Chain Dagger")
    state.players[0].weapons.append(off_dagger)

    # Track emitted events
    emitted = []
    game.events.register_handler(EventType.DEAL_DAMAGE, lambda e: emitted.append(("damage", e)))

    # Make the attack reaction card
    ar_card = CardInstance(
        instance_id=10,
        definition=CardDefinition(
            unique_id="throw-dagger",
            name="Throw Dagger",
            color=Color.BLUE,
            pitch=3,
            cost=0,
            power=None,
            defense=3,
            health=None,
            intellect=None,
            arcane=None,
            types=frozenset({CardType.ATTACK_REACTION}),
            subtypes=frozenset(),
            supertypes=frozenset(),
            keywords=frozenset(),
            functional_text="",
            type_text="",
        ),
        owner_index=0,
        zone=Zone.HAND,
    )

    ctx = _make_ctx(game, ar_card, link)
    initial_life = state.players[1].life_total
    _throw_dagger(ctx)

    # Damage should have gone through event system
    assert len(emitted) > 0, "DEAL_DAMAGE event should have been emitted"
    assert emitted[0][1].amount == 1
    assert state.players[1].life_total == initial_life - 1
    # Damage tracking counters should be updated
    assert state.players[1].turn_counters.damage_taken >= 1
    assert state.players[0].turn_counters.damage_dealt >= 1


def test_throw_dagger_emits_hit_event():
    """Throw Dagger should emit a HIT event when damage is dealt."""
    from htc.cards.abilities.ninja import _throw_dagger

    game = make_game_shell(life=20)
    state = game.state

    game.combat_mgr.open_chain(state)
    active_attack = make_draconic_ninja_attack(instance_id=1)
    link = game.combat_mgr.add_chain_link(state, active_attack, 1)
    link.attack_source = active_attack

    off_dagger = make_dagger_weapon(instance_id=200)
    state.players[0].weapons.append(off_dagger)

    hit_events = []
    game.events.register_handler(EventType.HIT, lambda e: hit_events.append(e))

    ar_card = make_ninja_attack(instance_id=10, name="Throw Dagger")
    ctx = _make_ctx(game, ar_card, link)
    _throw_dagger(ctx)

    assert len(hit_events) == 1, "HIT event should have been emitted"
    assert hit_events[0].source.instance_id == off_dagger.instance_id


# ---------------------------------------------------------------------------
# CRITICAL 1: Art of the Dragon: Fire emits DEAL_DAMAGE event
# ---------------------------------------------------------------------------


def test_art_of_dragon_fire_emits_damage_event():
    """Art of the Dragon: Fire should deal damage via DEAL_DAMAGE event."""
    from htc.cards.abilities.ninja import _art_of_the_dragon_fire_on_attack

    game = make_game_shell(life=20)
    state = game.state

    game.combat_mgr.open_chain(state)
    # Must be Draconic for the effect to trigger
    attack = make_draconic_ninja_attack(
        instance_id=1, name="Art of the Dragon: Fire", power=3,
    )
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    emitted = []
    game.events.register_handler(EventType.DEAL_DAMAGE, lambda e: emitted.append(e))

    ctx = _make_ctx(game, attack, link)
    initial_life = state.players[1].life_total
    _art_of_the_dragon_fire_on_attack(ctx)

    assert len(emitted) == 1, "DEAL_DAMAGE event should have been emitted"
    assert emitted[0].amount == 2
    assert state.players[1].life_total == initial_life - 2
    assert state.players[1].turn_counters.damage_taken >= 2


# ---------------------------------------------------------------------------
# CRITICAL 1: Blood Runs Deep emits DEAL_DAMAGE + HIT events per dagger
# ---------------------------------------------------------------------------


def test_blood_runs_deep_emits_damage_events():
    """Blood Runs Deep should emit DEAL_DAMAGE + HIT per dagger."""
    from htc.cards.abilities.ninja import _blood_runs_deep_on_attack

    game = make_game_shell(life=20)
    state = game.state

    game.combat_mgr.open_chain(state)
    attack = make_draconic_ninja_attack(
        instance_id=1, name="Blood Runs Deep", power=5,
    )
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    # Add 2 daggers
    dagger1 = make_dagger_weapon(instance_id=100, name="Dagger A")
    dagger2 = make_dagger_weapon(instance_id=101, name="Dagger B")
    state.players[0].weapons.extend([dagger1, dagger2])

    damage_events = []
    hit_events = []
    game.events.register_handler(EventType.DEAL_DAMAGE, lambda e: damage_events.append(e))
    game.events.register_handler(EventType.HIT, lambda e: hit_events.append(e))

    ctx = _make_ctx(game, attack, link)
    initial_life = state.players[1].life_total
    _blood_runs_deep_on_attack(ctx)

    assert len(damage_events) == 2, "One DEAL_DAMAGE per dagger"
    assert len(hit_events) == 2, "One HIT per dagger (each dagger dealt damage)"
    assert state.players[1].life_total == initial_life - 2
    assert state.players[1].turn_counters.damage_taken >= 2


# ---------------------------------------------------------------------------
# CRITICAL 2: Art of the Dragon: Scale counter visible to effect engine
# ---------------------------------------------------------------------------


def test_art_of_dragon_scale_counter_uses_counters_dict():
    """Art of the Dragon: Scale should set card.counters['defense'], not defense_counters."""
    from htc.cards.abilities.ninja import _ArtOfDragonScaleHitTrigger

    game = make_game_shell(life=20)
    state = game.state

    # Set up target equipment on player 1
    eq = make_equipment(
        instance_id=50, name="Vest", defense=2,
        subtype=SubType.CHEST, owner_index=1,
    )
    state.players[1].equipment[EquipmentSlot.CHEST] = eq

    # Create and fire the trigger directly
    trigger = _ArtOfDragonScaleHitTrigger(
        attack_instance_id=1,
        controller_index=0,
        target_player_index=1,
        _state=state,
        _ask=lambda d: PlayerResponse(selected_option_ids=["pass"]),
        one_shot=True,
    )

    # Fire the trigger with a matching HIT event
    source = make_draconic_ninja_attack(instance_id=1)
    hit_event = GameEvent(
        event_type=EventType.HIT,
        source=source,
        target_player=1,
        amount=4,
    )
    assert trigger.condition(hit_event)
    trigger.create_triggered_event(hit_event)

    # Counter should be in card.counters dict (visible to effect engine)
    assert "defense" in eq.counters, "Counter should be in card.counters dict"
    assert eq.counters["defense"] == -1

    # Effect engine should see the reduced defense
    effective = game.effect_engine.get_modified_defense(state, eq)
    assert effective == 1, f"Expected defense 1 (base 2 + counter -1), got {effective}"


def test_art_of_dragon_scale_counter_destroys_at_zero():
    """Equipment with 1 defense should be destroyed after -1 counter."""
    from htc.cards.abilities.ninja import _ArtOfDragonScaleHitTrigger

    game = make_game_shell(life=20)
    state = game.state

    eq = make_equipment(
        instance_id=50, name="Flimsy Armor", defense=1,
        subtype=SubType.CHEST, owner_index=1,
    )
    state.players[1].equipment[EquipmentSlot.CHEST] = eq

    trigger = _ArtOfDragonScaleHitTrigger(
        attack_instance_id=1,
        controller_index=0,
        target_player_index=1,
        _state=state,
        _ask=lambda d: PlayerResponse(selected_option_ids=["pass"]),
        one_shot=True,
    )

    source = make_draconic_ninja_attack(instance_id=1)
    hit_event = GameEvent(
        event_type=EventType.HIT,
        source=source,
        target_player=1,
        amount=4,
    )
    trigger.create_triggered_event(hit_event)

    # Equipment should be destroyed
    assert state.players[1].equipment[EquipmentSlot.CHEST] is None
    assert eq.zone == Zone.GRAVEYARD


# ---------------------------------------------------------------------------
# CRITICAL 3: Ambush from arsenal not restricted by Dominate
# ---------------------------------------------------------------------------


def _make_ambush_card(instance_id=40, owner_index=1):
    """Create a card with Ambush keyword for testing."""
    defn = CardDefinition(
        unique_id=f"ambush-{instance_id}",
        name="Ambush Card",
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
        supertypes=frozenset(),
        keywords=frozenset({Keyword.AMBUSH}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.ARSENAL,
    )


def _make_dominate_attack(instance_id=1, owner_index=0):
    """Create an attack with Dominate keyword."""
    defn = CardDefinition(
        unique_id=f"dominate-{instance_id}",
        name="Dominate Attack",
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
        keywords=frozenset({Keyword.DOMINATE}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def test_ambush_from_arsenal_allowed_alongside_hand_card_against_dominate():
    """Ambush card from arsenal should defend even when Dominate limits hand cards to 1.

    Per user ruling: cards from arsenal are NOT restricted by Dominate.
    The defender should be able to play 1 hand card + Ambush from arsenal.
    """
    game = make_game_shell(life=20)
    state = game.state

    # Set up Dominate attack on combat chain
    game.combat_mgr.open_chain(state)
    dominate_attack = _make_dominate_attack(instance_id=1)
    link = game.combat_mgr.add_chain_link(state, dominate_attack, 1)

    # Defender (player 1) has a hand card and an Ambush card in arsenal
    hand_card = make_card(
        instance_id=30, name="Hand Defender", power=None, defense=2,
        is_attack=False, owner_index=1, zone=Zone.HAND,
    )
    state.players[1].hand.append(hand_card)

    ambush_card = _make_ambush_card(instance_id=40, owner_index=1)
    state.players[1].arsenal.append(ambush_card)

    # Mock ask: select both the hand card and the ambush card
    def mock_ask(decision):
        return PlayerResponse(
            selected_option_ids=[f"defend_{hand_card.instance_id}", f"defend_{ambush_card.instance_id}"]
        )

    game._ask = mock_ask

    # Run the defend step logic
    game._defend_step()

    # Both cards should be defending
    assert hand_card in link.defending_cards, "Hand card should be defending"
    assert ambush_card in link.defending_cards, "Ambush card from arsenal should also defend"
    assert len(link.defending_cards) == 2


def test_ambush_from_arsenal_not_counted_as_hand_defense():
    """Ambush cards from arsenal should NOT increment hand_cards_defended counter.

    This means a second hand card should still be blocked by Dominate,
    but the Ambush card itself is always allowed.
    """
    game = make_game_shell(life=20)
    state = game.state

    game.combat_mgr.open_chain(state)
    dominate_attack = _make_dominate_attack(instance_id=1)
    link = game.combat_mgr.add_chain_link(state, dominate_attack, 1)

    # Defender (player 1) has 2 hand cards and 1 Ambush
    hand1 = make_card(
        instance_id=30, name="Hand Card 1", power=None, defense=2,
        is_attack=False, owner_index=1, zone=Zone.HAND,
    )
    hand2 = make_card(
        instance_id=31, name="Hand Card 2", power=None, defense=2,
        is_attack=False, owner_index=1, zone=Zone.HAND,
    )
    state.players[1].hand.extend([hand1, hand2])

    ambush_card = _make_ambush_card(instance_id=40, owner_index=1)
    state.players[1].arsenal.append(ambush_card)

    # Try to defend with all 3
    def mock_ask(decision):
        return PlayerResponse(
            selected_option_ids=[
                f"defend_{hand1.instance_id}",
                f"defend_{hand2.instance_id}",
                f"defend_{ambush_card.instance_id}",
            ]
        )

    game._ask = mock_ask
    game._defend_step()

    # Dominate should block hand2, but ambush is allowed
    assert hand1 in link.defending_cards, "First hand card should defend"
    assert hand2 not in link.defending_cards, "Second hand card blocked by Dominate"
    assert ambush_card in link.defending_cards, "Ambush from arsenal always allowed"
    assert len(link.defending_cards) == 2


# ---------------------------------------------------------------------------
# Damage prevention edge cases (DEAL_DAMAGE vs LOSE_LIFE distinction)
# ---------------------------------------------------------------------------


class _DamagePreventionEffect(ReplacementEffect):
    """A ReplacementEffect that cancels all DEAL_DAMAGE events (simulating
    complete damage prevention, e.g. Arcane Barrier preventing all damage)."""

    def __init__(self):
        super().__init__(one_shot=False)

    def condition(self, event: GameEvent) -> bool:
        return event.event_type == EventType.DEAL_DAMAGE

    def replace(self, event: GameEvent) -> GameEvent:
        event.amount = 0
        event.cancelled = True
        return event


def test_kiss_of_death_life_loss_bypasses_damage_prevention():
    """Kiss of Death uses LOSE_LIFE, not DEAL_DAMAGE — damage prevention
    should NOT prevent the life loss.

    This is the core design reason for routing Kiss of Death through
    LOSE_LIFE instead of DEAL_DAMAGE.
    """
    from htc.cards.abilities.assassin import _kiss_of_death_on_hit

    game = make_game_shell(life=20)
    state = game.state

    # Register a blanket damage prevention effect
    game.events.register_replacement(_DamagePreventionEffect())

    # Set up combat chain
    game.combat_mgr.open_chain(state)
    attack = make_dagger_attack(
        instance_id=1, name="Kiss of Death",
        keywords=frozenset({Keyword.STEALTH}),
    )
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    ctx = _make_ctx(game, attack, link)
    initial_life = state.players[1].life_total
    _kiss_of_death_on_hit(ctx)

    # Life loss should go through despite damage prevention
    assert state.players[1].life_total == initial_life - 1, (
        "Kiss of Death's LOSE_LIFE should bypass damage prevention"
    )


def test_throw_dagger_no_draw_when_damage_prevented():
    """Throw Dagger: if damage is prevented (actual_damage == 0), no card
    should be drawn."""
    from htc.cards.abilities.ninja import _throw_dagger

    game = make_game_shell(life=20)
    state = game.state

    # Register blanket damage prevention
    game.events.register_replacement(_DamagePreventionEffect())

    game.combat_mgr.open_chain(state)
    active_attack = make_draconic_ninja_attack(instance_id=1)
    link = game.combat_mgr.add_chain_link(state, active_attack, 1)
    link.attack_source = active_attack

    off_dagger = make_dagger_weapon(instance_id=200, name="Off-Chain Dagger")
    state.players[0].weapons.append(off_dagger)

    # Give player 0 a card in deck so draw would succeed if attempted
    deck_card = make_card(instance_id=300, name="Deck Card", owner_index=0, zone=Zone.DECK)
    state.players[0].deck.append(deck_card)

    initial_hand_size = len(state.players[0].hand)
    initial_life = state.players[1].life_total

    ar_card = make_ninja_attack(instance_id=10, name="Throw Dagger")
    ctx = _make_ctx(game, ar_card, link)
    _throw_dagger(ctx)

    # Damage was prevented: no life lost
    assert state.players[1].life_total == initial_life, (
        "Throw Dagger damage should be prevented"
    )
    # No card drawn because damage was prevented
    assert len(state.players[0].hand) == initial_hand_size, (
        "Throw Dagger should NOT draw a card when damage is prevented"
    )
    # Dagger should still be destroyed (card text says "Destroy the dagger" unconditionally)
    assert off_dagger not in state.players[0].weapons, (
        "Dagger should be destroyed regardless of prevention"
    )


def test_blood_runs_deep_partial_prevention():
    """Blood Runs Deep: if one dagger's damage is prevented but the other's
    isn't, only one HIT event should fire."""
    from htc.cards.abilities.ninja import _blood_runs_deep_on_attack

    game = make_game_shell(life=20)
    state = game.state

    game.combat_mgr.open_chain(state)
    attack = make_draconic_ninja_attack(
        instance_id=1, name="Blood Runs Deep", power=5,
    )
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    dagger1 = make_dagger_weapon(instance_id=100, name="Dagger A")
    dagger2 = make_dagger_weapon(instance_id=101, name="Dagger B")
    state.players[0].weapons.extend([dagger1, dagger2])

    # Register a one-shot prevention that blocks the first DEAL_DAMAGE only
    class _OneTimePrevention(ReplacementEffect):
        def __init__(self):
            super().__init__(one_shot=True)

        def condition(self, event: GameEvent) -> bool:
            return event.event_type == EventType.DEAL_DAMAGE

        def replace(self, event: GameEvent) -> GameEvent:
            event.amount = 0
            event.cancelled = True
            return event

    game.events.register_replacement(_OneTimePrevention())

    damage_events = []
    hit_events = []
    game.events.register_handler(EventType.DEAL_DAMAGE, lambda e: damage_events.append(e))
    game.events.register_handler(EventType.HIT, lambda e: hit_events.append(e))

    initial_life = state.players[1].life_total
    ctx = _make_ctx(game, attack, link)
    _blood_runs_deep_on_attack(ctx)

    # First dagger's damage was prevented (cancelled), second goes through
    assert len(hit_events) == 1, (
        f"Expected 1 HIT event (one dagger prevented), got {len(hit_events)}"
    )
    assert state.players[1].life_total == initial_life - 1, (
        "Only one dagger's damage should have gone through"
    )
    # Both daggers should still be destroyed
    assert dagger1 not in state.players[0].weapons
    assert dagger2 not in state.players[0].weapons


def test_art_of_dragon_fire_damage_prevented():
    """Art of the Dragon: Fire — if the 2 damage is prevented, it shouldn't
    go through."""
    from htc.cards.abilities.ninja import _art_of_the_dragon_fire_on_attack

    game = make_game_shell(life=20)
    state = game.state

    # Register blanket damage prevention
    game.events.register_replacement(_DamagePreventionEffect())

    game.combat_mgr.open_chain(state)
    attack = make_draconic_ninja_attack(
        instance_id=1, name="Art of the Dragon: Fire", power=3,
    )
    link = game.combat_mgr.add_chain_link(state, attack, 1)

    initial_life = state.players[1].life_total
    ctx = _make_ctx(game, attack, link)
    _art_of_the_dragon_fire_on_attack(ctx)

    assert state.players[1].life_total == initial_life, (
        "Art of the Dragon: Fire damage should be fully prevented"
    )


# ---------------------------------------------------------------------------
# Ambush + Overpower interaction from arsenal
# ---------------------------------------------------------------------------


def _make_overpower_attack(instance_id=1, owner_index=0):
    """Create an attack with Overpower keyword."""
    defn = CardDefinition(
        unique_id=f"overpower-{instance_id}",
        name="Overpower Attack",
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
        keywords=frozenset({Keyword.OVERPOWER}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


def test_ambush_from_arsenal_bypasses_overpower():
    """Ambush card from arsenal should defend even when Overpower limits
    action cards from hand to 1.

    Overpower says "can't be defended by more than 1 action card from hand".
    Arsenal is not hand, so Ambush cards from arsenal are not restricted.
    """
    game = make_game_shell(life=20)
    state = game.state

    game.combat_mgr.open_chain(state)
    overpower_attack = _make_overpower_attack(instance_id=1)
    link = game.combat_mgr.add_chain_link(state, overpower_attack, 1)

    # Defender (player 1) has an action card in hand and an Ambush action in arsenal
    hand_action = make_card(
        instance_id=30, name="Hand Action", power=None, defense=2,
        is_attack=False, owner_index=1, zone=Zone.HAND,
    )
    state.players[1].hand.append(hand_action)

    ambush_card = _make_ambush_card(instance_id=40, owner_index=1)
    state.players[1].arsenal.append(ambush_card)

    def mock_ask(decision):
        return PlayerResponse(
            selected_option_ids=[
                f"defend_{hand_action.instance_id}",
                f"defend_{ambush_card.instance_id}",
            ]
        )

    game._ask = mock_ask
    game._defend_step()

    # Both should defend: Overpower only restricts hand cards
    assert hand_action in link.defending_cards, "Hand action card should defend"
    assert ambush_card in link.defending_cards, (
        "Ambush from arsenal should bypass Overpower restriction"
    )
    assert len(link.defending_cards) == 2
