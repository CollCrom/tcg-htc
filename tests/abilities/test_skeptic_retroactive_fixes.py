"""Tests for skeptic retroactive audit fixes (PRs #76-83).

Covers:
1. Warmonger's Diplomacy: controller restriction survives through their next turn
2. Shelter from the Storm: expires on any END_OF_TURN, not just controller's
3. Return-to-brood: no skip_first, fires on controller's first end phase
"""

from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.rules.actions import ActionOption, Decision, PlayerResponse
from engine.rules.events import EventBus, EventType, GameEvent
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
)
from tests.abilities.conftest import (
    make_mock_interfaces,
    make_ninja_attack,
    make_dagger_weapon,
    make_non_attack_action as _make_non_attack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attack_action(
    instance_id: int = 1,
    name: str = "Test Attack",
    *,
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
    zone: Zone = Zone.HAND,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"test-{instance_id}",
        name=name,
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
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def _make_non_attack_action(
    instance_id: int = 30,
    name: str = "Non-Attack Action",
    *,
    cost: int = 0,
    owner_index: int = 0,
    zone: Zone = Zone.HAND,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"naa-{instance_id}",
        name=name,
        color=Color.BLUE,
        pitch=3,
        cost=cost,
        power=None,
        defense=2,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset(),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


# ===========================================================================
# 1. Warmonger's Diplomacy — controller restriction survives
# ===========================================================================


class TestDiplomacyControllerRestriction:
    """Controller's diplomacy restriction must survive through their next turn."""

    def test_controller_restriction_not_cleared_on_own_turn(self):
        """Restriction set on controller's turn is NOT cleared at end of that turn.

        The restriction applies to the controller's NEXT turn, so it must
        persist through the current end phase (when it's set) and the
        opponent's turn.
        """
        game = make_game_shell(action_points={0: 1, 1: 0})
        game.state.turn_number = 5  # controller's turn

        mock_ask = make_mock_ask({"Warmonger's Diplomacy": ["war"]})
        game.interfaces = make_mock_interfaces(mock_ask)

        card = _make_non_attack_action(instance_id=1, name="Warmonger's Diplomacy")
        game._apply_card_ability(card, 0, "on_play")

        # Controller (P0) chose war, restriction set
        assert game.state.players[0].diplomacy_restriction == "war"
        # Expires on turn 7 (2 turns later = controller's next turn)
        assert game.state.players[0].diplomacy_restriction_expires_turn == 7

        # Now run end phase for the controller's turn (turn 5)
        game.state.turn_player_index = 0
        game._run_end_phase()

        # Restriction must still be active — it expires on turn 7
        assert game.state.players[0].diplomacy_restriction == "war"

    def test_controller_restriction_survives_opponent_turn(self):
        """Restriction survives through the opponent's turn end phase."""
        game = make_game_shell(action_points={0: 0, 1: 0})
        game.state.turn_number = 6  # opponent's turn

        # Simulate restriction set on turn 5 (controller's previous turn)
        game.state.players[0].diplomacy_restriction = "peace"
        game.state.players[0].diplomacy_restriction_expires_turn = 7

        # Run opponent's end phase
        game.state.turn_player_index = 1
        game.interfaces = make_mock_interfaces(make_mock_ask({}))
        game._run_end_phase()

        # P0's restriction still active (it's not P0's turn)
        assert game.state.players[0].diplomacy_restriction == "peace"

    def test_controller_restriction_cleared_on_next_turn(self):
        """Restriction IS cleared at the end of the controller's next turn."""
        game = make_game_shell(action_points={0: 0, 1: 0})
        game.state.turn_number = 7  # controller's next turn

        game.state.players[0].diplomacy_restriction = "war"
        game.state.players[0].diplomacy_restriction_expires_turn = 7

        game.state.turn_player_index = 0
        game.interfaces = make_mock_interfaces(make_mock_ask({}))
        game._run_end_phase()

        assert game.state.players[0].diplomacy_restriction is None
        assert game.state.players[0].diplomacy_restriction_expires_turn is None

    def test_opponent_restriction_cleared_on_their_next_turn(self):
        """Opponent's restriction is cleared at end of their next turn."""
        game = make_game_shell(action_points={0: 0, 1: 0})
        game.state.turn_number = 6  # opponent's turn

        # Set on turn 5 (controller's turn), expires on turn 6
        game.state.players[1].diplomacy_restriction = "peace"
        game.state.players[1].diplomacy_restriction_expires_turn = 6

        game.state.turn_player_index = 1
        game.interfaces = make_mock_interfaces(make_mock_ask({}))
        game._run_end_phase()

        assert game.state.players[1].diplomacy_restriction is None
        assert game.state.players[1].diplomacy_restriction_expires_turn is None

    def test_handler_sets_correct_expiry_for_both_players(self):
        """Warmonger's Diplomacy handler sets different expiry turns for
        opponent (current+1) vs controller (current+2)."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        game.state.turn_number = 10

        mock_ask = make_mock_ask({"Warmonger's Diplomacy": ["peace"]})
        game.interfaces = make_mock_interfaces(mock_ask)

        card = _make_non_attack_action(instance_id=1, name="Warmonger's Diplomacy")
        game._apply_card_ability(card, 0, "on_play")

        # Opponent's restriction expires next turn (10+1=11)
        assert game.state.players[1].diplomacy_restriction_expires_turn == 11
        # Controller's restriction expires on their next turn (10+2=12)
        assert game.state.players[0].diplomacy_restriction_expires_turn == 12

    def test_controller_restriction_enforced_during_next_turn(self):
        """The controller's war restriction actually blocks non-attacks
        during their next turn (the restriction was not cleared early)."""
        game = make_game_shell(action_points={0: 1, 1: 0})
        game.state.turn_number = 7

        # Restriction set, expires this turn (7)
        game.state.players[0].diplomacy_restriction = "war"
        game.state.players[0].diplomacy_restriction_expires_turn = 7
        game.state.turn_player_index = 0

        # Non-attack should be blocked during this turn
        non_attack = _make_non_attack_action(instance_id=5, owner_index=0)
        game.state.players[0].hand.append(non_attack)
        assert not game.action_builder.can_play_card(game.state, 0, non_attack)

        # Attack should be allowed
        attack = _make_attack_action(instance_id=6, owner_index=0)
        attack.zone = Zone.HAND
        game.state.players[0].hand.append(attack)
        assert game.action_builder.can_play_card(game.state, 0, attack)


# ===========================================================================
# 2. Shelter from the Storm — expires on correct turn
# ===========================================================================


class TestShelterFromTheStormExpiry:
    """Shelter from the Storm prevention expires on first END_OF_TURN."""

    def test_prevention_expires_on_opponents_end_of_turn(self):
        """Prevention expires at end of the opponent's turn (the turn it was
        played), even though the controller is the defender, not the turn player."""
        game = make_game_shell(life=20)
        controller = 1  # defender

        # Register the prevention via the ability handler
        from engine.cards.abilities.generic import _shelter_from_the_storm_instant
        from tests.abilities.conftest import make_ability_context

        shelter = make_card(instance_id=99, name="Shelter from the Storm", is_attack=False)
        ctx = make_ability_context(game, shelter, controller)
        _shelter_from_the_storm_instant(ctx)

        # Verify prevention is active
        assert len(game.events._replacement_effects) == 1

        # Emit END_OF_TURN for the OPPONENT (turn player = 0, not controller 1)
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,  # opponent is the turn player
        ))

        # Prevention should be removed
        assert len(game.events._replacement_effects) == 0

    def test_prevention_works_before_expiry(self):
        """Prevention reduces damage while active."""
        game = make_game_shell(life=20)
        controller = 1

        from engine.cards.abilities.generic import _shelter_from_the_storm_instant
        from tests.abilities.conftest import make_ability_context

        shelter = make_card(instance_id=99, name="Shelter from the Storm", is_attack=False)
        ctx = make_ability_context(game, shelter, controller)
        _shelter_from_the_storm_instant(ctx)

        # Deal 5 damage to controller — should be reduced to 4
        event = game.events.emit(GameEvent(
            event_type=EventType.DEAL_DAMAGE,
            target_player=controller,
            amount=5,
        ))
        assert event.amount == 4

    def test_prevention_does_not_persist_past_turn_end(self):
        """After END_OF_TURN, prevention no longer reduces damage."""
        game = make_game_shell(life=20)
        controller = 1

        from engine.cards.abilities.generic import _shelter_from_the_storm_instant
        from tests.abilities.conftest import make_ability_context

        shelter = make_card(instance_id=99, name="Shelter from the Storm", is_attack=False)
        ctx = make_ability_context(game, shelter, controller)
        _shelter_from_the_storm_instant(ctx)

        # End the turn
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))

        # Deal damage — should NOT be reduced (prevention expired)
        event = game.events.emit(GameEvent(
            event_type=EventType.DEAL_DAMAGE,
            target_player=controller,
            amount=5,
        ))
        assert event.amount == 5


# ===========================================================================
# 3. Return-to-brood — fires on controller's first end phase
# ===========================================================================


class TestReturnToBroodTiming:
    """Return-to-brood should fire on controller's first end phase
    after transformation, not one turn late."""

    def _make_hero(self, name="Arakni, Marionette", instance_id=900):
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
            supertypes=frozenset({SuperType.ASSASSIN}),
            keywords=frozenset(),
            functional_text="",
            type_text="",
        )
        return CardInstance(
            instance_id=instance_id,
            definition=defn,
            owner_index=0,
            zone=Zone.HERO,
        )

    def _make_agent(self, name="Arakni, Black Widow", instance_id=901):
        defn = CardDefinition(
            unique_id=f"agent-{instance_id}",
            name=name,
            color=None,
            pitch=None,
            cost=None,
            power=None,
            defense=None,
            health=None,
            intellect=4,
            arcane=None,
            types=frozenset({CardType.DEMI_HERO}),
            subtypes=frozenset(),
            supertypes=frozenset({SuperType.ASSASSIN}),
            keywords=frozenset(),
            functional_text="",
            type_text="",
        )
        return CardInstance(
            instance_id=instance_id,
            definition=defn,
            owner_index=0,
            zone=Zone.HERO,
        )

    def test_reverts_on_first_controller_end_phase(self):
        """After transformation, hero reverts at end of controller's first turn."""
        game = make_game_shell()
        player = game.state.players[0]
        original_hero = self._make_hero()
        player.hero = original_hero
        agent = self._make_agent()

        # Transform
        game._become_agent_of_chaos(0, agent)
        assert player.hero == agent
        assert player.original_hero == original_hero

        # Opponent's end phase — should NOT revert
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,
        ))
        assert player.hero == agent

        # Controller's end phase — SHOULD revert
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        assert player.hero == original_hero
        assert player.original_hero is None

    def test_does_not_revert_on_opponent_end_phase(self):
        """Transformation is NOT reverted during the opponent's end phase."""
        game = make_game_shell()
        player = game.state.players[0]
        player.hero = self._make_hero()
        agent = self._make_agent()

        game._become_agent_of_chaos(0, agent)

        # Multiple opponent end phases should not revert
        for _ in range(3):
            game.events.emit(GameEvent(
                event_type=EventType.END_OF_TURN,
                target_player=1,
            ))
        assert player.hero == agent

    def test_fires_only_once(self):
        """Return-to-brood fires exactly once (not on subsequent turns)."""
        game = make_game_shell()
        player = game.state.players[0]
        original_hero = self._make_hero()
        player.hero = original_hero
        agent = self._make_agent()

        game._become_agent_of_chaos(0, agent)

        # Controller's end phase — reverts
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        assert player.hero == original_hero

        # Simulate re-transformation for a new fight
        agent2 = self._make_agent(name="Arakni, Redback", instance_id=902)
        player.hero = agent2
        player.original_hero = original_hero

        # Another controller end phase — should NOT fire the OLD handler again
        # (it was already fired and marked)
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=0,
        ))
        # The old handler doesn't revert because fired[0] is True
        # (new transformation would need its own handler)
        assert player.hero == agent2
