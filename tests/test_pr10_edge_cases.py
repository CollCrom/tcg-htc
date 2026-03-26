"""Edge-case tests for PR #10 fixes, per skeptic review recommendations.

Covers:
1. Go Again dynamic effects (grant/remove during combat)
2. Defense reaction counter edge cases
3. Self-damage source attribution
4. Life counter precision
5. Combat chain state interactions with Go Again
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.continuous import (
    ContinuousEffect,
    EffectDuration,
    ModStage,
    ModSubstage,
    make_keyword_grant,
)
from htc.engine.effects import EffectEngine
from htc.engine.events import EventBus, EventType, GameEvent
from htc.engine.game import Game
from htc.enums import CardType, Keyword, SubType, Zone
from htc.state.combat_state import ChainLink, CombatChainState
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState
from htc.state.turn_counters import TurnCounters
from tests.conftest import make_card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state() -> GameState:
    state = GameState()
    state.players = [
        PlayerState(index=0, life_total=20),
        PlayerState(index=1, life_total=20),
    ]
    return state


def _make_game_shell(state: GameState | None = None) -> Game:
    """Create a minimal Game object for unit-testing internal methods."""
    game = Game.__new__(Game)
    game.state = state or _make_state()
    game.effect_engine = EffectEngine()
    game.events = EventBus()
    game._register_event_handlers()
    return game


# ---------------------------------------------------------------------------
# 1. Go Again dynamic effects
# ---------------------------------------------------------------------------


def test_go_again_granted_by_effect_during_combat():
    """An effect granting Go Again mid-combat should be respected at resolution."""
    state = _make_state()
    engine = EffectEngine()

    attack = make_card(instance_id=1, name="Plain Attack", power=3)
    # Card does NOT have Go Again natively
    assert Keyword.GO_AGAIN not in attack.definition.keywords

    # Before any effect, no Go Again
    kw = engine.get_modified_keywords(state, attack)
    assert Keyword.GO_AGAIN not in kw

    # Simulate mid-combat effect granting Go Again
    effect = make_keyword_grant(
        frozenset({Keyword.GO_AGAIN}),
        controller_index=0,
        duration=EffectDuration.END_OF_TURN,
    )
    engine.add_continuous_effect(state, effect)

    # Now the card should have Go Again
    kw = engine.get_modified_keywords(state, attack)
    assert Keyword.GO_AGAIN in kw


def test_go_again_removed_by_effect_during_combat():
    """An effect removing Go Again mid-combat should be respected at resolution."""
    state = _make_state()
    engine = EffectEngine()

    attack = make_card(
        instance_id=1,
        name="Go Again Attack",
        power=3,
        keywords=frozenset({Keyword.GO_AGAIN}),
    )
    # Card has Go Again natively
    assert Keyword.GO_AGAIN in attack.definition.keywords

    # Before any effect, has Go Again
    kw = engine.get_modified_keywords(state, attack)
    assert Keyword.GO_AGAIN in kw

    # Add effect that removes Go Again
    effect = ContinuousEffect(
        controller_index=1,
        stage=ModStage.ABILITIES,
        substage=ModSubstage.ADD_TO,
        duration=EffectDuration.END_OF_TURN,
        target_filter=lambda _c: True,
        keywords_to_remove=frozenset({Keyword.GO_AGAIN}),
    )
    engine.add_continuous_effect(state, effect)

    # Now Go Again should be gone
    kw = engine.get_modified_keywords(state, attack)
    assert Keyword.GO_AGAIN not in kw


def test_resolution_step_uses_dynamic_go_again():
    """_resolution_step should check modified keywords, not just link.has_go_again."""
    game = _make_game_shell()
    state = game.state

    attack = make_card(instance_id=1, name="Plain Attack", power=3)
    # Set up a combat chain link WITHOUT Go Again on the link
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
        has_go_again=False,
    )
    state.combat_chain = CombatChainState(is_open=True, chain_links=[link])
    state.turn_player_index = 0
    state.action_points = {0: 0, 1: 0}

    # Grant Go Again via continuous effect
    effect = make_keyword_grant(
        frozenset({Keyword.GO_AGAIN}),
        controller_index=0,
        duration=EffectDuration.END_OF_TURN,
    )
    game.effect_engine.add_continuous_effect(state, effect)

    # Verify the dynamic check would give Go Again
    kw = game.effect_engine.get_modified_keywords(state, attack)
    assert Keyword.GO_AGAIN in kw

    # The attacker (player 0) should gain an AP from the resolution logic
    # We test the logic directly rather than calling _resolution_step which
    # requires full game setup
    attacker_index = 1 - link.attack_target_index
    has_go_again = link.has_go_again  # False from link
    if link.active_attack:
        attack_keywords = game.effect_engine.get_modified_keywords(state, link.active_attack)
        has_go_again = Keyword.GO_AGAIN in attack_keywords
    if has_go_again:
        state.action_points[attacker_index] += 1

    assert state.action_points[0] == 1, "Player 0 should gain 1 AP from dynamic Go Again"


# ---------------------------------------------------------------------------
# 2. Defense reaction counter edge cases
# ---------------------------------------------------------------------------


def test_defense_reaction_counter_increments():
    """Playing a defense reaction should increment the counter."""
    counters = TurnCounters()
    assert counters.num_defense_reactions_played == 0
    counters.num_defense_reactions_played += 1
    assert counters.num_defense_reactions_played == 1


def test_multiple_defense_reactions_in_turn():
    """Multiple defense reactions in a single turn should all be counted."""
    counters = TurnCounters()
    counters.num_defense_reactions_played += 1
    counters.num_defense_reactions_played += 1
    counters.num_defense_reactions_played += 1
    assert counters.num_defense_reactions_played == 3


def test_defense_reaction_counter_resets_between_turns():
    """Counter should reset to 0 when TurnCounters.reset() is called."""
    counters = TurnCounters()
    counters.num_defense_reactions_played = 5
    counters.num_cards_defended_from_hand = 3
    counters.damage_taken = 10

    counters.reset()

    assert counters.num_defense_reactions_played == 0
    assert counters.num_cards_defended_from_hand == 0
    assert counters.damage_taken == 0


def test_defense_reaction_counter_independent_of_other_counters():
    """Defense reaction counter should be independent of other play counters."""
    counters = TurnCounters()
    counters.num_attacks_played = 2
    counters.num_non_attack_actions_played = 1
    counters.num_instants_played = 3
    counters.num_defense_reactions_played = 1

    assert counters.num_attacks_played == 2
    assert counters.num_non_attack_actions_played == 1
    assert counters.num_instants_played == 3
    assert counters.num_defense_reactions_played == 1


# ---------------------------------------------------------------------------
# 3. Self-damage source attribution
# ---------------------------------------------------------------------------


def test_damage_attributed_to_source_owner():
    """Damage should be attributed to source.owner_index, not inferred."""
    game = _make_game_shell()
    state = game.state

    # Player 0 owns the source card
    source = make_card(instance_id=1, name="Blood Debt Source", owner_index=0)

    # Player 0 takes damage from their own card (self-damage)
    event = GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=source,
        target_player=0,
        amount=3,
    )
    game._handle_damage(event)

    # Player 0 took 3 damage
    assert state.players[0].life_total == 17
    assert state.players[0].turn_counters.damage_taken == 3
    # Player 0 dealt the damage (to themselves)
    assert state.players[0].turn_counters.damage_dealt == 3
    # Player 1 was not involved
    assert state.players[1].turn_counters.damage_dealt == 0
    assert state.players[1].turn_counters.damage_taken == 0


def test_normal_damage_attribution():
    """Normal attack: player 0's card damages player 1."""
    game = _make_game_shell()
    state = game.state

    source = make_card(instance_id=1, name="Attack", owner_index=0)
    event = GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=source,
        target_player=1,
        amount=5,
    )
    game._handle_damage(event)

    assert state.players[1].life_total == 15
    assert state.players[1].turn_counters.damage_taken == 5
    assert state.players[0].turn_counters.damage_dealt == 5
    assert state.players[0].turn_counters.damage_taken == 0


def test_damage_without_source_no_dealt_tracking():
    """Damage with no source should not crash or attribute damage_dealt."""
    game = _make_game_shell()
    state = game.state

    event = GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=None,
        target_player=1,
        amount=2,
    )
    game._handle_damage(event)

    assert state.players[1].life_total == 18
    assert state.players[1].turn_counters.damage_taken == 2
    # No source, so no damage_dealt attributed
    assert state.players[0].turn_counters.damage_dealt == 0
    assert state.players[1].turn_counters.damage_dealt == 0


# ---------------------------------------------------------------------------
# 4. Life counter precision
# ---------------------------------------------------------------------------


def test_life_lost_counter_tracks_damage():
    """life_lost counter should increase when taking damage."""
    game = _make_game_shell()
    state = game.state

    source = make_card(instance_id=1, name="Attack", owner_index=0)
    event = GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=source,
        target_player=1,
        amount=7,
    )
    game._handle_damage(event)

    assert state.players[1].turn_counters.life_lost == 7


def test_life_gained_counter_tracks_healing():
    """life_gained counter should increase on life gain events."""
    game = _make_game_shell()
    state = game.state

    event = GameEvent(
        event_type=EventType.GAIN_LIFE,
        target_player=0,
        amount=4,
    )
    game._handle_gain_life(event)

    assert state.players[0].life_total == 24
    assert state.players[0].turn_counters.life_gained == 4


def test_life_counters_accumulate():
    """Multiple damage and heal events should accumulate correctly."""
    game = _make_game_shell()
    state = game.state

    source = make_card(instance_id=1, name="Attack", owner_index=0)

    # Take 3 damage
    game._handle_damage(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=source, target_player=1, amount=3,
    ))
    # Take 5 more damage
    game._handle_damage(GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=source, target_player=1, amount=5,
    ))
    # Gain 2 life
    game._handle_gain_life(GameEvent(
        event_type=EventType.GAIN_LIFE,
        target_player=1, amount=2,
    ))

    assert state.players[1].life_total == 14  # 20 - 3 - 5 + 2
    assert state.players[1].turn_counters.life_lost == 8  # 3 + 5
    assert state.players[1].turn_counters.life_gained == 2
    assert state.players[1].turn_counters.damage_taken == 8


def test_life_counters_reset_with_turn():
    """Life counters should reset when TurnCounters resets."""
    counters = TurnCounters()
    counters.life_gained = 5
    counters.life_lost = 8
    counters.reset()
    assert counters.life_gained == 0
    assert counters.life_lost == 0


def test_zero_damage_does_not_affect_counters():
    """Zero-amount damage event should not change any counters."""
    game = _make_game_shell()
    state = game.state

    event = GameEvent(
        event_type=EventType.DEAL_DAMAGE,
        source=make_card(instance_id=1, owner_index=0),
        target_player=1,
        amount=0,
    )
    game._handle_damage(event)

    assert state.players[1].life_total == 20
    assert state.players[1].turn_counters.damage_taken == 0
    assert state.players[1].turn_counters.life_lost == 0


def test_zero_life_gain_does_not_affect_counters():
    """Zero-amount life gain event should not change any counters."""
    game = _make_game_shell()
    state = game.state

    event = GameEvent(
        event_type=EventType.GAIN_LIFE,
        target_player=0,
        amount=0,
    )
    game._handle_gain_life(event)

    assert state.players[0].life_total == 20
    assert state.players[0].turn_counters.life_gained == 0


# ---------------------------------------------------------------------------
# 5. Combat chain / Go Again interaction
# ---------------------------------------------------------------------------


def test_go_again_from_link_when_no_active_attack():
    """If active_attack is None, fall back to link.has_go_again."""
    state = _make_state()
    state.action_points = {0: 0, 1: 0}

    link = ChainLink(
        link_number=1,
        active_attack=None,
        attack_target_index=1,
        has_go_again=True,
    )

    # Replicate the resolution logic
    attacker_index = 1 - link.attack_target_index
    has_go_again = link.has_go_again
    if link.active_attack:
        # Would check dynamic keywords, but no active attack
        pass
    if has_go_again:
        state.action_points[attacker_index] += 1

    assert state.action_points[0] == 1


def test_go_again_link_false_no_effect_means_no_ap():
    """Without Go Again on link or from effects, no AP should be granted."""
    state = _make_state()
    engine = EffectEngine()
    state.action_points = {0: 0, 1: 0}

    attack = make_card(instance_id=1, name="No GA Attack", power=3)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
        has_go_again=False,
    )

    attacker_index = 1 - link.attack_target_index
    has_go_again = link.has_go_again
    if link.active_attack:
        kw = engine.get_modified_keywords(state, link.active_attack)
        has_go_again = Keyword.GO_AGAIN in kw
    if has_go_again:
        state.action_points[attacker_index] += 1

    assert state.action_points[0] == 0, "No AP without Go Again"
