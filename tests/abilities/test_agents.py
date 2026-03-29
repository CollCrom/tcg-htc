"""Tests for Agent of Chaos Demi-Hero abilities.

Verifies:
1. Return to the brood — shared by all 6 agents
2. Arakni, Redback — AR: +3 power, stealth => go again
3. Arakni, Black Widow — AR: +3 power, stealth => on-hit banish from hand
4. Arakni, Funnel Web — AR: +3 power, stealth => on-hit banish from arsenal
5. Arakni, Tarantula — Passive: dagger hit => lose 1 life; AR: dagger +3 power
6. Arakni, Orb-Weaver — Instant: create token + stealth buff
7. Arakni, Trap-Door — On-become: search deck and banish face-down
"""

from __future__ import annotations

from random import Random

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.agents import (
    ReturnToBroodTrigger,
    TarantulaDaggerHitTrigger,
    TrapDoorOnBecomeTrigger,
    register_agent_abilities,
    deregister_agent_triggers,
    AGENT_TRIGGER_TAG,
)
from htc.engine.actions import Decision, PlayerResponse
from htc.engine.events import EventBus, EventType, GameEvent
from htc.engine.effects import EffectEngine
from htc.enums import (
    CardType,
    Color,
    DecisionType,
    EquipmentSlot,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from htc.state.combat_state import ChainLink
from htc.state.game_state import GameState
from htc.state.player_state import PlayerState

from tests.conftest import make_card, make_game_shell, make_state
from tests.abilities.conftest import (
    make_dagger_attack,
    make_dagger_weapon,
    make_stealth_attack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hero(
    name: str = "Arakni, Marionette",
    instance_id: int = 900,
    owner_index: int = 0,
    health: int = 20,
    intellect: int = 4,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"hero-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        health=health,
        intellect=intellect,
        arcane=None,
        types=frozenset({CardType.HERO}),
        subtypes=frozenset(),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Hero - Assassin",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HERO,
    )


def _make_demi_hero(
    name: str = "Arakni, Redback",
    instance_id: int = 800,
    owner_index: int = 0,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"demi-{instance_id}",
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


def _make_assassin_hand_card(
    instance_id: int = 500,
    name: str = "Assassin Fodder",
    owner_index: int = 0,
) -> CardInstance:
    """An Assassin card suitable for discarding as cost."""
    defn = CardDefinition(
        unique_id=f"assassin-{instance_id}",
        name=name,
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
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_non_assassin_card(
    instance_id: int = 600,
    owner_index: int = 0,
) -> CardInstance:
    """A non-Assassin card (cannot be discarded for agent AR cost)."""
    defn = CardDefinition(
        unique_id=f"generic-{instance_id}",
        name="Generic Card",
        color=Color.BLUE,
        pitch=3,
        cost=0,
        power=2,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset(),
        functional_text="",
        type_text="Generic Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


def _make_trap_card(
    instance_id: int = 700,
    name: str = "Booby Trap",
    owner_index: int = 0,
) -> CardInstance:
    defn = CardDefinition(
        unique_id=f"trap-{instance_id}",
        name=name,
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.TRAP}),
        supertypes=frozenset({SuperType.ASSASSIN}),
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Trap Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.DECK,
    )


def _setup_agent_test(agent_name: str = "Arakni, Redback"):
    """Set up a game shell with a player transformed into an agent.

    Returns (game, agent_card, original_hero, chain_link).
    """
    game = make_game_shell()
    state = game.state
    state.rng = Random(42)

    original_hero = _make_hero(instance_id=900, owner_index=0)
    state.players[0].hero = original_hero
    state.players[0].life_total = 20

    enemy_hero = _make_hero(name="Cindra", instance_id=901, owner_index=1)
    state.players[1].hero = enemy_hero
    state.players[1].life_total = 20

    agent = _make_demi_hero(name=agent_name, instance_id=800, owner_index=0)
    state.players[0].demi_heroes = [agent]

    # Transform
    game._become_agent_of_chaos(0, agent)

    # Set up a combat chain link
    attack = make_stealth_attack(instance_id=10, power=3, owner_index=0)
    link = ChainLink(
        link_number=1,
        active_attack=attack,
        attack_target_index=1,
    )
    state.combat_chain.chain_links.append(link)

    # Always-pass mock ask
    game._ask = lambda d: PlayerResponse(selected_option_ids=["pass"])

    return game, agent, original_hero, link


def _build_ability_context(game, card, link=None, controller_index=0):
    """Build an AbilityContext from the game shell."""
    from htc.engine.abilities import AbilityContext
    return AbilityContext(
        state=game.state,
        source_card=card,
        controller_index=controller_index,
        chain_link=link,
        effect_engine=game.effect_engine,
        events=game.events,
        ask=game._ask,
        keyword_engine=game.keyword_engine,
        combat_mgr=game.combat_mgr,
    )


def make_stealth_assassin_attack(
    instance_id: int = 10,
    power: int = 3,
    owner_index: int = 0,
) -> CardInstance:
    """Assassin attack with Stealth."""
    defn = CardDefinition(
        unique_id=f"stealth-assassin-{instance_id}",
        name="Stealth Assassin Strike",
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
        zone=Zone.COMBAT_CHAIN,
    )


def make_non_stealth_assassin_attack(
    instance_id: int = 11,
    power: int = 4,
    owner_index: int = 0,
) -> CardInstance:
    """Assassin attack WITHOUT Stealth."""
    defn = CardDefinition(
        unique_id=f"assassin-nostlth-{instance_id}",
        name="Assassin Strike",
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
        keywords=frozenset(),
        functional_text="",
        type_text="Assassin Attack Action",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.COMBAT_CHAIN,
    )


# ---------------------------------------------------------------------------
# 1. Return to the Brood
# ---------------------------------------------------------------------------


class TestReturnToBrood:
    """Shared 'return to the brood' mechanic for all agents."""

    def test_return_to_brood_on_end_phase(self):
        """Agent reverts to original hero at start of end phase."""
        game, agent, original, _ = _setup_agent_test()
        assert game.state.players[0].hero.name == "Arakni, Redback"
        assert game.state.players[0].original_hero is original

        # Emit START_OF_END_PHASE
        game.events.emit(GameEvent(
            event_type=EventType.START_OF_END_PHASE,
            target_player=0,
        ))
        game._process_pending_triggers()

        assert game.state.players[0].hero is original
        assert game.state.players[0].original_hero is None

    def test_return_to_brood_preserves_life(self):
        """Life total unchanged when reverting."""
        game, _, original, _ = _setup_agent_test()
        game.state.players[0].life_total = 12

        game.events.emit(GameEvent(
            event_type=EventType.START_OF_END_PHASE,
            target_player=0,
        ))
        game._process_pending_triggers()

        assert game.state.players[0].life_total == 12

    def test_return_to_brood_deregisters_triggers(self):
        """Agent triggers are removed when reverting."""
        game, _, _, _ = _setup_agent_test("Arakni, Tarantula")

        # Tarantula should have a dagger-hit trigger registered
        agent_triggers = [
            t for t in game.events._triggered_effects
            if getattr(t, AGENT_TRIGGER_TAG, None) == 0
        ]
        assert len(agent_triggers) >= 1  # at least the brood trigger + tarantula

        game.events.emit(GameEvent(
            event_type=EventType.START_OF_END_PHASE,
            target_player=0,
        ))
        game._process_pending_triggers()

        # All agent triggers for player 0 should be gone
        remaining = [
            t for t in game.events._triggered_effects
            if getattr(t, AGENT_TRIGGER_TAG, None) == 0
        ]
        assert remaining == []

    def test_no_revert_if_not_transformed(self):
        """If player is not in agent form, nothing happens."""
        game = make_game_shell()
        hero = _make_hero()
        game.state.players[0].hero = hero
        game.state.players[0].original_hero = None

        game._return_to_brood(0)
        assert game.state.players[0].hero is hero

    def test_return_to_brood_only_fires_on_own_end_phase(self):
        """The trigger only fires on the controller's end phase."""
        game, agent, original, _ = _setup_agent_test()

        # Other player's end phase should NOT trigger revert
        game.events.emit(GameEvent(
            event_type=EventType.START_OF_END_PHASE,
            target_player=1,
        ))
        game._process_pending_triggers()

        assert game.state.players[0].hero.name == "Arakni, Redback"


# ---------------------------------------------------------------------------
# 2. Arakni, Redback
# ---------------------------------------------------------------------------


class TestRedback:
    """Arakni, Redback — AR: discard Assassin, Assassin attack +3 power.
    If stealth: also go again."""

    def test_redback_ar_plus_3_power(self):
        """Redback AR grants +3 power to Assassin attack."""
        game, agent, _, _ = _setup_agent_test("Arakni, Redback")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_non_stealth_assassin_attack(instance_id=11, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        # Mock ask to discard the assassin card
        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _redback_ar
        ctx = _build_ability_context(game, agent, link)
        _redback_ar(ctx)

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 4 + 3  # base 4 + 3

    def test_redback_ar_stealth_gets_go_again(self):
        """Stealth Assassin attack also gets Go Again."""
        game, agent, _, _ = _setup_agent_test("Arakni, Redback")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _redback_ar
        ctx = _build_ability_context(game, agent, link)
        _redback_ar(ctx)

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 3 + 3

        kws = game.effect_engine.get_modified_keywords(game.state, attack)
        assert Keyword.GO_AGAIN in kws

    def test_redback_ar_no_go_again_without_stealth(self):
        """Non-stealth Assassin attack does NOT get Go Again."""
        game, agent, _, _ = _setup_agent_test("Arakni, Redback")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_non_stealth_assassin_attack(instance_id=11, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _redback_ar
        ctx = _build_ability_context(game, agent, link)
        _redback_ar(ctx)

        kws = game.effect_engine.get_modified_keywords(game.state, attack)
        assert Keyword.GO_AGAIN not in kws

    def test_redback_ar_no_assassin_to_discard(self):
        """AR does nothing if no Assassin card in hand."""
        game, agent, _, _ = _setup_agent_test("Arakni, Redback")
        non_assassin = _make_non_assassin_card(instance_id=600, owner_index=0)
        game.state.players[0].hand = [non_assassin]

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        from htc.cards.abilities.agents import _redback_ar
        ctx = _build_ability_context(game, agent, link)
        _redback_ar(ctx)

        # No power bonus
        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 3  # unchanged

    def test_redback_ar_non_assassin_attack_ignored(self):
        """AR ignores non-Assassin attacks."""
        game, agent, _, _ = _setup_agent_test("Arakni, Redback")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        # Generic (non-Assassin) attack
        attack = make_card(instance_id=20, name="Generic Strike", power=5)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        from htc.cards.abilities.agents import _redback_ar
        ctx = _build_ability_context(game, agent, link)
        _redback_ar(ctx)

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 5  # unchanged


# ---------------------------------------------------------------------------
# 3. Arakni, Black Widow
# ---------------------------------------------------------------------------


class TestBlackWidow:
    """Arakni, Black Widow — AR: +3 power, stealth => on-hit banish from hand."""

    def test_black_widow_ar_plus_3(self):
        """Black Widow AR grants +3 power."""
        game, agent, _, _ = _setup_agent_test("Arakni, Black Widow")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _black_widow_ar
        ctx = _build_ability_context(game, agent, link)
        _black_widow_ar(ctx)

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 3 + 3

    def test_black_widow_stealth_on_hit_banishes_hand(self):
        """Stealth attack with Black Widow banishes from defender's hand on hit."""
        game, agent, _, _ = _setup_agent_test("Arakni, Black Widow")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        # Give defender some cards in hand
        defender_card = _make_non_assassin_card(instance_id=601, owner_index=1)
        game.state.players[1].hand = [defender_card]

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _black_widow_ar
        ctx = _build_ability_context(game, agent, link)
        _black_widow_ar(ctx)

        # Now simulate the hit
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=6,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Defender should have had a card banished from hand
        assert len(game.state.players[1].hand) == 0
        assert len(game.state.players[1].banished) == 1
        assert game.state.players[1].banished[0] is defender_card

    def test_black_widow_no_stealth_no_banish(self):
        """Non-stealth attack gets +3 power but no banish trigger."""
        game, agent, _, _ = _setup_agent_test("Arakni, Black Widow")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_non_stealth_assassin_attack(instance_id=11, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        defender_card = _make_non_assassin_card(instance_id=601, owner_index=1)
        game.state.players[1].hand = [defender_card]

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _black_widow_ar
        ctx = _build_ability_context(game, agent, link)
        _black_widow_ar(ctx)

        # Hit event
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=7,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Defender hand should be untouched
        assert len(game.state.players[1].hand) == 1


# ---------------------------------------------------------------------------
# 4. Arakni, Funnel Web
# ---------------------------------------------------------------------------


class TestFunnelWeb:
    """Arakni, Funnel Web — AR: +3 power, stealth => on-hit banish arsenal."""

    def test_funnel_web_stealth_on_hit_banishes_arsenal(self):
        """Stealth attack banishes from defender's arsenal on hit."""
        game, agent, _, _ = _setup_agent_test("Arakni, Funnel Web")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        # Give defender a card in arsenal
        arsenal_card = _make_non_assassin_card(instance_id=602, owner_index=1)
        arsenal_card.zone = Zone.ARSENAL
        game.state.players[1].arsenal = [arsenal_card]

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _funnel_web_ar
        ctx = _build_ability_context(game, agent, link)
        _funnel_web_ar(ctx)

        # Simulate hit
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=6,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        assert len(game.state.players[1].arsenal) == 0
        assert len(game.state.players[1].banished) == 1
        assert game.state.players[1].banished[0] is arsenal_card

    def test_funnel_web_no_stealth_no_banish(self):
        """Non-stealth attack: +3 power but no arsenal banish."""
        game, agent, _, _ = _setup_agent_test("Arakni, Funnel Web")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_non_stealth_assassin_attack(instance_id=11, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        arsenal_card = _make_non_assassin_card(instance_id=602, owner_index=1)
        arsenal_card.zone = Zone.ARSENAL
        game.state.players[1].arsenal = [arsenal_card]

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _funnel_web_ar
        ctx = _build_ability_context(game, agent, link)
        _funnel_web_ar(ctx)

        # Hit
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=7,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Arsenal untouched
        assert len(game.state.players[1].arsenal) == 1

    def test_funnel_web_empty_arsenal_no_error(self):
        """On-hit trigger handles empty arsenal gracefully."""
        game, agent, _, _ = _setup_agent_test("Arakni, Funnel Web")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        game.state.players[1].arsenal = []

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _funnel_web_ar
        ctx = _build_ability_context(game, agent, link)
        _funnel_web_ar(ctx)

        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=6,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # No crash
        assert game.state.players[1].banished == []


# ---------------------------------------------------------------------------
# 5. Arakni, Tarantula
# ---------------------------------------------------------------------------


class TestTarantula:
    """Arakni, Tarantula — dagger hit lose 1 life + AR dagger +3 power."""

    def test_tarantula_dagger_hit_causes_life_loss(self):
        """Dagger hit triggers 1 life loss (via LOSE_LIFE event)."""
        game, agent, _, _ = _setup_agent_test("Arakni, Tarantula")

        dagger_attack = make_dagger_attack(instance_id=15, power=1, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = dagger_attack

        initial_life = game.state.players[1].life_total

        # Emit HIT event for the dagger
        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=dagger_attack,
            target_player=1,
            amount=1,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # Defender lost 1 life from the passive
        assert game.state.players[1].life_total == initial_life - 1

    def test_tarantula_non_dagger_no_life_loss(self):
        """Non-dagger attacks do NOT trigger life loss."""
        game, agent, _, _ = _setup_agent_test("Arakni, Tarantula")

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        initial_life = game.state.players[1].life_total

        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=attack,
            target_player=1,
            amount=3,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        assert game.state.players[1].life_total == initial_life

    def test_tarantula_ar_dagger_plus_3(self):
        """Tarantula AR: dagger gets +3 power."""
        game, agent, _, _ = _setup_agent_test("Arakni, Tarantula")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        dagger_attack = make_dagger_attack(instance_id=15, power=1, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = dagger_attack

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _tarantula_ar
        ctx = _build_ability_context(game, agent, link)
        _tarantula_ar(ctx)

        modified_power = game.effect_engine.get_modified_power(game.state, dagger_attack)
        assert modified_power == 1 + 3

    def test_tarantula_ar_non_dagger_ignored(self):
        """Tarantula AR ignores non-dagger attacks."""
        game, agent, _, _ = _setup_agent_test("Arakni, Tarantula")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        attack = make_stealth_assassin_attack(instance_id=12, owner_index=0)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = attack

        from htc.cards.abilities.agents import _tarantula_ar
        ctx = _build_ability_context(game, agent, link)
        _tarantula_ar(ctx)

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 3  # unchanged

    def test_tarantula_opponent_dagger_no_trigger(self):
        """Opponent's dagger hit does NOT trigger Tarantula's passive."""
        game, agent, _, _ = _setup_agent_test("Arakni, Tarantula")

        # Dagger owned by opponent (player 1)
        dagger_attack = make_dagger_attack(instance_id=15, power=1, owner_index=1)
        link = game.state.combat_chain.chain_links[0]
        link.active_attack = dagger_attack

        initial_life = game.state.players[0].life_total

        game.events.emit(GameEvent(
            event_type=EventType.HIT,
            source=dagger_attack,
            target_player=0,
            amount=1,
            data={"chain_link": link},
        ))
        game._process_pending_triggers()

        # No life loss from passive (damage was already dealt by combat, not the passive)
        assert game.state.players[0].life_total == initial_life


# ---------------------------------------------------------------------------
# 6. Arakni, Orb-Weaver
# ---------------------------------------------------------------------------


class TestOrbWeaver:
    """Arakni, Orb-Weaver — instant: create Graphene Chelicera + stealth buff."""

    def test_orb_weaver_creates_token(self):
        """Orb-Weaver instant creates a Graphene Chelicera token."""
        game, agent, _, _ = _setup_agent_test("Arakni, Orb-Weaver")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _orb_weaver_instant
        ctx = _build_ability_context(game, agent, None)
        _orb_weaver_instant(ctx)

        permanents = game.state.players[0].permanents
        assert len(permanents) == 1
        assert permanents[0].name == "Graphene Chelicera"

    def test_orb_weaver_stealth_attack_gets_plus_3(self):
        """Next stealth attack this turn gets +3 power."""
        game, agent, _, _ = _setup_agent_test("Arakni, Orb-Weaver")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _orb_weaver_instant
        ctx = _build_ability_context(game, agent, None)
        _orb_weaver_instant(ctx)

        # Now declare a stealth attack
        stealth_attack = make_stealth_assassin_attack(instance_id=20, owner_index=0)
        game.events.emit(GameEvent(
            event_type=EventType.ATTACK_DECLARED,
            source=stealth_attack,
            target_player=1,
        ))
        game._process_pending_triggers()

        modified_power = game.effect_engine.get_modified_power(game.state, stealth_attack)
        assert modified_power == 3 + 3

    def test_orb_weaver_non_stealth_no_buff(self):
        """Non-stealth attack does NOT get the +3 power buff."""
        game, agent, _, _ = _setup_agent_test("Arakni, Orb-Weaver")
        assassin_card = _make_assassin_hand_card(instance_id=500, owner_index=0)
        game.state.players[0].hand.append(assassin_card)

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"discard_{assassin_card.instance_id}"]
        )

        from htc.cards.abilities.agents import _orb_weaver_instant
        ctx = _build_ability_context(game, agent, None)
        _orb_weaver_instant(ctx)

        # Non-stealth attack
        attack = make_non_stealth_assassin_attack(instance_id=21, owner_index=0)
        game.events.emit(GameEvent(
            event_type=EventType.ATTACK_DECLARED,
            source=attack,
            target_player=1,
        ))
        game._process_pending_triggers()

        modified_power = game.effect_engine.get_modified_power(game.state, attack)
        assert modified_power == 4  # unchanged

    def test_orb_weaver_no_assassin_to_discard(self):
        """Instant does nothing if no Assassin card to discard."""
        game, agent, _, _ = _setup_agent_test("Arakni, Orb-Weaver")
        game.state.players[0].hand = [_make_non_assassin_card(instance_id=600)]

        from htc.cards.abilities.agents import _orb_weaver_instant
        ctx = _build_ability_context(game, agent, None)
        _orb_weaver_instant(ctx)

        assert len(game.state.players[0].permanents) == 0


# ---------------------------------------------------------------------------
# 7. Arakni, Trap-Door
# ---------------------------------------------------------------------------


class TestTrapDoor:
    """Arakni, Trap-Door — on-become: search deck, banish face-down."""

    def test_trap_door_on_become_banishes_card(self):
        """Transforming into Trap-Door searches deck and banishes a card."""
        game = make_game_shell()
        state = game.state
        state.rng = Random(42)

        original_hero = _make_hero(instance_id=900, owner_index=0)
        state.players[0].hero = original_hero
        state.players[0].life_total = 20

        enemy_hero = _make_hero(name="Cindra", instance_id=901, owner_index=1)
        state.players[1].hero = enemy_hero

        agent = _make_demi_hero(name="Arakni, Trap-Door", instance_id=800)
        state.players[0].demi_heroes = [agent]

        # Put some cards in deck
        trap_card = _make_trap_card(instance_id=700, owner_index=0)
        other_card = _make_assassin_hand_card(instance_id=701, owner_index=0)
        other_card.zone = Zone.DECK
        state.players[0].deck = [trap_card, other_card]

        # Mock ask: choose the trap card
        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"banish_{trap_card.instance_id}"]
        )

        game._become_agent_of_chaos(0, agent)

        # Trap card should be banished face-down
        assert trap_card in state.players[0].banished
        assert trap_card.zone == Zone.BANISHED
        assert trap_card.face_up is False
        # Deck should have remaining card (shuffled)
        assert len(state.players[0].deck) == 1

    def test_trap_door_empty_deck(self):
        """On-become with empty deck does nothing."""
        game = make_game_shell()
        state = game.state
        state.rng = Random(42)

        original_hero = _make_hero(instance_id=900, owner_index=0)
        state.players[0].hero = original_hero
        state.players[0].life_total = 20

        enemy_hero = _make_hero(name="Cindra", instance_id=901, owner_index=1)
        state.players[1].hero = enemy_hero

        agent = _make_demi_hero(name="Arakni, Trap-Door", instance_id=800)
        state.players[0].demi_heroes = [agent]
        state.players[0].deck = []

        game._ask = lambda d: PlayerResponse(selected_option_ids=["pass"])
        game._become_agent_of_chaos(0, agent)

        assert state.players[0].banished == []

    def test_trap_door_shuffles_deck_after_search(self):
        """Deck is shuffled after searching."""
        game = make_game_shell()
        state = game.state
        state.rng = Random(42)

        original_hero = _make_hero(instance_id=900, owner_index=0)
        state.players[0].hero = original_hero
        state.players[0].life_total = 20

        enemy_hero = _make_hero(name="Cindra", instance_id=901, owner_index=1)
        state.players[1].hero = enemy_hero

        agent = _make_demi_hero(name="Arakni, Trap-Door", instance_id=800)
        state.players[0].demi_heroes = [agent]

        # Fill deck with several cards
        cards = []
        for i in range(5):
            c = _make_assassin_hand_card(instance_id=710 + i, owner_index=0)
            c.zone = Zone.DECK
            cards.append(c)
        state.players[0].deck = list(cards)

        game._ask = lambda d: PlayerResponse(
            selected_option_ids=[f"banish_{cards[0].instance_id}"]
        )

        game._become_agent_of_chaos(0, agent)

        # After banishing 1, deck should have 4 cards
        assert len(state.players[0].deck) == 4


# ---------------------------------------------------------------------------
# Integration: Agent abilities registered through _become_agent_of_chaos
# ---------------------------------------------------------------------------


class TestAgentAbilityRegistration:
    """Verify that _become_agent_of_chaos registers the correct abilities."""

    def test_redback_registered_as_attack_reaction(self):
        """Redback AR is registered in the ability registry."""
        game, _, _, _ = _setup_agent_test("Arakni, Redback")
        handler = game.ability_registry.lookup(
            "attack_reaction_effect", "Arakni, Redback"
        )
        assert handler is not None

    def test_tarantula_registers_dagger_hit_trigger(self):
        """Tarantula registers a persistent dagger-hit trigger on the EventBus."""
        game, _, _, _ = _setup_agent_test("Arakni, Tarantula")
        tarantula_triggers = [
            t for t in game.events._triggered_effects
            if isinstance(t, TarantulaDaggerHitTrigger)
        ]
        assert len(tarantula_triggers) == 1

    def test_orb_weaver_registered_as_instant(self):
        """Orb-Weaver instant is registered in the ability registry."""
        game, _, _, _ = _setup_agent_test("Arakni, Orb-Weaver")
        handler = game.ability_registry.lookup(
            "equipment_instant_effect", "Arakni, Orb-Weaver"
        )
        assert handler is not None

    def test_all_agents_register_brood_trigger(self):
        """All agents register a return-to-brood trigger."""
        for name in [
            "Arakni, Redback",
            "Arakni, Black Widow",
            "Arakni, Funnel Web",
            "Arakni, Tarantula",
            "Arakni, Orb-Weaver",
            "Arakni, Trap-Door",
        ]:
            game, _, _, _ = _setup_agent_test(name)
            brood_triggers = [
                t for t in game.events._triggered_effects
                if isinstance(t, ReturnToBroodTrigger)
            ]
            assert len(brood_triggers) >= 1, f"{name} missing ReturnToBroodTrigger"
