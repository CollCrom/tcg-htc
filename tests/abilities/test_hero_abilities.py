"""Tests for hero ability triggered effects.

Covers Arakni, Marionette and Cindra, Dracai of Retribution.
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.cards.abilities.heroes import (
    ArakniMarionetteTrigger,
    CindraRetributionTrigger,
    register_hero_abilities,
)
from htc.engine.continuous import EffectDuration
from htc.engine.events import EventBus, EventType, GameEvent
from htc.enums import (
    CardType,
    Color,
    Keyword,
    SubType,
    SuperType,
    Zone,
)
from tests.conftest import make_card, make_game_shell


def _make_stealth_attack(
    instance_id: int = 1,
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
) -> CardInstance:
    """Create an attack action card with Stealth keyword."""
    defn = CardDefinition(
        unique_id=f"stealth-{instance_id}",
        name="Stealth Strike",
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


def _make_non_stealth_attack(
    instance_id: int = 2,
    power: int = 4,
    owner_index: int = 0,
) -> CardInstance:
    """Create an attack action card without Stealth keyword."""
    defn = CardDefinition(
        unique_id=f"nostealth-{instance_id}",
        name="Regular Strike",
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
# Arakni, Marionette
# ---------------------------------------------------------------------------


def test_arakni_stealth_vs_marked_gets_plus_one_power():
    """Stealth attack vs marked hero gets +1 power from Arakni ability."""
    game = make_game_shell()
    attack = _make_stealth_attack(instance_id=1, power=3, owner_index=0)

    # Mark the opponent
    game.state.players[1].is_marked = True

    # Register Arakni ability
    register_hero_abilities(
        "Arakni, Marionette", 0, game.events, game.effect_engine,
        lambda: game.state,
    )

    # Open combat chain and add attack
    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Emit attack declared event
    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    # Attack should have +1 power (3 + 1 = 4)
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4


def test_arakni_stealth_vs_marked_gets_go_again_on_hit():
    """Stealth attack vs marked hero gets Go Again when it hits."""
    game = make_game_shell()
    attack = _make_stealth_attack(instance_id=1, power=3, owner_index=0)

    game.state.players[1].is_marked = True

    register_hero_abilities(
        "Arakni, Marionette", 0, game.events, game.effect_engine,
        lambda: game.state,
    )

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Emit attack declared — triggers the ability
    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    # Go Again should NOT be present before the hit
    modified_kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in modified_kws

    # Simulate a hit
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=4,
        data={"chain_link": link},
    ))
    game._process_pending_triggers()

    # Now Go Again should be granted
    modified_kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN in modified_kws


def test_arakni_stealth_vs_unmarked_gets_nothing():
    """Stealth attack vs unmarked hero gets no bonus from Arakni."""
    game = make_game_shell()
    attack = _make_stealth_attack(instance_id=1, power=3, owner_index=0)

    # Opponent is NOT marked
    game.state.players[1].is_marked = False

    register_hero_abilities(
        "Arakni, Marionette", 0, game.events, game.effect_engine,
        lambda: game.state,
    )

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    # Power should be unchanged
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 3

    # No Go Again trigger should be registered
    modified_kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in modified_kws


def test_arakni_non_stealth_vs_marked_gets_nothing():
    """Non-stealth attack vs marked hero gets no bonus from Arakni."""
    game = make_game_shell()
    attack = _make_non_stealth_attack(instance_id=1, power=4, owner_index=0)

    game.state.players[1].is_marked = True

    register_hero_abilities(
        "Arakni, Marionette", 0, game.events, game.effect_engine,
        lambda: game.state,
    )

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    # Power should be unchanged — no stealth, no bonus
    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4


def test_arakni_non_stealth_unmarked_gets_nothing():
    """Non-stealth attack vs unmarked hero gets nothing from Arakni."""
    game = make_game_shell()
    attack = _make_non_stealth_attack(instance_id=1, power=4, owner_index=0)

    game.state.players[1].is_marked = False

    register_hero_abilities(
        "Arakni, Marionette", 0, game.events, game.effect_engine,
        lambda: game.state,
    )

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    effective_power = game.effect_engine.get_modified_power(game.state, attack)
    assert effective_power == 4

    modified_kws = game.effect_engine.get_modified_keywords(game.state, attack)
    assert Keyword.GO_AGAIN not in modified_kws


# ---------------------------------------------------------------------------
# Cindra, Dracai of Retribution
# ---------------------------------------------------------------------------


def test_cindra_creates_fealty_token_on_hitting_marked_hero():
    """Cindra creates a Fealty token when hitting a marked hero."""
    game = make_game_shell()
    attack = make_card(instance_id=1, power=4, zone=Zone.COMBAT_CHAIN, owner_index=0)

    # Mark the opponent
    game.state.players[1].is_marked = True

    register_hero_abilities(
        "Cindra, Dracai of Retribution", 0, game.events, game.effect_engine,
        lambda: game.state, game=game,
    )

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    # Emit attack declared — Cindra records that target is marked
    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    # No token yet
    assert len(game.state.players[0].permanents) == 0

    # Emit hit event — Cindra should create a Fealty token
    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=4,
        data={"chain_link": link},
    ))
    game._process_pending_triggers()

    # Player 0 should now have a Fealty token
    fealty_tokens = [
        p for p in game.state.players[0].permanents if p.name == "Fealty"
    ]
    assert len(fealty_tokens) == 1


def test_cindra_no_token_when_hitting_unmarked_hero():
    """Cindra does not create a Fealty token when hitting an unmarked hero."""
    game = make_game_shell()
    attack = make_card(instance_id=1, power=4, zone=Zone.COMBAT_CHAIN, owner_index=0)

    # Opponent is NOT marked
    game.state.players[1].is_marked = False

    register_hero_abilities(
        "Cindra, Dracai of Retribution", 0, game.events, game.effect_engine,
        lambda: game.state, game=game,
    )

    game.combat_mgr.open_chain(game.state)
    link = game.combat_mgr.add_chain_link(game.state, attack, 1)

    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack,
        target_player=1,
        data={"chain_link": link, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack,
        target_player=1,
        amount=4,
        data={"chain_link": link},
    ))
    game._process_pending_triggers()

    # No tokens should be created
    assert len(game.state.players[0].permanents) == 0


def test_cindra_multiple_hits_create_multiple_tokens():
    """Cindra creates a token for each hit against a marked hero."""
    game = make_game_shell()

    register_hero_abilities(
        "Cindra, Dracai of Retribution", 0, game.events, game.effect_engine,
        lambda: game.state, game=game,
    )

    # First attack — mark the opponent
    game.state.players[1].is_marked = True
    attack1 = make_card(instance_id=1, power=4, zone=Zone.COMBAT_CHAIN, owner_index=0)

    game.combat_mgr.open_chain(game.state)
    link1 = game.combat_mgr.add_chain_link(game.state, attack1, 1)

    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack1, target_player=1,
        data={"chain_link": link1, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack1, target_player=1, amount=4,
        data={"chain_link": link1},
    ))
    game._process_pending_triggers()

    assert len(game.state.players[0].permanents) == 1

    # Second attack — re-mark the opponent (as would happen in a real game)
    game.state.players[1].is_marked = True
    attack2 = make_card(instance_id=2, power=3, zone=Zone.COMBAT_CHAIN, owner_index=0)
    link2 = game.combat_mgr.add_chain_link(game.state, attack2, 1)

    game.events.emit(GameEvent(
        event_type=EventType.ATTACK_DECLARED,
        source=attack2, target_player=1,
        data={"chain_link": link2, "attacker_index": 0},
    ))
    game._process_pending_triggers()

    game.events.emit(GameEvent(
        event_type=EventType.HIT,
        source=attack2, target_player=1, amount=3,
        data={"chain_link": link2},
    ))
    game._process_pending_triggers()

    # Should now have 2 Fealty tokens
    fealty_tokens = [
        p for p in game.state.players[0].permanents if p.name == "Fealty"
    ]
    assert len(fealty_tokens) == 2
