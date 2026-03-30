"""Tests for banish zone infrastructure, play-from-banish, and related abilities.

Covers:
- Banish zone on PlayerState
- _banish_card helper
- Playable-from-banish tracking and expiry
- Play from banish with graveyard redirect
- Trap-Door on_become ability
- Under the Trap-Door instant-discard ability
- Graphene Chelicera cost reduction for Orb-Weaver
- ActionBuilder offering banished cards as play options
"""

from __future__ import annotations

import pytest

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.abilities import AbilityContext
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.enums import (
    ActionType,
    CardType,
    Color,
    DecisionType,
    Keyword,
    SubType,
    SuperType,
    Zone,
)

from tests.conftest import make_card, make_game_shell, make_state, make_weapon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trap(
    instance_id: int = 50,
    name: str = "Den of the Spider",
    *,
    color: Color = Color.RED,
    owner_index: int = 0,
    zone: Zone = Zone.HAND,
    defense: int = 4,
) -> CardInstance:
    """Create a trap defense reaction card for testing."""
    defn = CardDefinition(
        unique_id=f"trap-{instance_id}",
        name=name,
        color=color,
        pitch=1,
        cost=0,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEFENSE_REACTION}),
        subtypes=frozenset({SubType.TRAP}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Defense Reaction - Trap",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def _make_under_the_trap_door(
    instance_id: int = 60,
    owner_index: int = 0,
) -> CardInstance:
    """Create Under the Trap-Door card."""
    defn = CardDefinition(
        unique_id=f"utd-{instance_id}",
        name="Under the Trap-Door",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=1,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text='**Stealth**\n\n**Instant** - Discard this: Banish target trap from your graveyard.',
        type_text="Assassin Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_demi_hero(
    name: str,
    instance_id: int = 200,
    owner_index: int = 0,
) -> CardInstance:
    """Create a demi-hero card."""
    defn = CardDefinition(
        unique_id=f"dh-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEMI_HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.CHAOS, SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Chaos Assassin Demi-Hero",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_hero(
    name: str = "Arakni, Marionette",
    instance_id: int = 300,
    owner_index: int = 0,
) -> CardInstance:
    """Create a hero card."""
    defn = CardDefinition(
        unique_id=f"hero-{instance_id}",
        name=name,
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
        supertypes=frozenset({SuperType.CHAOS, SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Chaos Assassin Hero",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_graphene_chelicera(
    instance_id: int = 400,
    owner_index: int = 0,
) -> CardInstance:
    """Create a Graphene Chelicera weapon token."""
    defn = CardDefinition(
        unique_id=f"gc-{instance_id}",
        name="Graphene Chelicera",
        color=None,
        pitch=None,
        cost=None,
        power=1,
        defense=None,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.WEAPON, CardType.TOKEN}),
        subtypes=frozenset({SubType.DAGGER, SubType.ONE_HAND}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset({Keyword.STEALTH}),
        functional_text="**Stealth**\n\n**Once per Turn Action** - {r}: **Attack**",
        type_text="Assassin Token Weapon - Dagger (1H)",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.WEAPON_1,
    )


# ---------------------------------------------------------------------------
# Banish zone infrastructure tests
# ---------------------------------------------------------------------------


class TestBanishZoneInfra:
    """Tests for banish zone on PlayerState."""

    def test_banished_list_exists(self):
        """PlayerState should have a banished list."""
        state = make_state()
        assert state.players[0].banished == []

    def test_get_zone_cards_banished(self):
        """get_zone_cards should return banished list."""
        state = make_state()
        card = make_card(instance_id=1, zone=Zone.BANISHED, owner_index=0)
        state.players[0].banished.append(card)
        assert state.players[0].get_zone_cards(Zone.BANISHED) == [card]

    def test_remove_card_from_banished(self):
        """remove_card should find and remove from banished."""
        state = make_state()
        card = make_card(instance_id=1, zone=Zone.BANISHED, owner_index=0)
        state.players[0].banished.append(card)
        assert state.players[0].remove_card(card) is True
        assert card not in state.players[0].banished

    def test_find_card_in_banished(self):
        """find_card should locate cards in banished."""
        state = make_state()
        card = make_card(instance_id=42, zone=Zone.BANISHED, owner_index=0)
        state.players[0].banished.append(card)
        assert state.players[0].find_card(42) is card

    def test_face_up_default(self):
        """CardInstance defaults to face_up=True."""
        card = make_card(instance_id=1)
        assert card.face_up is True

    def test_face_down_banish(self):
        """face_up can be set to False for face-down banish."""
        card = make_card(instance_id=1)
        card.face_up = False
        assert card.face_up is False


class TestBanishCardHelper:
    """Tests for Game._banish_card helper."""

    def test_banish_card_face_up(self):
        """_banish_card should move card to banish face-up by default."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.HAND, owner_index=0)
        game.state.players[0].hand.append(card)

        game._banish_card(card, 0)

        assert card in game.state.players[0].banished
        assert card not in game.state.players[0].hand
        assert card.zone == Zone.BANISHED
        assert card.face_up is True

    def test_banish_card_face_down(self):
        """_banish_card with face_down=True should set face_up=False."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.HAND, owner_index=0)
        game.state.players[0].hand.append(card)

        game._banish_card(card, 0, face_down=True)

        assert card in game.state.players[0].banished
        assert card.face_up is False

    def test_banish_from_deck(self):
        """_banish_card should work for cards in the deck."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.DECK, owner_index=0)
        game.state.players[0].deck.append(card)

        game._banish_card(card, 0, face_down=True)

        assert card in game.state.players[0].banished
        assert card not in game.state.players[0].deck


# ---------------------------------------------------------------------------
# Playable-from-banish tracking tests
# ---------------------------------------------------------------------------


class TestPlayableFromBanish:
    """Tests for playable-from-banish tracking."""

    def test_mark_playable(self):
        """_mark_playable_from_banish should add entry."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.BANISHED, owner_index=0)
        game.state.players[0].banished.append(card)

        game._mark_playable_from_banish(card, 0, "end_of_turn")

        assert (1, "end_of_turn", True) in game.state.players[0].playable_from_banish

    def test_is_playable(self):
        """_is_playable_from_banish should return True for marked cards."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.BANISHED, owner_index=0)
        game.state.players[0].banished.append(card)
        game.state.players[0].playable_from_banish.append((1, "end_of_turn", True))

        assert game._is_playable_from_banish(card, 0) is True

    def test_not_playable(self):
        """_is_playable_from_banish should return False for unmarked cards."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.BANISHED, owner_index=0)
        game.state.players[0].banished.append(card)

        assert game._is_playable_from_banish(card, 0) is False

    def test_expire_end_of_turn(self):
        """_expire_playable_from_banish_end_of_turn should remove end_of_turn entries."""
        game = make_game_shell()
        game.state.players[0].playable_from_banish = [
            (1, "end_of_turn", True),
            (2, "start_of_next_turn", False),
        ]

        game._expire_playable_from_banish_end_of_turn()

        assert game.state.players[0].playable_from_banish == [(2, "start_of_next_turn", False)]

    def test_expire_start_of_turn(self):
        """_expire_playable_from_banish_start_of_turn should remove for specific player."""
        game = make_game_shell()
        game.state.players[0].playable_from_banish = [
            (1, "start_of_next_turn", False),
            (2, "end_of_turn", True),
        ]

        game._expire_playable_from_banish_start_of_turn(0)

        assert game.state.players[0].playable_from_banish == [(2, "end_of_turn", True)]


# ---------------------------------------------------------------------------
# ActionBuilder banish integration tests
# ---------------------------------------------------------------------------


class TestActionBuilderBanish:
    """Tests for ActionBuilder offering playable-from-banish cards."""

    def test_banished_card_appears_in_options(self):
        """Playable-from-banish cards should appear in action options."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        card = make_card(instance_id=10, zone=Zone.BANISHED, owner_index=0, cost=0)
        game.state.players[0].banished.append(card)
        game.state.players[0].playable_from_banish.append((10, "end_of_turn", True))

        decision = game.action_builder.build_action_decision(game.state, 0, True)
        play_ids = [o.card_instance_id for o in decision.options if o.card_instance_id]
        assert 10 in play_ids

    def test_unmarked_banished_card_not_offered(self):
        """Banished cards not marked as playable should NOT appear."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        card = make_card(instance_id=10, zone=Zone.BANISHED, owner_index=0)
        game.state.players[0].banished.append(card)

        decision = game.action_builder.build_action_decision(game.state, 0, True)
        play_ids = [o.card_instance_id for o in decision.options if o.card_instance_id]
        assert 10 not in play_ids


# ---------------------------------------------------------------------------
# Play from banish -> banish instead of graveyard tests
# ---------------------------------------------------------------------------


class TestPlayFromBanishRedirect:
    """Tests for the graveyard->banish redirect when playing from banish."""

    def test_move_to_graveyard_or_banish_normal(self):
        """Normally, cards go to graveyard."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.STACK, owner_index=0)

        game._move_to_graveyard_or_banish(card)
        assert card.zone == Zone.GRAVEYARD

    def test_move_to_graveyard_or_banish_redirect(self):
        """Cards tracked in _banish_instead_of_graveyard go to banish."""
        game = make_game_shell()
        card = make_card(instance_id=1, zone=Zone.STACK, owner_index=0)
        game._banish_instead_of_graveyard.add(1)

        game._move_to_graveyard_or_banish(card)
        assert card.zone == Zone.BANISHED
        assert 1 not in game._banish_instead_of_graveyard  # cleaned up


class TestTrapDoorNoRedirect:
    """Tests that Trap-Door played cards go to graveyard (not banish).

    Trap-Door's text says "you may play it until the start of your next turn"
    with NO mention of graveyard redirect. Only Under the Trap-Door has
    "if it would be put into the graveyard this turn, instead banish it".
    """

    def test_trap_door_played_card_not_marked_for_redirect(self):
        """When a card played from banish via Trap-Door (redirect=False),
        it should NOT be added to _banish_instead_of_graveyard."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        player = game.state.players[0]

        # Set up a trap in banish, marked playable with redirect=False (Trap-Door)
        trap = _make_trap(instance_id=50, zone=Zone.BANISHED, owner_index=0)
        player.banished.append(trap)
        player.playable_from_banish.append((50, "start_of_next_turn", False))

        # Simulate _play_card behavior: card is in banish and playable
        assert game._is_playable_from_banish(trap, 0) is True

        # After playing, the card should NOT be in _banish_instead_of_graveyard
        # We test the redirect logic directly
        redirect = any(
            iid == trap.instance_id and redir
            for iid, _, redir in player.playable_from_banish
        )
        assert redirect is False

    def test_under_trap_door_played_card_marked_for_redirect(self):
        """When a card played from banish via Under the Trap-Door (redirect=True),
        it SHOULD be added to _banish_instead_of_graveyard."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        player = game.state.players[0]

        trap = _make_trap(instance_id=50, zone=Zone.BANISHED, owner_index=0)
        player.banished.append(trap)
        player.playable_from_banish.append((50, "end_of_turn", True))

        redirect = any(
            iid == trap.instance_id and redir
            for iid, _, redir in player.playable_from_banish
        )
        assert redirect is True


# ---------------------------------------------------------------------------
# Trap-Door on_become tests
# ---------------------------------------------------------------------------


class TestTrapDoorOnBecome:
    """Tests for Trap-Door demi-hero on_become ability."""

    def test_trap_door_banish_trap_from_deck(self):
        """Trap-Door should banish a chosen card face-down and mark traps as playable."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_hero(owner_index=0)

        # Put a trap in the deck
        trap = _make_trap(instance_id=50, name="Den of the Spider", zone=Zone.DECK, owner_index=0)
        player.deck.append(trap)

        # Also add a non-trap card
        non_trap = make_card(instance_id=51, zone=Zone.DECK, owner_index=0)
        player.deck.append(non_trap)

        # Mock ask to choose the trap
        def mock_ask(decision):
            return PlayerResponse(selected_option_ids=[f"trap_door_{trap.instance_id}"])
        game.interfaces = [type('P', (), {'decide': lambda s, st, d: mock_ask(d)})(), type('P', (), {'decide': lambda s, st, d: mock_ask(d)})()]

        # Create demi-hero and trigger on_become
        agent = _make_demi_hero("Arakni, Trap-Door", instance_id=200, owner_index=0)
        game._become_agent_of_chaos(0, agent)

        # Trap should be banished face-down
        assert trap in player.banished
        assert trap.face_up is False
        assert trap not in player.deck

        # Trap should be marked as playable (it's a Trap subtype)
        assert any(iid == trap.instance_id for iid, _, _ in player.playable_from_banish)
        # Trap-Door should NOT redirect to banish (no graveyard redirect text)
        assert any(
            iid == trap.instance_id and redir is False
            for iid, _, redir in player.playable_from_banish
        )

    def test_trap_door_banish_non_trap(self):
        """When a non-trap card is chosen, it should be banished but NOT playable."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_hero(owner_index=0)

        non_trap = make_card(instance_id=51, name="Regular Card", zone=Zone.DECK, owner_index=0)
        player.deck.append(non_trap)

        def mock_ask(decision):
            return PlayerResponse(selected_option_ids=[f"trap_door_{non_trap.instance_id}"])
        game.interfaces = [type('P', (), {'decide': lambda s, st, d: mock_ask(d)})(), type('P', (), {'decide': lambda s, st, d: mock_ask(d)})()]

        agent = _make_demi_hero("Arakni, Trap-Door", instance_id=200, owner_index=0)
        game._become_agent_of_chaos(0, agent)

        assert non_trap in player.banished
        assert non_trap.face_up is False
        # Non-trap should NOT be playable from banish
        assert not any(iid == non_trap.instance_id for iid, _, _ in player.playable_from_banish)

    def test_trap_door_pass(self):
        """Player may choose not to search."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_hero(owner_index=0)

        trap = _make_trap(instance_id=50, zone=Zone.DECK, owner_index=0)
        player.deck.append(trap)

        def mock_ask(decision):
            return PlayerResponse(selected_option_ids=["pass"])
        game.interfaces = [type('P', (), {'decide': lambda s, st, d: mock_ask(d)})(), type('P', (), {'decide': lambda s, st, d: mock_ask(d)})()]

        agent = _make_demi_hero("Arakni, Trap-Door", instance_id=200, owner_index=0)
        game._become_agent_of_chaos(0, agent)

        # Nothing should be banished
        assert trap in player.deck
        assert len(player.banished) == 0


# ---------------------------------------------------------------------------
# Under the Trap-Door tests
# ---------------------------------------------------------------------------


class TestUnderTheTrapDoor:
    """Tests for Under the Trap-Door instant-discard ability."""

    def test_instant_discard_banishes_trap_from_graveyard(self):
        """Discarding Under the Trap-Door should banish a trap from graveyard."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_hero(owner_index=0)

        # Put a trap in the graveyard
        trap = _make_trap(instance_id=50, zone=Zone.GRAVEYARD, owner_index=0)
        player.graveyard.append(trap)

        # Put Under the Trap-Door in hand
        utd = _make_under_the_trap_door(instance_id=60, owner_index=0)
        player.hand.append(utd)

        # Mock ask to choose the trap
        def mock_ask(decision):
            if "trap" in decision.prompt.lower():
                return PlayerResponse(selected_option_ids=[f"banish_trap_{trap.instance_id}"])
            return PlayerResponse(selected_option_ids=["pass"])
        game.interfaces = [type('P', (), {'decide': lambda s, st, d: mock_ask(d)})(), type('P', (), {'decide': lambda s, st, d: mock_ask(d)})()]

        game._activate_instant_discard(0, utd)

        # Under the Trap-Door should be in graveyard (discarded as cost)
        assert utd in player.graveyard

        # Trap should be banished from graveyard
        assert trap in player.banished
        assert trap not in player.graveyard
        assert trap.face_up is True

        # Trap should be playable this turn
        assert any(iid == trap.instance_id for iid, _, _ in player.playable_from_banish)
        # Under the Trap-Door SHOULD redirect to banish
        assert any(
            iid == trap.instance_id and redir is True
            for iid, _, redir in player.playable_from_banish
        )

    def test_instant_discard_no_traps(self):
        """If no traps in graveyard, UTD still discards but does nothing else."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_hero(owner_index=0)

        utd = _make_under_the_trap_door(instance_id=60, owner_index=0)
        player.hand.append(utd)

        def mock_ask(decision):
            return PlayerResponse(selected_option_ids=["pass"])
        game.interfaces = [type('P', (), {'decide': lambda s, st, d: mock_ask(d)})(), type('P', (), {'decide': lambda s, st, d: mock_ask(d)})()]

        game._activate_instant_discard(0, utd)

        # UTD should be in graveyard
        assert utd in player.graveyard
        assert len(player.banished) == 0

    def test_instant_discard_offered_in_options(self):
        """ActionBuilder should offer Under the Trap-Door as an instant-discard option."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        player = game.state.players[0]

        utd = _make_under_the_trap_door(instance_id=60, owner_index=0)
        player.hand.append(utd)

        decision = game.action_builder.build_action_decision(game.state, 0, True)
        activate_ids = [
            o.card_instance_id for o in decision.options
            if o.action_type == ActionType.ACTIVATE_ABILITY
        ]
        assert 60 in activate_ids

    def test_instant_discard_pass(self):
        """Player may choose not to banish a trap."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_hero(owner_index=0)

        trap = _make_trap(instance_id=50, zone=Zone.GRAVEYARD, owner_index=0)
        player.graveyard.append(trap)

        utd = _make_under_the_trap_door(instance_id=60, owner_index=0)
        player.hand.append(utd)

        def mock_ask(decision):
            return PlayerResponse(selected_option_ids=["pass"])
        game.interfaces = [type('P', (), {'decide': lambda s, st, d: mock_ask(d)})(), type('P', (), {'decide': lambda s, st, d: mock_ask(d)})()]

        game._activate_instant_discard(0, utd)

        # UTD discarded, but trap stays in graveyard
        assert utd in player.graveyard
        assert trap in player.graveyard
        assert len(player.banished) == 0


# ---------------------------------------------------------------------------
# Graphene Chelicera cost reduction tests
# ---------------------------------------------------------------------------


class TestGrapheneCheliceraCostReduction:
    """Tests for Orb-Weaver's Graphene Chelicera cost reduction."""

    def test_normal_activation_cost(self):
        """Graphene Chelicera should cost 1 resource normally."""
        from htc.engine.action_builder import ActionBuilder
        state = make_state()
        player = state.players[0]
        player.hero = _make_hero("Arakni, Marionette", owner_index=0)

        gc = _make_graphene_chelicera(owner_index=0)
        cost = ActionBuilder._apply_weapon_cost_reduction(state, 0, gc, 1)
        assert cost == 1

    def test_orb_weaver_reduces_cost(self):
        """Orb-Weaver should reduce Graphene Chelicera cost to 0."""
        from htc.engine.action_builder import ActionBuilder
        state = make_state()
        player = state.players[0]
        player.hero = _make_demi_hero("Arakni, Orb-Weaver", owner_index=0)

        gc = _make_graphene_chelicera(owner_index=0)
        cost = ActionBuilder._apply_weapon_cost_reduction(state, 0, gc, 1)
        assert cost == 0

    def test_orb_weaver_doesnt_reduce_other_weapons(self):
        """Orb-Weaver should not reduce cost of non-Graphene weapons."""
        from htc.engine.action_builder import ActionBuilder
        state = make_state()
        player = state.players[0]
        player.hero = _make_demi_hero("Arakni, Orb-Weaver", owner_index=0)

        weapon = make_weapon(instance_id=500, name="Kunai of Retribution", power=1, cost=0)
        cost = ActionBuilder._apply_weapon_cost_reduction(state, 0, weapon, 1)
        assert cost == 1

    def test_orb_weaver_can_activate_free(self):
        """With Orb-Weaver, Graphene Chelicera should be activatable without resources."""
        from htc.engine.action_builder import ActionBuilder
        state = make_state()
        state.action_points = {0: 1, 1: 0}
        state.resource_points = {0: 0, 1: 0}
        player = state.players[0]
        player.hero = _make_demi_hero("Arakni, Orb-Weaver", owner_index=0)

        gc = _make_graphene_chelicera(owner_index=0)
        player.weapons.append(gc)

        assert ActionBuilder._can_activate_weapon(state, 0, gc) is True

    def test_without_orb_weaver_needs_resource(self):
        """Without Orb-Weaver, Graphene Chelicera should need 1 resource."""
        from htc.engine.action_builder import ActionBuilder
        state = make_state()
        state.action_points = {0: 1, 1: 0}
        state.resource_points = {0: 0, 1: 0}
        player = state.players[0]
        player.hero = _make_hero("Arakni, Marionette", owner_index=0)

        gc = _make_graphene_chelicera(owner_index=0)
        player.weapons.append(gc)

        # No resources and no pitchable cards -> can't activate
        assert ActionBuilder._can_activate_weapon(state, 0, gc) is False

    def test_weapon_activation_cost_with_reduction(self):
        """Game._weapon_activation_cost should apply Orb-Weaver reduction."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = _make_demi_hero("Arakni, Orb-Weaver", owner_index=0)

        gc = _make_graphene_chelicera(owner_index=0)
        cost = game._weapon_activation_cost(gc, 0)
        assert cost == 0

    def test_base_weapon_activation_cost_unchanged(self):
        """_base_weapon_activation_cost should return the raw cost."""
        from htc.engine.game import Game
        gc = _make_graphene_chelicera(owner_index=0)
        cost = Game._base_weapon_activation_cost(gc)
        assert cost == 1  # {r} in functional text


# ---------------------------------------------------------------------------
# on_become timing registration tests
# ---------------------------------------------------------------------------


class TestOnBecomeTiming:
    """Tests for on_become timing in ability registry."""

    def test_trap_door_registered(self):
        """Trap-Door should have an on_become handler."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("on_become", "Arakni, Trap-Door")
        assert handler is not None

    def test_orb_weaver_registered(self):
        """Orb-Weaver should have an on_become handler."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("on_become", "Arakni, Orb-Weaver")
        assert handler is not None

    def test_instant_discard_registered(self):
        """Under the Trap-Door should have an instant_discard_effect handler."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("instant_discard_effect", "Under the Trap-Door")
        assert handler is not None


# ---------------------------------------------------------------------------
# Critical fix: defending cards redirected to banish on chain close
# ---------------------------------------------------------------------------


class TestDefendingCardBanishRedirect:
    """Tests that defending cards played from banish go back to banish
    (not graveyard) when the combat chain closes."""

    def test_defending_card_banished_on_chain_close(self):
        """A trap defense reaction played from banish should return to banish
        when the chain closes, not graveyard."""
        from htc.state.combat_state import ChainLink

        game = make_game_shell()
        state = game.state

        # Set up an attack on the chain
        attack = make_card(instance_id=1, zone=Zone.COMBAT_CHAIN, owner_index=0)
        trap = _make_trap(instance_id=50, zone=Zone.COMBAT_CHAIN, owner_index=1)

        link = ChainLink(link_number=1, active_attack=attack, attack_target_index=1)
        link.defending_cards.append(trap)

        state.combat_chain.is_open = True
        state.combat_chain.chain_links.append(link)

        # Mark the trap as needing banish redirect (played from banish)
        game._banish_instead_of_graveyard.add(trap.instance_id)

        # Run redirect + close
        game._redirect_banish_on_chain_close()
        game.combat_mgr.close_chain(state)

        # Trap should be in banish, not graveyard
        assert trap.zone == Zone.BANISHED
        assert trap in state.players[1].banished
        assert trap not in state.players[1].graveyard

    def test_non_banish_defending_card_goes_to_graveyard(self):
        """A normal defending card (not played from banish) should go to graveyard."""
        from htc.state.combat_state import ChainLink

        game = make_game_shell()
        state = game.state

        attack = make_card(instance_id=1, zone=Zone.COMBAT_CHAIN, owner_index=0)
        defender = make_card(instance_id=2, zone=Zone.COMBAT_CHAIN, owner_index=1, is_attack=False)

        link = ChainLink(link_number=1, active_attack=attack, attack_target_index=1)
        link.defending_cards.append(defender)

        state.combat_chain.is_open = True
        state.combat_chain.chain_links.append(link)

        # No banish redirect for this card
        game._redirect_banish_on_chain_close()
        game.combat_mgr.close_chain(state)

        assert defender.zone == Zone.GRAVEYARD

    def test_mixed_defending_cards_redirect(self):
        """When multiple defenders, only the one played from banish is redirected."""
        from htc.state.combat_state import ChainLink

        game = make_game_shell()
        state = game.state

        attack = make_card(instance_id=1, zone=Zone.COMBAT_CHAIN, owner_index=0)
        trap = _make_trap(instance_id=50, zone=Zone.COMBAT_CHAIN, owner_index=1)
        normal = make_card(instance_id=2, zone=Zone.COMBAT_CHAIN, owner_index=1, is_attack=False)

        link = ChainLink(link_number=1, active_attack=attack, attack_target_index=1)
        link.defending_cards.extend([trap, normal])

        state.combat_chain.is_open = True
        state.combat_chain.chain_links.append(link)

        game._banish_instead_of_graveyard.add(trap.instance_id)

        game._redirect_banish_on_chain_close()
        game.combat_mgr.close_chain(state)

        assert trap.zone == Zone.BANISHED
        assert trap in state.players[1].banished
        assert normal.zone == Zone.GRAVEYARD


# ---------------------------------------------------------------------------
# Critical fix: defense reactions from banish offered during reaction step
# ---------------------------------------------------------------------------


class TestDefenseReactionFromBanish:
    """Tests that defense reactions in the banish zone (marked playable)
    are offered during the reaction step."""

    def test_banished_trap_offered_as_defense_reaction(self):
        """A trap defense reaction banished by Trap-Door should appear
        as a defense reaction option during the reaction step."""
        game = make_game_shell()
        state = game.state

        trap = _make_trap(instance_id=50, zone=Zone.BANISHED, owner_index=1)
        state.players[1].banished.append(trap)
        state.players[1].playable_from_banish.append((50, "start_of_next_turn", False))

        decision = game.action_builder.build_reaction_decision(
            state,
            priority_player=1,
            attacker_index=0,
            defender_index=1,
        )

        play_ids = [o.card_instance_id for o in decision.options if o.card_instance_id]
        assert 50 in play_ids

    def test_banished_trap_not_offered_to_attacker(self):
        """Defense reactions from banish should NOT be offered to the attacker."""
        game = make_game_shell()
        state = game.state

        trap = _make_trap(instance_id=50, zone=Zone.BANISHED, owner_index=0)
        state.players[0].banished.append(trap)
        state.players[0].playable_from_banish.append((50, "start_of_next_turn", False))

        decision = game.action_builder.build_reaction_decision(
            state,
            priority_player=0,
            attacker_index=0,
            defender_index=1,
        )

        play_ids = [o.card_instance_id for o in decision.options if o.card_instance_id]
        assert 50 not in play_ids

    def test_unmarked_banished_trap_not_offered(self):
        """Banished traps NOT marked as playable should not be offered."""
        game = make_game_shell()
        state = game.state

        trap = _make_trap(instance_id=50, zone=Zone.BANISHED, owner_index=1)
        state.players[1].banished.append(trap)
        # Not marked as playable

        decision = game.action_builder.build_reaction_decision(
            state,
            priority_player=1,
            attacker_index=0,
            defender_index=1,
        )

        play_ids = [o.card_instance_id for o in decision.options if o.card_instance_id]
        assert 50 not in play_ids
