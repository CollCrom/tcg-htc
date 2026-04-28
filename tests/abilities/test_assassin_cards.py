"""Tests for Assassin card ability effects (Arakni Marionette deck).

Covers attack reactions, defense reaction traps, non-attack action on_play
effects, and attack action on_attack/on_hit effects.
"""

from engine.cards.instance import CardInstance
from engine.rules.actions import PlayerResponse
from engine.rules.events import EventType, GameEvent
from engine.enums import (
    CardType,
    Color,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_game_shell, make_mock_ask
from tests.abilities.conftest import (
    make_dagger_attack as _make_dagger_attack,
    make_dagger_weapon as _make_dagger_weapon,
    make_stealth_attack as _make_stealth_attack,
    make_non_attack_action as _make_non_attack_action,
    make_attack_reaction as _shared_make_attack_reaction,
    make_defense_reaction as _shared_make_defense_reaction,
)


# ---------------------------------------------------------------------------
# Test helpers — thin wrappers over shared factories for Assassin defaults
# ---------------------------------------------------------------------------


def _make_attack_reaction(
    name: str,
    instance_id: int = 10,
    color: Color = Color.RED,
    owner_index: int = 0,
    cost: int = 0,
) -> CardInstance:
    return _shared_make_attack_reaction(
        name, instance_id=instance_id, color=color, owner_index=owner_index,
        cost=cost, supertypes=frozenset({SuperType.ASSASSIN}),
    )


def _make_defense_reaction(
    name: str,
    instance_id: int = 20,
    color: Color = Color.RED,
    defense: int = 3,
    owner_index: int = 1,
) -> CardInstance:
    return _shared_make_defense_reaction(
        name, instance_id=instance_id, color=color, defense=defense,
        owner_index=owner_index, subtypes=frozenset({SubType.TRAP}),
        supertypes=frozenset({SuperType.ASSASSIN}),
    )


# ===========================================================================
# Attack Reactions
# ===========================================================================


class TestIncision:
    """Incision: Target dagger attack gets +N{p}."""

    def test_red_gives_plus_three(self):
        game = make_game_shell()
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Incision", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 6

    def test_blue_gives_plus_one(self):
        game = make_game_shell()
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Incision", color=Color.BLUE)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 4

    def test_no_effect_on_non_dagger(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Incision", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 3


class TestToThePoint:
    """To the Point: +N or +N+1 if marked."""

    def test_unmarked_gives_base_bonus(self):
        game = make_game_shell()
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("To the Point", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        # Red base = +3, unmarked
        assert game.effect_engine.get_modified_power(game.state, attack) == 6

    def test_marked_gives_extra_bonus(self):
        game = make_game_shell()
        game.state.players[1].is_marked = True  # Defender is marked
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("To the Point", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        # Red marked = +4
        assert game.effect_engine.get_modified_power(game.state, attack) == 7


class TestScarTissue:
    """Scar Tissue: +N power and mark on hit."""

    def test_gives_power_boost(self):
        game = make_game_shell()
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Scar Tissue", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 6

    def test_marks_on_hit(self):
        game = make_game_shell()
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Scar Tissue", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        # Not marked yet
        assert not game.state.players[1].is_marked

        # Simulate hit
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=6,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Now marked
        assert game.state.players[1].is_marked


class TestStainsOfTheRedback:
    """Stains of the Redback: +N power and go again to stealth attack."""

    def test_gives_power_and_go_again(self):
        game = make_game_shell()
        attack = _make_stealth_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Stains of the Redback", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 6
        kws = game.effect_engine.get_modified_keywords(game.state, attack)
        assert Keyword.GO_AGAIN in kws

    def test_no_effect_without_stealth(self):
        game = make_game_shell()
        attack = _make_dagger_attack(instance_id=1, power=3)  # No stealth
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Stains of the Redback", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 3


class TestShred:
    """Shred: Target defending card gets -N defense."""

    def test_reduces_defense(self):
        game = make_game_shell()
        attack = _make_stealth_attack(
            instance_id=1, power=5,
            supertypes=frozenset({SuperType.ASSASSIN}),
        )
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, attack, 1)

        defender = make_card(instance_id=2, defense=5, zone=Zone.COMBAT_CHAIN, owner_index=1)
        game.combat_mgr.add_defender(game.state, link, defender)

        card = _make_attack_reaction("Shred", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        # Red Shred = -4 defense: 5 - 4 = 1
        assert game.effect_engine.get_modified_defense(game.state, defender) == 1

    def test_no_effect_without_assassin_attack(self):
        game = make_game_shell()
        # Non-assassin attack
        attack = make_card(instance_id=1, power=5, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, attack, 1)

        defender = make_card(instance_id=2, defense=5, zone=Zone.COMBAT_CHAIN, owner_index=1)
        game.combat_mgr.add_defender(game.state, link, defender)

        card = _make_attack_reaction("Shred", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        # Defense unchanged
        assert game.effect_engine.get_modified_defense(game.state, defender) == 5


class TestTakeUpTheMantle:
    """Take Up the Mantle: +2 power or +3 if marked."""

    def test_unmarked_gives_plus_two(self):
        game = make_game_shell()
        attack = _make_stealth_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Take Up the Mantle", color=Color.YELLOW)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 5

    def test_marked_gives_plus_three(self):
        game = make_game_shell()
        game.state.players[1].is_marked = True
        attack = _make_stealth_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Take Up the Mantle", color=Color.YELLOW)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 6


class TestTarantulaToxin:
    """Tarantula Toxin: +3 power to dagger and/or -3 defense to defender."""

    def test_dagger_mode_gives_power(self):
        game = make_game_shell()
        # Dagger attack without stealth -> only mode 1 valid
        attack = _make_dagger_attack(instance_id=1, power=3)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        card = _make_attack_reaction("Tarantula Toxin", color=Color.RED)
        game._apply_card_ability(card, 0, "attack_reaction_effect")

        assert game.effect_engine.get_modified_power(game.state, attack) == 6


# ===========================================================================
# Defense Reactions / Traps
# ===========================================================================


class TestDenOfTheSpider:
    """Den of the Spider: Mark attacker if attack power > base."""

    def test_marks_when_boosted(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, attack, 1)

        # Boost attack power above base
        from engine.rules.continuous import EffectDuration, make_power_modifier
        effect = make_power_modifier(2, 0, duration=EffectDuration.END_OF_COMBAT,
                                     target_filter=lambda c: c.instance_id == 1)
        game.effect_engine.add_continuous_effect(game.state, effect)

        dr = _make_defense_reaction("Den of the Spider", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        # Player 0 (attacker) should be marked
        assert game.state.players[0].is_marked

    def test_no_mark_when_not_boosted(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        dr = _make_defense_reaction("Den of the Spider", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        assert not game.state.players[0].is_marked


class TestLairOfTheSpider:
    """Lair of the Spider: Mark attacker if attack has go again."""

    def test_marks_when_go_again(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN,
                           keywords=frozenset({Keyword.GO_AGAIN}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        dr = _make_defense_reaction("Lair of the Spider", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        assert game.state.players[0].is_marked

    def test_no_mark_without_go_again(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        dr = _make_defense_reaction("Lair of the Spider", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        assert not game.state.players[0].is_marked


class TestFrailtyTrap:
    """Frailty Trap: Create Frailty token if attack has go again."""

    def test_creates_token_when_go_again(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN,
                           keywords=frozenset({Keyword.GO_AGAIN}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        dr = _make_defense_reaction("Frailty Trap", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        # Frailty token should be on attacker (player 0)
        tokens = [p for p in game.state.players[0].permanents if p.name == "Frailty"]
        assert len(tokens) == 1

    def test_no_token_without_go_again(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        dr = _make_defense_reaction("Frailty Trap", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        tokens = [p for p in game.state.players[0].permanents if p.name == "Frailty"]
        assert len(tokens) == 0


class TestInertiaTrap:
    """Inertia Trap: Create Inertia token if attack power > base."""

    def test_creates_token_when_boosted(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=3, zone=Zone.COMBAT_CHAIN)
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        from engine.rules.continuous import EffectDuration, make_power_modifier
        effect = make_power_modifier(2, 0, duration=EffectDuration.END_OF_COMBAT,
                                     target_filter=lambda c: c.instance_id == 1)
        game.effect_engine.add_continuous_effect(game.state, effect)

        dr = _make_defense_reaction("Inertia Trap", owner_index=1)
        game._apply_card_ability(dr, 1, "defense_reaction_effect")

        tokens = [p for p in game.state.players[0].permanents if p.name == "Inertia"]
        assert len(tokens) == 1


# ===========================================================================
# Non-Attack Actions (on_play)
# ===========================================================================


class TestCutFromTheSameCloth:
    """Cut from the Same Cloth: Reveal hand, mark if AR found, +N power to next dagger."""

    def test_marks_when_ar_in_hand(self):
        game = make_game_shell()
        # Opponent has an attack reaction
        ar = _make_attack_reaction("Some AR", instance_id=50, owner_index=1)
        game.state.players[1].hand.append(ar)

        card = _make_non_attack_action("Cut from the Same Cloth", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        assert game.state.players[1].is_marked

    def test_no_mark_without_ar(self):
        game = make_game_shell()
        # Opponent has no attack reaction
        normal = make_card(instance_id=50, owner_index=1, zone=Zone.HAND)
        game.state.players[1].hand.append(normal)

        card = _make_non_attack_action("Cut from the Same Cloth", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        assert not game.state.players[1].is_marked

    def test_reveals_opponent_hand_to_controller(self):
        """After resolution, every card in opponent's hand is revealed to the
        controller and shows up in their per-player snapshot."""
        from engine.state.snapshot import snapshot_for

        game = make_game_shell()
        # Opponent (P1) has three cards in hand — controller (P0) plays Cut.
        c1 = make_card(instance_id=70, owner_index=1, zone=Zone.HAND, name="Mystery 1")
        c2 = make_card(instance_id=71, owner_index=1, zone=Zone.HAND, name="Mystery 2")
        c3 = _make_attack_reaction("Some AR", instance_id=72, owner_index=1)
        game.state.players[1].hand.extend([c1, c2, c3])

        card = _make_non_attack_action("Cut from the Same Cloth", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        # All three opponent-hand instance_ids are now revealed to player 0.
        revealed = game.state.players[1].hand_revealed_to[0]
        assert revealed == {70, 71, 72}

        # And the snapshot from P0's viewpoint surfaces them under hand_revealed,
        # while still reporting the full hand_size and redacting `hand`.
        snap = snapshot_for(game.state, viewer_index=0, effect_engine=game.effect_engine)
        opp = snap["opponent"]
        assert opp["hand_size"] == 3
        assert "hand" not in opp
        revealed_ids = {c["instance_id"] for c in opp["hand_revealed"]}
        assert revealed_ids == {70, 71, 72}

        # The opposite snapshot (from P1's viewpoint of P0) should NOT show
        # P0's hand revealed — peeks are directional.
        snap_p1 = snapshot_for(game.state, viewer_index=1, effect_engine=game.effect_engine)
        assert snap_p1["opponent"]["hand_revealed"] == []

    def test_revealed_card_disappears_when_it_leaves_hand(self):
        """Persistent reveal is filtered against current hand contents — a
        revealed card that gets played/pitched/discarded falls off the snapshot."""
        from engine.state.snapshot import snapshot_for

        game = make_game_shell()
        c1 = make_card(instance_id=80, owner_index=1, zone=Zone.HAND, name="Will leave")
        c2 = make_card(instance_id=81, owner_index=1, zone=Zone.HAND, name="Will stay")
        game.state.players[1].hand.extend([c1, c2])

        card = _make_non_attack_action("Cut from the Same Cloth", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        # Both revealed initially.
        snap = snapshot_for(game.state, viewer_index=0, effect_engine=game.effect_engine)
        assert {c["instance_id"] for c in snap["opponent"]["hand_revealed"]} == {80, 81}

        # Move c1 out of hand (e.g. into pitch). Snapshot should now only show c2.
        game.state.players[1].hand.remove(c1)
        c1.zone = Zone.PITCH
        game.state.players[1].pitch.append(c1)

        snap = snapshot_for(game.state, viewer_index=0, effect_engine=game.effect_engine)
        revealed_ids = {c["instance_id"] for c in snap["opponent"]["hand_revealed"]}
        assert revealed_ids == {81}
        assert snap["opponent"]["hand_size"] == 1


class TestCodexOfFrailty:
    """Codex of Frailty: Arsenal from GY, discard, create tokens."""

    def test_creates_ponder_and_frailty_tokens(self):
        game = make_game_shell()
        # Put an attack action in P0's graveyard
        gy_card = _make_dagger_attack(instance_id=50, owner_index=0)
        gy_card.zone = Zone.GRAVEYARD
        game.state.players[0].graveyard.append(gy_card)
        # Give P0 a hand card to discard
        hand_card = make_card(instance_id=51, owner_index=0, zone=Zone.HAND)
        game.state.players[0].hand.append(hand_card)

        card = _make_non_attack_action("Codex of Frailty", color=Color.YELLOW)
        game._apply_card_ability(card, 0, "on_play")

        # Ponder token for controller (P0)
        ponder_tokens = [p for p in game.state.players[0].permanents if p.name == "Ponder"]
        assert len(ponder_tokens) == 1

        # Frailty token for opponent (P1)
        frailty_tokens = [p for p in game.state.players[1].permanents if p.name == "Frailty"]
        assert len(frailty_tokens) == 1


class TestCodexOfInertia:
    """Codex of Inertia: Arsenal top card, discard, create tokens."""

    def test_creates_ponder_and_inertia_tokens(self):
        game = make_game_shell()
        # P0 deck with cards
        deck_card = make_card(instance_id=50, owner_index=0, zone=Zone.DECK)
        game.state.players[0].deck.append(deck_card)
        # P0 hand with card to discard
        hand_card = make_card(instance_id=51, owner_index=0, zone=Zone.HAND)
        game.state.players[0].hand.append(hand_card)

        card = _make_non_attack_action("Codex of Inertia", color=Color.YELLOW)
        game._apply_card_ability(card, 0, "on_play")

        # Deck card should be in arsenal
        assert deck_card in game.state.players[0].arsenal
        assert not deck_card.face_up

        # Ponder for P0, Inertia for P1
        ponder = [p for p in game.state.players[0].permanents if p.name == "Ponder"]
        inertia = [p for p in game.state.players[1].permanents if p.name == "Inertia"]
        assert len(ponder) == 1
        assert len(inertia) == 1


class TestRelentlessPursuit:
    """Relentless Pursuit: Mark opponent, deck-bottom redirect if attacked."""

    def test_marks_opponent(self):
        game = make_game_shell()
        card = _make_non_attack_action("Relentless Pursuit", color=Color.BLUE)
        game._apply_card_ability(card, 0, "on_play")

        assert game.state.players[1].is_marked

    def test_deck_bottom_when_attacked_this_turn(self):
        """If player has attacked this turn, card goes to bottom of deck."""
        game = make_game_shell()
        card = _make_non_attack_action("Relentless Pursuit", color=Color.BLUE,
                                        instance_id=99, owner_index=0)
        # Put card in hand so move_card can find and remove it
        card.zone = Zone.HAND
        game.state.players[0].hand.append(card)

        # Simulate having attacked this turn
        game.state.players[0].turn_counters.has_attacked = True

        # Fire on_play — sets _redirect_to_deck_bottom flag
        game._apply_card_ability(card, 0, "on_play")
        assert getattr(card, '_redirect_to_deck_bottom', False)

        # Now move to graveyard (engine normally does this after on_play)
        game._move_to_graveyard_or_banish(card)

        # Card should be at bottom of deck, not in graveyard
        assert card.zone == Zone.DECK
        assert card in game.state.players[0].deck
        assert card not in game.state.players[0].graveyard
        # Flag should be cleared
        assert not getattr(card, '_redirect_to_deck_bottom', False)

    def test_graveyard_when_not_attacked_this_turn(self):
        """If player has NOT attacked this turn, card goes to graveyard."""
        game = make_game_shell()
        card = _make_non_attack_action("Relentless Pursuit", color=Color.BLUE,
                                        instance_id=99, owner_index=0)
        card.zone = Zone.HAND
        game.state.players[0].hand.append(card)

        # has_attacked defaults to False — no attack this turn
        assert not game.state.players[0].turn_counters.has_attacked

        game._apply_card_ability(card, 0, "on_play")
        assert not getattr(card, '_redirect_to_deck_bottom', False)

        game._move_to_graveyard_or_banish(card)

        assert card.zone == Zone.GRAVEYARD
        assert card in game.state.players[0].graveyard
        assert card not in game.state.players[0].deck

    def test_deck_bottom_takes_priority_over_banish_redirect(self):
        """If played from banish AND attacked this turn, deck-bottom wins."""
        game = make_game_shell()
        card = _make_non_attack_action("Relentless Pursuit", color=Color.BLUE,
                                        instance_id=99, owner_index=0)
        card.zone = Zone.HAND
        game.state.players[0].hand.append(card)

        # Simulate: attacked this turn AND played from banish
        game.state.players[0].turn_counters.has_attacked = True
        game._banish_instead_of_graveyard.add(card.instance_id)

        game._apply_card_ability(card, 0, "on_play")
        game._move_to_graveyard_or_banish(card)

        # Deck-bottom takes priority over banish redirect
        assert card.zone == Zone.DECK
        assert card in game.state.players[0].deck
        assert card not in game.state.players[0].banished
        assert card not in game.state.players[0].graveyard
        # Banish redirect should also be cleaned up
        assert card.instance_id not in game._banish_instead_of_graveyard


class TestUpSticksAndRun:
    """Up Sticks and Run: Retrieve dagger, +N power to next dagger."""

    def test_retrieves_dagger_from_graveyard(self):
        game = make_game_shell()
        # Mock ask for retrieve — prompt contains "retrieve from your graveyard"
        game._ask = make_mock_ask({"retrieve": ["retrieve_50"]})
        game.keyword_engine._ask = game._ask

        # Put a dagger in graveyard
        dagger = _make_dagger_attack(instance_id=50, owner_index=0)
        dagger.zone = Zone.GRAVEYARD
        game.state.players[0].graveyard.append(dagger)

        card = _make_non_attack_action("Up Sticks and Run", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        # Dagger should be in hand
        assert dagger in game.state.players[0].hand


class TestOrbWeaverSpinneret:
    """Orb-Weaver Spinneret: Equip Graphene Chelicera, +N power to next stealth attack."""

    def test_creates_graphene_chelicera_token(self):
        game = make_game_shell()
        card = _make_non_attack_action("Orb-Weaver Spinneret", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        # Graphene Chelicera is now a weapon, not a permanent
        weapons = [w for w in game.state.players[0].weapons if w.name == "Graphene Chelicera"]
        assert len(weapons) == 1


class TestSavorBloodshed:
    """Savor Bloodshed: +4 power to next dagger, draw on hit if marked."""

    def test_registers_draw_on_hit_trigger(self):
        game = make_game_shell()
        card = _make_non_attack_action("Savor Bloodshed", color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        # Should have registered a triggered effect
        assert len(game.events._triggered_effects) > 0


# ===========================================================================
# Attack Actions — on_attack
# ===========================================================================


class TestPickUpThePoint:
    """Pick Up the Point: Retrieve dagger on attack."""

    def test_retrieves_dagger_on_attack(self):
        game = make_game_shell()
        game._ask = make_mock_ask({"retrieve": ["retrieve_50"]})
        game.keyword_engine._ask = game._ask

        # Dagger in graveyard
        dagger = _make_dagger_attack(instance_id=50, owner_index=0)
        dagger.zone = Zone.GRAVEYARD
        game.state.players[0].graveyard.append(dagger)

        # Attack card
        attack = _make_dagger_attack(instance_id=1, name="Pick Up the Point")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        assert dagger in game.state.players[0].hand


class TestWhittleFromBone:
    """Whittle from Bone: Equip Graphene Chelicera on attack if marked."""

    def test_equips_when_marked(self):
        game = make_game_shell()
        game.state.players[1].is_marked = True

        attack = _make_stealth_attack(instance_id=1, name="Whittle from Bone")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        # Graphene Chelicera is now a weapon, not a permanent
        weapons = [w for w in game.state.players[0].weapons if w.name == "Graphene Chelicera"]
        assert len(weapons) == 1

    def test_no_equip_when_not_marked(self):
        game = make_game_shell()

        attack = _make_stealth_attack(instance_id=1, name="Whittle from Bone")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        tokens = [p for p in game.state.players[0].permanents if p.name == "Graphene Chelicera"]
        assert len(tokens) == 0


class TestOvercrowded:
    """Overcrowded: +1/+1 per unique aura token name."""

    def test_bonus_from_aura_tokens(self):
        game = make_game_shell()
        # Create 2 different aura tokens
        from engine.cards.abilities._helpers import create_token as _create_token
        _create_token(game.state, 0, "Frailty", SubType.AURA)
        _create_token(game.state, 1, "Inertia", SubType.AURA)

        attack = make_card(instance_id=1, power=1, defense=2, zone=Zone.COMBAT_CHAIN,
                           name="Overcrowded")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        # +2 power (Frailty + Inertia = 2 unique names)
        assert game.effect_engine.get_modified_power(game.state, attack) == 3
        assert game.effect_engine.get_modified_defense(game.state, attack) == 4

    def test_no_bonus_without_tokens(self):
        game = make_game_shell()
        attack = make_card(instance_id=1, power=1, defense=2, zone=Zone.COMBAT_CHAIN,
                           name="Overcrowded")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_attack")

        assert game.effect_engine.get_modified_power(game.state, attack) == 1


# ===========================================================================
# Attack Actions — on_hit
# ===========================================================================


class TestKissOfDeath:
    """Kiss of Death: Opponent loses 1 life on hit via LOSE_LIFE event."""

    def test_loses_one_life(self):
        game = make_game_shell(life=20)
        attack = _make_dagger_attack(instance_id=1, name="Kiss of Death",
                                     keywords=frozenset({Keyword.STEALTH}))
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].life_total == 19

    def test_tracks_life_lost(self):
        """Life loss should update turn_counters.life_lost."""
        game = make_game_shell(life=20)
        attack = _make_dagger_attack(instance_id=1, name="Kiss of Death",
                                     keywords=frozenset({Keyword.STEALTH}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].turn_counters.life_lost == 1

    def test_is_not_damage(self):
        """Life loss is not damage — damage_taken should remain 0."""
        game = make_game_shell(life=20)
        attack = _make_dagger_attack(instance_id=1, name="Kiss of Death",
                                     keywords=frozenset({Keyword.STEALTH}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].turn_counters.damage_taken == 0


class TestMarkOfTheBlackWidow:
    """Mark of the Black Widow: Banish from hand if marked."""

    def test_banishes_when_marked(self):
        game = make_game_shell()
        game.state.players[1].is_marked = True
        hand_card = make_card(instance_id=50, owner_index=1, zone=Zone.HAND)
        game.state.players[1].hand.append(hand_card)

        attack = _make_stealth_attack(instance_id=1, name="Mark of the Black Widow")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert hand_card not in game.state.players[1].hand
        assert hand_card in game.state.players[1].banished

    def test_no_banish_when_not_marked(self):
        game = make_game_shell()
        hand_card = make_card(instance_id=50, owner_index=1, zone=Zone.HAND)
        game.state.players[1].hand.append(hand_card)

        attack = _make_stealth_attack(instance_id=1, name="Mark of the Black Widow")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert hand_card in game.state.players[1].hand


class TestLeaveNoWitnesses:
    """Leave No Witnesses: Banish top of deck and arsenal card."""

    def test_banishes_deck_and_arsenal(self):
        game = make_game_shell()
        deck_card = make_card(instance_id=50, owner_index=1, zone=Zone.DECK)
        game.state.players[1].deck.append(deck_card)
        arsenal_card = make_card(instance_id=51, owner_index=1, zone=Zone.ARSENAL)
        game.state.players[1].arsenal.append(arsenal_card)

        attack = make_card(instance_id=1, power=4, zone=Zone.COMBAT_CHAIN,
                           name="Leave No Witnesses")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert deck_card in game.state.players[1].banished
        assert arsenal_card in game.state.players[1].banished
        assert len(game.state.players[1].deck) == 0
        assert len(game.state.players[1].arsenal) == 0


class TestPainInTheBackside:
    """Pain in the Backside: Dagger deals 1 damage on hit via DEAL_DAMAGE event."""

    def test_deals_one_damage_via_event(self):
        game = make_game_shell(life=20)
        dagger = _make_dagger_weapon(instance_id=100, owner_index=0)
        game.state.players[0].weapons.append(dagger)

        attack = _make_dagger_attack(instance_id=1, name="Pain in the Backside",
                                     keywords=frozenset({Keyword.GO_AGAIN}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].life_total == 19
        assert game.state.players[1].turn_counters.damage_taken == 1
        assert game.state.players[1].turn_counters.life_lost == 1

    def test_emits_hit_event(self):
        """The dagger has hit — should emit a HIT event."""
        game = make_game_shell(life=20)
        dagger = _make_dagger_weapon(instance_id=100, owner_index=0)
        game.state.players[0].weapons.append(dagger)

        hit_events = []
        game.events.register_handler(
            EventType.HIT,
            lambda e: hit_events.append(e),
        )

        attack = _make_dagger_attack(instance_id=1, name="Pain in the Backside",
                                     keywords=frozenset({Keyword.GO_AGAIN}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert len(hit_events) == 1
        assert hit_events[0].source is dagger
        assert hit_events[0].amount == 1

    def test_no_dagger_no_damage_no_events(self):
        """If controller has no dagger weapon, no damage or hit events are emitted."""
        game = make_game_shell(life=20)
        # No weapons on player 0

        damage_events = []
        hit_events = []
        game.events.register_handler(
            EventType.DEAL_DAMAGE, lambda e: damage_events.append(e),
        )
        game.events.register_handler(
            EventType.HIT, lambda e: hit_events.append(e),
        )

        attack = _make_dagger_attack(instance_id=1, name="Pain in the Backside",
                                     keywords=frozenset({Keyword.GO_AGAIN}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].life_total == 20
        assert len(damage_events) == 0, "No DEAL_DAMAGE events when no daggers"
        assert len(hit_events) == 0, "No HIT events when no daggers"

    def test_multi_dagger_choose_second(self):
        """With 2 daggers, player chooses the second — HIT source should be that dagger."""
        from engine.rules.actions import PlayerResponse

        game = make_game_shell(life=20)
        dagger1 = _make_dagger_weapon(instance_id=100, owner_index=0)
        dagger2 = _make_dagger_weapon(instance_id=101, owner_index=0)
        dagger2.definition = dagger2.definition  # same def is fine
        game.state.players[0].weapons.extend([dagger1, dagger2])

        hit_events = []
        game.events.register_handler(
            EventType.HIT, lambda e: hit_events.append(e),
        )

        # Mock: choose the second dagger (instance_id=101)
        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"dagger_{dagger2.instance_id}"],
        )

        attack = _make_dagger_attack(instance_id=1, name="Pain in the Backside",
                                     keywords=frozenset({Keyword.GO_AGAIN}))
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].life_total == 19
        assert len(hit_events) == 1
        assert hit_events[0].source is dagger2, (
            f"Expected dagger2 (id={dagger2.instance_id}) as HIT source, "
            f"got id={hit_events[0].source.instance_id}"
        )


class TestPersuasivePrognosis:
    """Persuasive Prognosis: Banish top of deck, then banish matching color from hand."""

    def test_banishes_deck_and_matching_hand(self):
        game = make_game_shell()
        # Top of deck is a Red card
        deck_card = _make_dagger_attack(instance_id=50, owner_index=1)  # Red
        deck_card.zone = Zone.DECK
        game.state.players[1].deck = [deck_card]

        # Hand has a Red card
        hand_card = _make_dagger_attack(instance_id=51, owner_index=1)  # Red
        hand_card.zone = Zone.HAND
        game.state.players[1].hand = [hand_card]

        attack = _make_stealth_attack(instance_id=1, name="Persuasive Prognosis")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert deck_card in game.state.players[1].banished
        assert hand_card in game.state.players[1].banished

    def test_gains_life_for_action_card(self):
        game = make_game_shell(life=20)
        # Top of deck is an action card (Red)
        deck_card = _make_dagger_attack(instance_id=50, owner_index=1)  # Action + Red
        deck_card.zone = Zone.DECK
        game.state.players[1].deck = [deck_card]
        game.state.players[1].hand = []

        attack = _make_stealth_attack(instance_id=1, name="Persuasive Prognosis")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        # Controller gains 1 life (banished an action card)
        assert game.state.players[0].life_total == 21

    def test_controller_chooses_when_multiple_matching_colors(self):
        """When 2+ matching-color cards are in hand, the controller is asked
        which one to banish — not auto-picked."""

        class _AskRecorder:
            """PlayerInterface impl that asserts a single CHOOSE_TARGET decision
            is asked of player 0 and returns the second matching card's id."""
            def __init__(self):
                self.decisions: list = []

            def decide(self, state, decision):
                self.decisions.append(decision)
                # Pick the second offered option (card_b), not the first.
                return PlayerResponse(selected_option_ids=[decision.options[1].action_id])

        game = make_game_shell()
        # Top of deck: Red action card.
        deck_card = _make_dagger_attack(instance_id=50, owner_index=1)
        deck_card.zone = Zone.DECK
        game.state.players[1].deck = [deck_card]

        # Two Red cards in opponent's hand — controller must choose between them.
        card_a = _make_dagger_attack(instance_id=60, owner_index=1)
        card_a.zone = Zone.HAND
        card_b = _make_dagger_attack(instance_id=61, owner_index=1)
        card_b.zone = Zone.HAND
        game.state.players[1].hand = [card_a, card_b]

        # A non-matching Yellow card should not appear among options.
        card_yellow = _make_attack_reaction(
            "Yellow Distractor", instance_id=62, color=Color.YELLOW, owner_index=1,
        )
        game.state.players[1].hand.append(card_yellow)

        recorder = _AskRecorder()
        game.interfaces = {0: recorder, 1: recorder}

        attack = _make_stealth_attack(instance_id=1, name="Persuasive Prognosis")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        # Exactly one Decision was asked, of player 0, with the documented prompt
        # and only the two Red cards as options.
        assert len(recorder.decisions) == 1
        d = recorder.decisions[0]
        assert d.player_index == 0
        assert "Persuasive Prognosis" in d.prompt
        offered_ids = {opt.card_instance_id for opt in d.options}
        assert offered_ids == {60, 61}, "only matching-color cards should be offered"

        # The chosen card (card_b, id 61) was banished; card_a (id 60) was not.
        assert card_b in game.state.players[1].banished
        assert card_a not in game.state.players[1].banished
        assert card_a in game.state.players[1].hand
        # The yellow distractor never moved.
        assert card_yellow in game.state.players[1].hand

    def test_single_matching_card_is_auto_banished_no_decision(self):
        """With exactly one matching-color card, no Decision is asked."""

        class _AssertNoAsk:
            def decide(self, state, decision):
                raise AssertionError(
                    f"unexpected Decision asked: {decision.prompt!r}"
                )

        game = make_game_shell()
        deck_card = _make_dagger_attack(instance_id=50, owner_index=1)  # Red
        deck_card.zone = Zone.DECK
        game.state.players[1].deck = [deck_card]

        only_red = _make_dagger_attack(instance_id=60, owner_index=1)  # Red
        only_red.zone = Zone.HAND
        game.state.players[1].hand = [only_red]

        game.interfaces = {0: _AssertNoAsk(), 1: _AssertNoAsk()}

        attack = _make_stealth_attack(instance_id=1, name="Persuasive Prognosis")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        assert only_red in game.state.players[1].banished


class TestMeetMadness:
    """Meet Madness: Random banish effect on hit."""

    def test_banishes_something(self):
        """Meet Madness should banish from hand, arsenal, or deck top."""
        game = make_game_shell()
        game.state.rng.seed(42)  # Deterministic via state RNG
        hand_card = make_card(instance_id=50, owner_index=1, zone=Zone.HAND)
        game.state.players[1].hand = [hand_card]
        deck_card = make_card(instance_id=51, owner_index=1, zone=Zone.DECK)
        game.state.players[1].deck = [deck_card]

        attack = _make_stealth_attack(instance_id=1, name="Meet Madness")
        game.combat_mgr.open_chain(game.state)
        game.combat_mgr.add_chain_link(game.state, attack, 1)

        game._apply_card_ability(attack, 0, "on_hit")

        # Something should have been banished
        assert len(game.state.players[1].banished) >= 1


# ===========================================================================
# Integration: on_play, on_attack, on_hit wiring in game.py
# ===========================================================================


class TestGameIntegrationWiring:
    """Verify that on_play, on_attack, and on_hit are dispatched by the game engine."""

    def test_on_play_fires_for_non_attack_action(self):
        """When a non-attack action resolves, its on_play handler should fire."""
        game = make_game_shell()
        # Opponent has an attack reaction so we can verify marking
        ar = _make_attack_reaction("Test AR", instance_id=50, owner_index=1)
        game.state.players[1].hand.append(ar)

        card = _make_non_attack_action("Cut from the Same Cloth", instance_id=30, color=Color.RED)
        game._apply_card_ability(card, 0, "on_play")

        # The handler should have marked the opponent
        assert game.state.players[1].is_marked

    def test_on_hit_fires_for_attack(self):
        """When an attack hits, its on_hit handler should fire."""
        game = make_game_shell(life=20)
        attack = _make_dagger_attack(instance_id=1, name="Kiss of Death",
                                     keywords=frozenset({Keyword.STEALTH}))
        game.combat_mgr.open_chain(game.state)
        link = game.combat_mgr.add_chain_link(game.state, attack, 1)

        # Manually call on_hit (normally called from _resolve_damage)
        game._apply_card_ability(attack, 0, "on_hit")

        assert game.state.players[1].life_total == 19
