"""Tests for actionable TODO fixes.

Covers:
1. Devotion Never Dies: playable-from-banish after on-hit banish
2. Rising Resentment: playable-from-banish + cost reduction after on-hit banish
3. Art of the Dragon: Fire: any-target choice (opponent or self)
4. Warmonger's Diplomacy: war/peace turn restrictions
5. Stains of the Redback: cost reduction when opponent is marked
6. Reaper's Call: instant discard marks opposing hero
7. Under the Trap-Door: stale TODO removed (instant already implemented)
8. Diplomacy restriction cleared at end of turn
9. War restriction allows weapon activations
10. _is_draconic uses effect engine for granted supertypes
11. Stains of the Redback cost reduction via intrinsic modifier registry
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import ActionOption, Decision, PlayerResponse
from htc.engine.events import EventType, GameEvent
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
from tests.conftest import (
    make_card,
    make_game_shell,
    make_mock_ask,
    make_pitch_card,
)
from tests.abilities.conftest import (
    make_draconic_ninja_attack,
    make_ninja_attack,
    make_stealth_attack,
    make_dagger_weapon,
    make_attack_reaction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_interfaces(ask_fn):
    """Create mock player interfaces that delegate to ask_fn."""
    _MockPlayer = type("P", (), {"decide": lambda s, state, d: ask_fn(d)})
    return [_MockPlayer(), _MockPlayer()]


def _make_attack_action(
    instance_id: int = 1,
    name: str = "Test Attack",
    *,
    power: int = 3,
    cost: int = 1,
    owner_index: int = 0,
    zone: Zone = Zone.HAND,
    supertypes: frozenset = frozenset(),
    keywords: frozenset = frozenset(),
) -> CardInstance:
    """Create an attack action card."""
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
        supertypes=supertypes,
        keywords=keywords,
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
    keywords: frozenset = frozenset(),
) -> CardInstance:
    """Create a non-attack action card."""
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
        keywords=keywords,
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
# 1. Devotion Never Dies — playable-from-banish
# ===========================================================================


class TestDevotionNeverDies:
    """Devotion Never Dies on-hit: banish + playable from banish this turn."""

    def test_banish_and_playable_from_banish(self):
        """When hit after a Draconic link, card is banished and marked playable."""
        game = make_game_shell()
        player = game.state.players[0]

        # Set up chain: link 0 = Draconic, link 1 = Devotion Never Dies
        prev_attack = make_draconic_ninja_attack(instance_id=2, name="Draconic Prev")
        dnd_attack = make_ninja_attack(
            instance_id=1, name="Devotion Never Dies", power=3,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, prev_attack, 1)
        game.combat_mgr.add_chain_link(game.state, dnd_attack, 1)

        game._apply_card_ability(dnd_attack, 0, "on_hit")

        # Card should be in banished zone
        assert dnd_attack in player.banished
        assert dnd_attack.zone == Zone.BANISHED

        # Card should be marked playable from banish (end_of_turn, no redirect)
        assert any(
            iid == dnd_attack.instance_id and exp == "end_of_turn" and redir is False
            for iid, exp, redir in player.playable_from_banish
        )

    def test_no_banish_without_draconic_prev(self):
        """No banish if previous link was not Draconic."""
        game = make_game_shell()
        player = game.state.players[0]

        prev_attack = make_ninja_attack(instance_id=2, name="Non-Draconic Prev")
        dnd_attack = make_ninja_attack(
            instance_id=1, name="Devotion Never Dies", power=3,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, prev_attack, 1)
        game.combat_mgr.add_chain_link(game.state, dnd_attack, 1)

        game._apply_card_ability(dnd_attack, 0, "on_hit")

        assert dnd_attack not in player.banished
        assert not player.playable_from_banish


# ===========================================================================
# 2. Rising Resentment — playable-from-banish + cost reduction
# ===========================================================================


class TestRisingResentment:
    """Rising Resentment on-hit: banish from hand, playable, costs 1 less."""

    def test_banish_eligible_card_and_mark_playable(self):
        """Chosen card is banished, marked playable, and gets cost reduction."""
        game = make_game_shell()
        player = game.state.players[0]

        # Need 2+ Draconic chain links so cost < 2 is eligible
        d1 = make_draconic_ninja_attack(instance_id=10, name="Draconic 1")
        d2 = make_draconic_ninja_attack(instance_id=11, name="Draconic 2")
        rr_attack = make_draconic_ninja_attack(
            instance_id=1, name="Rising Resentment", power=3,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, d1, 1)
        game.combat_mgr.add_chain_link(game.state, d2, 1)
        game.combat_mgr.add_chain_link(game.state, rr_attack, 1)

        # Put an eligible attack action (cost=1 < 3 Draconic links) in hand
        eligible = _make_attack_action(instance_id=20, name="Cheap Attack", cost=1)
        eligible.zone = Zone.HAND
        player.hand.append(eligible)

        # Mock: choose to banish the eligible card
        mock_ask = make_mock_ask({"Rising Resentment": [f"banish_{eligible.instance_id}"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        game._apply_card_ability(rr_attack, 0, "on_hit")

        # Card should be banished
        assert eligible in player.banished
        assert eligible not in player.hand

        # Card should be marked playable from banish
        assert any(
            iid == eligible.instance_id and exp == "end_of_turn" and redir is False
            for iid, exp, redir in player.playable_from_banish
        )

        # Card should have cost reduction (-1)
        modified_cost = game.effect_engine.get_modified_cost(game.state, eligible)
        assert modified_cost == 0  # 1 - 1 = 0

    def test_pass_does_not_banish(self):
        """Passing does not banish any card."""
        game = make_game_shell()
        player = game.state.players[0]

        d1 = make_draconic_ninja_attack(instance_id=10, name="Draconic 1")
        d2 = make_draconic_ninja_attack(instance_id=11, name="Draconic 2")
        rr_attack = make_draconic_ninja_attack(
            instance_id=1, name="Rising Resentment", power=3,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, d1, 1)
        game.combat_mgr.add_chain_link(game.state, d2, 1)
        game.combat_mgr.add_chain_link(game.state, rr_attack, 1)

        eligible = _make_attack_action(instance_id=20, name="Cheap Attack", cost=1)
        player.hand.append(eligible)

        mock_ask = make_mock_ask({"Rising Resentment": ["pass"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        game._apply_card_ability(rr_attack, 0, "on_hit")

        assert eligible not in player.banished
        assert eligible in player.hand
        assert not player.playable_from_banish

    def test_no_eligible_cards(self):
        """No banish when no eligible cards in hand."""
        game = make_game_shell()
        player = game.state.players[0]

        # Only 1 Draconic chain link, so need cost < 1 — nothing eligible
        d1 = make_draconic_ninja_attack(instance_id=10, name="Draconic 1")
        rr_attack = make_draconic_ninja_attack(
            instance_id=1, name="Rising Resentment", power=3,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, d1, 1)
        game.combat_mgr.add_chain_link(game.state, rr_attack, 1)

        # Put a cost=2 card in hand (not eligible since 2 >= 2 draconic links)
        expensive = _make_attack_action(instance_id=20, name="Expensive Attack", cost=2)
        player.hand.append(expensive)

        # No decision should be asked
        game._apply_card_ability(rr_attack, 0, "on_hit")

        assert expensive in player.hand
        assert not player.playable_from_banish


# ===========================================================================
# 3. Art of the Dragon: Fire — any target choice
# ===========================================================================


class TestArtOfTheDragonFireTarget:
    """Art of the Dragon: Fire lets the player choose any hero as target."""

    def test_choose_opponent(self):
        """Choosing the opponent deals 2 damage to them."""
        game = make_game_shell(life=20)
        mock_ask = make_mock_ask({"Art of the Dragon: Fire": ["target_1"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        attack = make_draconic_ninja_attack(
            instance_id=1, name="Art of the Dragon: Fire", power=5,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        assert game.state.players[1].life_total == 18
        assert game.state.players[0].life_total == 20

    def test_choose_self(self):
        """Choosing yourself deals 2 damage to you."""
        game = make_game_shell(life=20)
        mock_ask = make_mock_ask({"Art of the Dragon: Fire": ["target_0"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        attack = make_draconic_ninja_attack(
            instance_id=1, name="Art of the Dragon: Fire", power=5,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        assert game.state.players[0].life_total == 18
        assert game.state.players[1].life_total == 20

    def test_defaults_to_opponent_on_invalid_response(self):
        """Invalid response defaults to opponent."""
        game = make_game_shell(life=20)
        mock_ask = make_mock_ask({"Art of the Dragon: Fire": ["pass"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        attack = make_draconic_ninja_attack(
            instance_id=1, name="Art of the Dragon: Fire", power=5,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        # Default: opponent takes 2 damage
        assert game.state.players[1].life_total == 18

    def test_not_draconic_no_damage(self):
        """Not Draconic: no damage, no choice asked."""
        game = make_game_shell(life=20)
        attack = make_ninja_attack(
            instance_id=1, name="Art of the Dragon: Fire", power=5,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        assert game.state.players[0].life_total == 20
        assert game.state.players[1].life_total == 20


# ===========================================================================
# 4. Warmonger's Diplomacy — war/peace turn restrictions
# ===========================================================================


class TestWarmongersDiplomacy:
    """Warmonger's Diplomacy sets diplomacy_restriction on opponent."""

    def test_war_choice_sets_restriction(self):
        """Choosing war sets diplomacy_restriction='war' on opponent."""
        game = make_game_shell()
        mock_ask = make_mock_ask({"Warmonger's Diplomacy": ["war"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        card = _make_non_attack_action(instance_id=1, name="Warmonger's Diplomacy")
        game._apply_card_ability(card, 0, "on_play")

        assert game.state.players[1].diplomacy_restriction == "war"

    def test_peace_choice_sets_restriction(self):
        """Choosing peace sets diplomacy_restriction='peace' on opponent."""
        game = make_game_shell()
        mock_ask = make_mock_ask({"Warmonger's Diplomacy": ["peace"]})
        game.interfaces = _make_mock_interfaces(mock_ask)

        card = _make_non_attack_action(instance_id=1, name="Warmonger's Diplomacy")
        game._apply_card_ability(card, 0, "on_play")

        assert game.state.players[1].diplomacy_restriction == "peace"

    def test_war_blocks_non_attack_actions(self):
        """War restriction blocks non-attack action cards."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "war"

        non_attack = _make_non_attack_action(instance_id=5, owner_index=1)
        game.state.players[1].hand.append(non_attack)

        assert not game.action_builder.can_play_card(game.state, 1, non_attack)

    def test_war_allows_attack_actions(self):
        """War restriction allows attack action cards."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "war"

        attack = _make_attack_action(instance_id=5, owner_index=1, cost=0)
        attack.zone = Zone.HAND
        game.state.players[1].hand.append(attack)

        assert game.action_builder.can_play_card(game.state, 1, attack)

    def test_peace_blocks_attack_actions(self):
        """Peace restriction blocks attack action cards."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "peace"

        attack = _make_attack_action(instance_id=5, owner_index=1, cost=0)
        attack.zone = Zone.HAND
        game.state.players[1].hand.append(attack)

        assert not game.action_builder.can_play_card(game.state, 1, attack)

    def test_peace_allows_non_attack_actions(self):
        """Peace restriction allows non-attack action cards."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "peace"

        non_attack = _make_non_attack_action(instance_id=5, owner_index=1, cost=0)
        game.state.players[1].hand.append(non_attack)

        assert game.action_builder.can_play_card(game.state, 1, non_attack)

    def test_peace_blocks_weapon_activation(self):
        """Peace restriction blocks weapon activations."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "peace"

        weapon = make_dagger_weapon(instance_id=100, owner_index=1)
        game.state.players[1].weapons.append(weapon)

        assert not game.action_builder._can_activate_weapon(game.state, 1, weapon)

    def test_no_restriction_allows_everything(self):
        """No restriction allows all actions."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        assert game.state.players[1].diplomacy_restriction is None

        attack = _make_attack_action(instance_id=5, owner_index=1, cost=0)
        attack.zone = Zone.HAND
        game.state.players[1].hand.append(attack)

        non_attack = _make_non_attack_action(instance_id=6, owner_index=1, cost=0)
        game.state.players[1].hand.append(non_attack)

        assert game.action_builder.can_play_card(game.state, 1, attack)
        assert game.action_builder.can_play_card(game.state, 1, non_attack)


# ===========================================================================
# 5. Stains of the Redback — cost reduction when opponent is marked
# ===========================================================================


class TestStainsOfTheRedbackCost:
    """Stains of the Redback costs {r} less when defending hero is marked."""

    def _make_stains(self, instance_id: int = 10, cost: int = 1, owner_index: int = 0):
        defn = CardDefinition(
            unique_id=f"stains-{instance_id}",
            name="Stains of the Redback",
            color=Color.RED,
            pitch=1,
            cost=cost,
            power=None,
            defense=3,
            health=None,
            intellect=None,
            arcane=None,
            types=frozenset({CardType.ATTACK_REACTION}),
            subtypes=frozenset(),
            supertypes=frozenset({SuperType.ASSASSIN}),
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

    def test_cost_reduced_when_opponent_marked(self):
        """Cost is reduced by 1 when the opponent is marked."""
        game = make_game_shell()
        stains = self._make_stains(cost=1)
        game.state.players[1].is_marked = True  # Opponent is marked

        cost = game.effect_engine.get_modified_cost(game.state, stains)
        assert cost == 0  # 1 - 1 = 0

    def test_cost_not_reduced_when_opponent_not_marked(self):
        """Cost is not reduced when the opponent is not marked."""
        game = make_game_shell()
        stains = self._make_stains(cost=1)
        game.state.players[1].is_marked = False

        cost = game.effect_engine.get_modified_cost(game.state, stains)
        assert cost == 1

    def test_cost_does_not_go_below_zero(self):
        """Cost reduction does not result in negative cost."""
        game = make_game_shell()
        stains = self._make_stains(cost=0)
        game.state.players[1].is_marked = True

        cost = game.effect_engine.get_modified_cost(game.state, stains)
        assert cost == 0

    def test_cost_reduced_for_player_1(self):
        """Cost reduction works correctly for player 1 (opponent=player 0)."""
        game = make_game_shell()
        stains = self._make_stains(cost=2, owner_index=1)
        game.state.players[0].is_marked = True  # Player 0 is marked (opponent of player 1)

        cost = game.effect_engine.get_modified_cost(game.state, stains)
        assert cost == 1  # 2 - 1 = 1


# ===========================================================================
# 6. Reaper's Call — instant discard marks opposing hero
# ===========================================================================


class TestReapersCallInstant:
    """Reaper's Call instant discard: marks the opposing hero."""

    def _make_reapers_call(self, instance_id: int = 10, owner_index: int = 0):
        defn = CardDefinition(
            unique_id=f"reapers-{instance_id}",
            name="Reaper's Call",
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
            supertypes=frozenset({SuperType.ASSASSIN}),
            keywords=frozenset({Keyword.STEALTH}),
            functional_text="",
            type_text="",
        )
        return CardInstance(
            instance_id=instance_id,
            definition=defn,
            owner_index=owner_index,
            zone=Zone.HAND,
        )

    def test_instant_discard_marks_opponent(self):
        """Discarding Reaper's Call marks the opposing hero."""
        game = make_game_shell()
        card = self._make_reapers_call()

        assert not game.state.players[1].is_marked

        game._apply_card_ability(card, 0, "instant_discard_effect")

        assert game.state.players[1].is_marked

    def test_instant_discard_registered(self):
        """Reaper's Call is registered as an instant_discard_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup("instant_discard_effect", "Reaper's Call")
        assert handler is not None

    def test_instant_discard_player_1(self):
        """Player 1 discarding Reaper's Call marks Player 0."""
        game = make_game_shell()
        card = self._make_reapers_call(owner_index=1)

        assert not game.state.players[0].is_marked

        game._apply_card_ability(card, 1, "instant_discard_effect")

        assert game.state.players[0].is_marked


# ===========================================================================
# 7. Under the Trap-Door — stale TODO verification
# ===========================================================================


class TestUnderTheTrapDoorTODO:
    """Verify the Under the Trap-Door instant discard is already implemented."""

    def test_instant_discard_registered(self):
        """Under the Trap-Door is registered as an instant_discard_effect."""
        game = make_game_shell()
        handler = game.ability_registry.lookup(
            "instant_discard_effect", "Under the Trap-Door"
        )
        assert handler is not None

    def test_on_hit_is_no_op(self):
        """Under the Trap-Door on_hit handler is a no-op (no side effects)."""
        game = make_game_shell(life=20)
        card = _make_attack_action(instance_id=1, name="Under the Trap-Door")

        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, card, 1)

        # Should not throw or change any state
        game._apply_card_ability(card, 0, "on_hit")

        assert game.state.players[0].life_total == 20
        assert game.state.players[1].life_total == 20


# ===========================================================================
# 8. Diplomacy restriction cleared at end of turn
# ===========================================================================


class TestDiplomacyRestrictionClearing:
    """Diplomacy restriction is cleared at end of the restricted player's turn."""

    def test_war_restriction_cleared_at_end_of_turn(self):
        """War restriction is cleared when the restricted player's turn ends."""
        game = make_game_shell(action_points={0: 0, 1: 0})
        game.state.players[0].diplomacy_restriction = "war"
        game.state.turn_player_index = 0

        # Provide an interface so _run_end_phase can ask about arsenaling
        game.interfaces = _make_mock_interfaces(make_mock_ask({}))

        game._run_end_phase()

        assert game.state.players[0].diplomacy_restriction is None

    def test_peace_restriction_cleared_at_end_of_turn(self):
        """Peace restriction is cleared when the restricted player's turn ends."""
        game = make_game_shell(action_points={0: 0, 1: 0})
        game.state.players[0].diplomacy_restriction = "peace"
        game.state.turn_player_index = 0

        game.interfaces = _make_mock_interfaces(make_mock_ask({}))

        game._run_end_phase()

        assert game.state.players[0].diplomacy_restriction is None

    def test_restriction_not_cleared_for_other_player(self):
        """Restriction on player 1 is NOT cleared when player 0's turn ends."""
        game = make_game_shell(action_points={0: 0, 1: 0})
        game.state.players[1].diplomacy_restriction = "war"
        game.state.turn_player_index = 0

        game.interfaces = _make_mock_interfaces(make_mock_ask({}))

        game._run_end_phase()

        # Player 1's restriction should still be active (it's player 0's turn)
        assert game.state.players[1].diplomacy_restriction == "war"


# ===========================================================================
# 9. War restriction allows weapon activations
# ===========================================================================


class TestWarAllowsWeapons:
    """War restriction allows weapon activations (only non-attack actions blocked)."""

    def test_war_allows_weapon_activation(self):
        """Under war restriction, weapons can still be activated."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "war"

        weapon = make_dagger_weapon(instance_id=100, owner_index=1)
        game.state.players[1].weapons.append(weapon)

        assert game.action_builder._can_activate_weapon(game.state, 1, weapon)

    def test_war_blocks_non_attack_but_allows_weapon(self):
        """War blocks non-attack actions but allows weapons in the same turn."""
        game = make_game_shell(action_points={0: 1, 1: 1})
        game.state.players[1].diplomacy_restriction = "war"

        # Non-attack action should be blocked
        non_attack = _make_non_attack_action(instance_id=5, owner_index=1)
        game.state.players[1].hand.append(non_attack)
        assert not game.action_builder.can_play_card(game.state, 1, non_attack)

        # Weapon should be allowed
        weapon = make_dagger_weapon(instance_id=100, owner_index=1)
        game.state.players[1].weapons.append(weapon)
        assert game.action_builder._can_activate_weapon(game.state, 1, weapon)


# ===========================================================================
# 10. _is_draconic uses effect engine for granted supertypes
# ===========================================================================


class TestIsDraconicUsesEffectEngine:
    """_is_draconic() queries the effect engine when ctx is provided."""

    def test_effect_granted_draconic_detected(self):
        """A non-Draconic card with a granted Draconic supertype is detected."""
        from htc.engine.continuous import EffectDuration, make_supertype_grant

        game = make_game_shell()

        # Non-Draconic ninja attack
        attack = make_ninja_attack(instance_id=1, name="Dragon Power", power=4)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        # NOT Draconic by definition
        assert SuperType.DRACONIC not in attack.definition.supertypes

        # Grant Draconic via continuous effect
        grant = make_supertype_grant(
            frozenset({SuperType.DRACONIC}),
            controller_index=0,
            duration=EffectDuration.END_OF_TURN,
            target_filter=lambda c: c.instance_id == attack.instance_id,
        )
        game.effect_engine.add_continuous_effect(game.state, grant)

        # _is_draconic without ctx falls back to definition (misses it)
        from htc.cards.abilities.ninja import _is_draconic
        assert not _is_draconic(attack)

        # _is_draconic with ctx should detect the granted supertype
        from htc.engine.abilities import AbilityContext
        ctx = AbilityContext(
            state=game.state,
            source_card=attack,
            controller_index=0,
            chain_link=game.state.combat_chain.chain_links[-1],
            effect_engine=game.effect_engine,
            events=game.events,
            ask=lambda d: None,
            keyword_engine=game.keyword_engine,
            combat_mgr=game.combat_mgr,
        )
        assert _is_draconic(attack, ctx)

    def test_dragon_power_triggers_with_granted_draconic(self):
        """Dragon Power grants +3 power when Draconic is effect-granted."""
        from htc.engine.continuous import EffectDuration, make_supertype_grant

        game = make_game_shell()

        attack = make_ninja_attack(
            instance_id=1, name="Dragon Power", power=4,
        )
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        # Grant Draconic via continuous effect
        grant = make_supertype_grant(
            frozenset({SuperType.DRACONIC}),
            controller_index=0,
            duration=EffectDuration.END_OF_TURN,
            target_filter=lambda c: c.instance_id == attack.instance_id,
        )
        game.effect_engine.add_continuous_effect(game.state, grant)

        # Apply Dragon Power on_attack
        game._apply_card_ability(attack, 0, "on_attack")

        # Should have +3 power from Dragon Power
        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 7  # 4 base + 3 from Dragon Power


# ===========================================================================
# 11. Stains of the Redback — intrinsic cost modifier registry
# ===========================================================================


class TestStainsCostModifierRegistry:
    """Stains of the Redback cost reduction uses the intrinsic modifier registry."""

    def test_modifier_is_registered(self):
        """The cost modifier is registered on the effect engine."""
        game = make_game_shell()
        assert "Stains of the Redback" in game.effect_engine._intrinsic_cost_modifiers

    def test_no_hardcoded_name_check_in_get_modified_cost(self):
        """get_modified_cost does not contain a hardcoded Stains check."""
        import inspect
        from htc.engine.effects import EffectEngine
        source = inspect.getsource(EffectEngine.get_modified_cost)
        assert "Stains of the Redback" not in source
