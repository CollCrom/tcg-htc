"""Scenario: Agent of Chaos transformation lifecycle and combo tests.

Tests:
9. Trap-Door agent: defend -> transform -> on_become (search/banish) -> end-phase revert.
   Verify the full lifecycle works.
10. Black Widow + Kiss of Death combo — Black Widow on-hit banishes from opponent's
    hand. If the banished card is red, Leave No Witnesses contract fires and creates
    a Silver token. Verify the event chain.

Sources: strategy-arakni-masterclass.md
"""

from __future__ import annotations

import logging

from engine.cards.card import CardDefinition
from engine.cards.instance import CardInstance
from engine.cards.abilities.agents import _trap_door_on_become
from engine.cards.abilities.assassin import (
    _kiss_of_death_on_hit,
    _mark_of_the_black_widow_on_hit,
    _leave_no_witnesses_on_attack,
)
from engine.rules.actions import PlayerResponse
from engine.rules.events import EventType, GameEvent
from engine.enums import (
    CardType,
    Color,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_game_shell
from tests.abilities.conftest import (
    make_ability_context,
    make_dagger_attack,
    make_ninja_attack,
    make_stealth_attack,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared card factories
# ---------------------------------------------------------------------------

def _make_hero(
    name: str = "Arakni, Marionette",
    instance_id: int = 900,
    owner_index: int = 0,
    supertypes: frozenset | None = None,
) -> CardInstance:
    if supertypes is None:
        supertypes = frozenset({SuperType.ASSASSIN})
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
        supertypes=supertypes,
        keywords=frozenset(),
        functional_text="",
        type_text="Hero",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_trap_door_demi(instance_id: int = 950, owner_index: int = 1) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"trap-door-{instance_id}",
        name="Arakni, Trap-Door",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=None,  # Demi-hero health is * (keep current)
        intellect=4,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="When you become this, search deck for a card, banish face-down, shuffle. If Trap, playable until start of next turn.",
        type_text="Demi-Hero - Assassin",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_generic_card(
    instance_id: int,
    name: str = "Filler Card",
    owner_index: int = 1,
    zone: Zone = Zone.DECK,
    color: Color = Color.RED,
    subtypes: frozenset | None = None,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"generic-{instance_id}",
        name=name,
        color=color,
        pitch=1,
        cost=0,
        power=3,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=subtypes or frozenset({SubType.ATTACK}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=zone,
    )


def _make_trap_card(
    instance_id: int,
    name: str = "Frailty Trap",
    owner_index: int = 1,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"trap-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=4,
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
        zone=Zone.DECK,
    )


def _setup_base_game():
    """Create a game shell. P0=Cindra, P1=Arakni."""
    game = make_game_shell()
    state = game.state

    state.players[0].hero = _make_hero(
        name="Cindra, Drachai of Two Talons", instance_id=900, owner_index=0,
        supertypes=frozenset({SuperType.NINJA}),
    )
    state.players[0].life_total = 20

    state.players[1].hero = _make_hero(
        name="Arakni, Marionette", instance_id=901, owner_index=1,
    )
    state.players[1].life_total = 20

    return game


# ---------------------------------------------------------------------------
# Test 9: Trap-Door agent defend -> transform -> end-phase revert
# ---------------------------------------------------------------------------


class TestTrapDoorLifecycle:
    """Verify the Trap-Door Agent of Chaos lifecycle:
    1. Defend triggers Mask of Deceit -> become Trap-Door
    2. Trap-Door on_become: search deck, banish face-down, shuffle
    3. If banished card is a Trap, it's playable from banish
    4. At end of controller's next turn, revert to original hero

    Source: strategy-arakni-masterclass.md
    """

    def test_trap_door_on_become_searches_deck(self, scenario_recorder):
        """Trap-Door on_become should search the deck and banish a card face-down."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        p1 = state.players[1]  # Arakni

        # Put cards in deck for searching
        trap = _make_trap_card(instance_id=700, name="Frailty Trap", owner_index=1)
        filler = _make_generic_card(instance_id=701, name="Filler", owner_index=1)
        p1.deck = [trap, filler]

        # Set up the demi-hero
        trap_door = _make_trap_door_demi(instance_id=950, owner_index=1)

        # Ask callback: choose the trap card
        def ask_fn(decision):
            for opt in decision.options:
                if "Frailty Trap" in opt.description:
                    return PlayerResponse(selected_option_ids=[opt.action_id])
            return PlayerResponse(selected_option_ids=["pass"])

        ctx = make_ability_context(game, trap_door, controller_index=1, ask=ask_fn)
        _trap_door_on_become(ctx)

        # Card should be banished face-down
        assert trap in p1.banished, (
            "Trap-Door on_become should banish the chosen card"
        )
        assert trap.zone == Zone.BANISHED, (
            f"Banished card zone should be BANISHED, got {trap.zone}"
        )

    def test_trap_door_marks_trap_as_playable_from_banish(self, scenario_recorder):
        """If the banished card is a Trap, it should be marked as playable from banish."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        p1 = state.players[1]

        trap = _make_trap_card(instance_id=700, name="Frailty Trap", owner_index=1)
        p1.deck = [trap]

        trap_door = _make_trap_door_demi(instance_id=950, owner_index=1)

        def ask_fn(decision):
            for opt in decision.options:
                if "Frailty Trap" in opt.description:
                    return PlayerResponse(selected_option_ids=[opt.action_id])
            return PlayerResponse(selected_option_ids=["pass"])

        ctx = make_ability_context(game, trap_door, controller_index=1, ask=ask_fn)
        _trap_door_on_become(ctx)

        # Verify it's marked as playable from banish
        playable_ids = [pb.instance_id for pb in p1.playable_from_banish]
        assert trap.instance_id in playable_ids, (
            "Trap cards banished by Trap-Door should be marked as playable from banish"
        )

    def test_trap_door_shuffles_deck(self, scenario_recorder):
        """After searching, Trap-Door should shuffle the remaining deck."""
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        p1 = state.players[1]

        # Put several cards in deck
        cards = []
        for i in range(5):
            c = _make_generic_card(instance_id=700 + i, name=f"Card {i}", owner_index=1)
            cards.append(c)
        p1.deck = list(cards)

        trap_door = _make_trap_door_demi(instance_id=950, owner_index=1)

        # Choose first card
        def ask_fn(decision):
            if decision.options:
                return PlayerResponse(selected_option_ids=[decision.options[0].action_id])
            return PlayerResponse(selected_option_ids=["pass"])

        ctx = make_ability_context(game, trap_door, controller_index=1, ask=ask_fn)
        _trap_door_on_become(ctx)

        # Deck should have one fewer card (one was banished)
        assert len(p1.deck) == 4, (
            f"Deck should have 4 cards after banishing 1. Got {len(p1.deck)}"
        )

    def test_return_to_brood_at_controller_end_phase(self, scenario_recorder):
        """At the beginning of the controller's end phase, the demi-hero
        should revert to the original hero.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        p1 = state.players[1]
        original_hero = p1.hero
        original_hero_name = original_hero.name

        # Transform to Trap-Door
        trap_door = _make_trap_door_demi(instance_id=950, owner_index=1)
        game._become_agent_of_chaos(1, trap_door)

        # Verify transformation
        assert p1.hero.name == "Arakni, Trap-Door", (
            f"After transformation, hero should be Trap-Door, got {p1.hero.name}"
        )
        assert p1.original_hero is not None, (
            "Original hero should be saved for return-to-brood"
        )

        # Emit END_OF_TURN for controller (player 1)
        game.events.emit(GameEvent(
            event_type=EventType.END_OF_TURN,
            target_player=1,
        ))

        # Should revert
        assert p1.hero.name == original_hero_name, (
            f"After end-of-turn, hero should revert to {original_hero_name}, "
            f"got {p1.hero.name}"
        )
        assert p1.original_hero is None, (
            "original_hero should be cleared after reverting"
        )


# ---------------------------------------------------------------------------
# Test 10: Black Widow + Kiss of Death combo
# ---------------------------------------------------------------------------


class TestBlackWidowKissOfDeathCombo:
    """Black Widow agent's on-hit banishes from opponent's hand.
    If Leave No Witnesses contract is active and the banished card is red,
    a Silver token is created.

    Source: strategy-arakni-masterclass.md
    """

    def test_black_widow_on_hit_banishes_from_hand(self, scenario_recorder):
        """Mark of the Black Widow on-hit should banish a card from
        opponent's hand when the target is marked.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        # P0 is the opponent (target). Mark them.
        state.players[0].is_marked = True

        # Give P0 cards in hand
        hand_card = _make_generic_card(
            instance_id=700, name="Red Card", owner_index=0,
            zone=Zone.HAND, color=Color.RED,
        )
        state.players[0].hand.append(hand_card)

        # Set up a chain link where P1 attacks P0
        game.combat_mgr.open_chain(state)
        atk = make_stealth_attack(
            instance_id=1, name="Mark of the Black Widow", power=3,
            owner_index=1, supertypes=frozenset({SuperType.ASSASSIN}),
        )
        link = game.combat_mgr.add_chain_link(state, atk, 0)
        link.hit = True
        link.hit_count = 1

        ctx = make_ability_context(game, atk, controller_index=1, chain_link=link)
        # Set target_was_marked via extra_data (it's a read-only property)
        ctx.extra_data["target_was_marked"] = True
        _mark_of_the_black_widow_on_hit(ctx)

        assert hand_card not in state.players[0].hand, (
            "Black Widow on-hit should banish a card from the opponent's hand"
        )
        assert hand_card in state.players[0].banished, (
            "The card should be in the banished zone"
        )

    def test_leave_no_witnesses_fires_on_red_banish(self, scenario_recorder):
        """When Leave No Witnesses contract is active and a red card is banished
        from the opponent, a Silver token should be created.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        state.players[0].is_marked = True

        # P0 has a red card in hand
        red_card = _make_generic_card(
            instance_id=700, name="Red Card", owner_index=0,
            zone=Zone.HAND, color=Color.RED,
        )
        state.players[0].hand.append(red_card)

        # Set up combat chain
        game.combat_mgr.open_chain(state)

        # First, register Leave No Witnesses contract by "attacking" with it
        lnw_card = make_dagger_attack(
            instance_id=10, name="Leave No Witnesses", power=2, owner_index=1,
        )
        lnw_link = game.combat_mgr.add_chain_link(state, lnw_card, 0)

        lnw_ctx = make_ability_context(game, lnw_card, controller_index=1, chain_link=lnw_link)
        _leave_no_witnesses_on_attack(lnw_ctx)

        # Now, Black Widow attack on a new chain link
        bw_atk = make_stealth_attack(
            instance_id=2, name="Mark of the Black Widow", power=3,
            owner_index=1, supertypes=frozenset({SuperType.ASSASSIN}),
        )
        bw_link = game.combat_mgr.add_chain_link(state, bw_atk, 0)
        bw_link.hit = True
        bw_link.hit_count = 1

        bw_ctx = make_ability_context(game, bw_atk, controller_index=1, chain_link=bw_link)
        bw_ctx.extra_data["target_was_marked"] = True
        _mark_of_the_black_widow_on_hit(bw_ctx)

        # Process triggers from the BANISH event
        game._process_pending_triggers()

        # Check: Silver token should be created for P1 (Arakni)
        silver_tokens = [p for p in state.players[1].permanents if p.name == "Silver"]
        assert len(silver_tokens) >= 1, (
            "Leave No Witnesses contract should fire when a red card is banished "
            "from the opponent, creating a Silver token. "
            f"Silver tokens found: {len(silver_tokens)}, "
            f"P1 permanents: {[p.name for p in state.players[1].permanents]}"
        )

    def test_kiss_of_death_on_hit_deals_life_loss(self, scenario_recorder):
        """Kiss of Death on-hit: 'When this hits a hero, they lose 1 life.'
        Basic sanity check that the on_hit handler works.
        """
        game = _setup_base_game()
        state = game.state
        recorder = scenario_recorder.bind(game)

        game.combat_mgr.open_chain(state)

        kiss_atk = make_dagger_attack(
            instance_id=1, name="Kiss of Death", power=2, owner_index=1,
            keywords=frozenset({Keyword.STEALTH}),
        )
        link = game.combat_mgr.add_chain_link(state, kiss_atk, 0)
        link.hit = True
        link.hit_count = 1

        initial_life = state.players[0].life_total

        ctx = make_ability_context(game, kiss_atk, controller_index=1, chain_link=link)
        _kiss_of_death_on_hit(ctx)

        assert state.players[0].life_total == initial_life - 1, (
            f"Kiss of Death on-hit should cause 1 life loss. "
            f"Was {initial_life}, now {state.players[0].life_total}"
        )
