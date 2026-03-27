"""High-value combat scenario tests covering:

1. Full combat chain with defense reactions
2. Multi-chain-link combat (4+ attacks, exercises Rupture context)
3. Dominate + equipment defense (equipment not limited)
4. Playing cards from arsenal through correct flow
5. Game-over during combat (life to 0 mid-combat)
"""

from htc.cards.card import CardDefinition
from htc.cards.instance import CardInstance
from htc.engine.actions import PlayerResponse
from htc.enums import (
    CardType,
    EquipmentSlot,
    Keyword,
    SubType,
    Zone,
)
from htc.state.combat_state import ChainLink, CombatChainState
from tests.conftest import (
    make_card,
    make_equipment,
    make_game_shell,
    make_pitch_card,
    make_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_defense_reaction(
    instance_id: int = 30,
    name: str = "Sink Below",
    defense: int = 4,
    cost: int = 0,
    owner_index: int = 1,
) -> CardInstance:
    """Create a defense reaction card."""
    defn = CardDefinition(
        unique_id=f"dr-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=None,
        defense=defense,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.DEFENSE_REACTION}),
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
        zone=Zone.HAND,
    )


def _make_go_again_attack(
    instance_id: int = 1,
    name: str = "GA Attack",
    power: int = 3,
    cost: int = 0,
    owner_index: int = 0,
) -> CardInstance:
    """Create an attack action card with Go Again."""
    defn = CardDefinition(
        unique_id=f"ga-{instance_id}",
        name=name,
        color=None,
        pitch=None,
        cost=cost,
        power=power,
        defense=3,
        health=None,
        intellect=None,
        arcane=None,
        types=frozenset({CardType.ACTION}),
        subtypes=frozenset({SubType.ATTACK}),
        supertypes=frozenset(),
        keywords=frozenset({Keyword.GO_AGAIN}),
        functional_text="",
        type_text="",
    )
    return CardInstance(
        instance_id=instance_id,
        definition=defn,
        owner_index=owner_index,
        zone=Zone.HAND,
    )


# ---------------------------------------------------------------------------
# 1. Full combat chain with defense reactions
# ---------------------------------------------------------------------------


def test_combat_with_defense_reaction():
    """Play an attack, defender plays a defense reaction, verify damage
    accounts for the defense reaction's defense value."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    state = game.state

    # Set up an attack on the combat chain (power=6)
    attack = make_card(instance_id=1, name="Big Attack", power=6, cost=0)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    # Defender has a hand card for defend step (defense=2)
    hand_defender = make_card(
        instance_id=10, name="Block Card", defense=2, power=1,
        owner_index=1, zone=Zone.HAND,
    )
    state.players[1].hand = [hand_defender]

    # Defender defends with the hand card
    game._ask = lambda d: PlayerResponse(
        selected_option_ids=[f"defend_{hand_defender.instance_id}"]
        if "Defend" in d.prompt else ["pass"]
    )
    game._defend_step()

    # Now add a defense reaction as a defending card (simulating reaction step)
    dr = _make_defense_reaction(instance_id=30, defense=4, owner_index=1)
    game.combat_mgr.add_defender(state, link, dr)

    # Verify total defense and damage
    total_defense = game.combat_mgr.get_total_defense(state, link)
    attack_power = game.combat_mgr.get_attack_power(state, link)
    damage = game.combat_mgr.calculate_damage(state, link)

    assert total_defense == 6, f"Expected 6 (2 hand + 4 DR), got {total_defense}"
    assert attack_power == 6
    assert damage == 0, "6 power - 6 defense = 0 damage (blocked)"


def test_combat_damage_reduced_by_defense_reaction():
    """Defense reaction reduces but doesn't fully block damage."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    state = game.state

    attack = make_card(instance_id=1, name="Heavy Attack", power=8, cost=0)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    # Defender only has a defense reaction (defense=3)
    dr = _make_defense_reaction(instance_id=30, defense=3, owner_index=1)
    game.combat_mgr.add_defender(state, link, dr)

    damage = game.combat_mgr.calculate_damage(state, link)
    assert damage == 5, f"Expected 5 (8 power - 3 defense), got {damage}"


# ---------------------------------------------------------------------------
# 2. Multi-chain-link combat (4+ attacks)
# ---------------------------------------------------------------------------


def test_multi_chain_link_four_attacks():
    """Play 4 attacks in sequence, verify chain link numbers and Rupture
    check is active on link 4."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    state = game.state
    game.combat_mgr.open_chain(state)

    attacks = []
    for i in range(4):
        atk = make_card(
            instance_id=i + 1,
            name=f"Attack {i + 1}",
            power=3,
            cost=0,
            keywords=frozenset({Keyword.RUPTURE}) if i == 3 else frozenset(),
        )
        attacks.append(atk)
        link = game.combat_mgr.add_chain_link(state, atk, attack_target_index=1)
        assert link.link_number == i + 1

    assert state.combat_chain.num_chain_links == 4

    # The 4th link should qualify for Rupture
    link4 = state.combat_chain.chain_links[3]
    assert game.keyword_engine.check_rupture_active(state, link4) is True

    # The 3rd link should NOT qualify (only 3rd link)
    link3 = state.combat_chain.chain_links[2]
    # link3 doesn't have Rupture keyword, so it's False regardless of position
    assert game.keyword_engine.check_rupture_active(state, link3) is False


def test_multi_chain_link_five_attacks():
    """5 attacks in sequence -- verify chain state integrity."""
    game = make_game_shell(action_points={0: 1, 1: 0})
    state = game.state
    game.combat_mgr.open_chain(state)

    for i in range(5):
        atk = make_card(instance_id=i + 1, name=f"Attack {i + 1}", power=2, cost=0)
        link = game.combat_mgr.add_chain_link(state, atk, attack_target_index=1)

    assert state.combat_chain.num_chain_links == 5
    assert state.combat_chain.active_link.link_number == 5

    # Each link should have its attack
    for i, link in enumerate(state.combat_chain.chain_links):
        assert link.active_attack is not None
        assert link.active_attack.name == f"Attack {i + 1}"


# ---------------------------------------------------------------------------
# 3. Dominate + equipment defense
# ---------------------------------------------------------------------------


def test_dominate_does_not_limit_equipment_defense():
    """Dominate limits hand cards to 1, but equipment should still be
    available to defend (equipment is not from hand)."""
    game = make_game_shell()
    state = game.state

    # Attack with Dominate
    attack = make_card(
        instance_id=1, name="Dominate Attack", power=8, cost=0,
        keywords=frozenset({Keyword.DOMINATE}),
    )
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    # Defender has 2 hand cards and 1 equipment
    hand1 = make_card(instance_id=10, name="Hand Card 1", defense=3, owner_index=1, zone=Zone.HAND)
    hand2 = make_card(instance_id=11, name="Hand Card 2", defense=3, owner_index=1, zone=Zone.HAND)
    chest = make_equipment(instance_id=50, name="Chest Plate", defense=2, subtype=SubType.CHEST, owner_index=1)

    state.players[1].hand = [hand1, hand2]
    state.players[1].equipment[EquipmentSlot.CHEST] = chest

    # Try to defend with both hand cards and the equipment
    game._ask = lambda d: PlayerResponse(
        selected_option_ids=[
            f"defend_{hand1.instance_id}",
            f"defend_{hand2.instance_id}",
            f"defend_{chest.instance_id}",
        ]
    ) if "Defend" in d.prompt else PlayerResponse(selected_option_ids=["pass"])

    game._defend_step()

    # Dominate: only 1 hand card should have been accepted
    # Equipment should always be accepted (not limited by Dominate)
    hand_defenders = [c for c in link.defending_cards if c in [hand1, hand2]]
    equip_defenders = [c for c in link.defending_cards if c is chest]

    assert len(hand_defenders) == 1, (
        f"Dominate should limit hand defense to 1, got {len(hand_defenders)}"
    )
    assert len(equip_defenders) == 1, (
        "Equipment should NOT be limited by Dominate"
    )
    # Total defenders: 1 hand + 1 equipment = 2
    assert len(link.defending_cards) == 2


def test_dominate_allows_all_equipment():
    """Multiple equipment pieces can defend even under Dominate."""
    game = make_game_shell()
    state = game.state

    attack = make_card(
        instance_id=1, power=10, cost=0,
        keywords=frozenset({Keyword.DOMINATE}),
    )
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    # Multiple equipment
    head = make_equipment(instance_id=50, name="Helm", defense=1, subtype=SubType.HEAD, owner_index=1)
    chest = make_equipment(instance_id=51, name="Chest", defense=2, subtype=SubType.CHEST, owner_index=1)
    legs = make_equipment(instance_id=52, name="Legs", defense=1, subtype=SubType.LEGS, owner_index=1)

    state.players[1].hand = []
    state.players[1].equipment[EquipmentSlot.HEAD] = head
    state.players[1].equipment[EquipmentSlot.CHEST] = chest
    state.players[1].equipment[EquipmentSlot.LEGS] = legs

    game._ask = lambda d: PlayerResponse(
        selected_option_ids=[
            f"defend_{head.instance_id}",
            f"defend_{chest.instance_id}",
            f"defend_{legs.instance_id}",
        ]
    ) if "Defend" in d.prompt else PlayerResponse(selected_option_ids=["pass"])

    game._defend_step()

    assert len(link.defending_cards) == 3, (
        "All 3 equipment pieces should defend under Dominate"
    )


# ---------------------------------------------------------------------------
# 4. Playing cards from arsenal
# ---------------------------------------------------------------------------


def test_play_card_from_arsenal():
    """A card played from arsenal should go through the correct flow:
    removed from arsenal, placed on stack, costs paid."""
    game = make_game_shell(action_points={0: 1, 1: 0}, resource_points={0: 3, 1: 0})
    state = game.state

    # Put an attack card in player 0's arsenal
    arsenal_card = make_card(
        instance_id=5, name="Arsenal Attack", power=4, cost=1,
        owner_index=0, zone=Zone.ARSENAL,
    )
    state.players[0].arsenal = [arsenal_card]
    state.players[0].hand = []

    # Play the card
    game._play_card(0, arsenal_card)

    # Card should be removed from arsenal
    assert arsenal_card not in state.players[0].arsenal
    # Card should be on the stack
    assert not game.stack_mgr.is_empty(state)
    top = game.stack_mgr.top(state)
    assert top is not None
    assert top.card is arsenal_card
    # Turn counters updated
    assert state.players[0].turn_counters.num_attack_cards_played == 1
    # Combat chain opened for attack
    assert state.combat_chain.is_open


def test_play_non_attack_from_arsenal():
    """Non-attack action from arsenal also goes through correct flow."""
    game = make_game_shell(action_points={0: 1, 1: 0}, resource_points={0: 3, 1: 0})
    state = game.state

    arsenal_card = make_card(
        instance_id=5, name="Arsenal Action", power=None, defense=3,
        cost=0, is_attack=False, owner_index=0, zone=Zone.ARSENAL,
    )
    state.players[0].arsenal = [arsenal_card]
    state.players[0].hand = []

    game._play_card(0, arsenal_card)

    assert arsenal_card not in state.players[0].arsenal
    assert not game.stack_mgr.is_empty(state)
    assert state.players[0].turn_counters.num_non_attack_actions_played == 1
    # Combat chain should NOT open for non-attack
    assert not state.combat_chain.is_open


# ---------------------------------------------------------------------------
# 5. Game-over during combat
# ---------------------------------------------------------------------------


def test_game_over_mid_combat_damage_step():
    """If damage reduces life to 0 during the damage step, game correctly
    signals game_over."""
    game = make_game_shell(action_points={0: 1, 1: 0}, life=5)
    state = game.state

    attack = make_card(instance_id=1, name="Lethal Attack", power=7, cost=0)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    # No defenders
    state.players[1].hand = []

    # Mock _ask to always pass
    game._ask = lambda d: PlayerResponse(selected_option_ids=["pass"])

    # Run defend step (no defenders)
    game._defend_step()

    # Run damage step
    game._damage_step()

    # Player 1 started at 5 life, took 7 damage -> 0 (clamped)
    assert state.players[1].life_total == 0
    assert state.game_over is True
    assert state.winner == 0


def test_game_over_stops_combat_chain():
    """After a player dies mid-combat, the combat loop should not continue
    to resolution step."""
    game = make_game_shell(action_points={0: 1, 1: 0}, life=3)
    state = game.state

    attack = make_card(
        instance_id=1, name="Fatal Strike", power=5, cost=0,
        keywords=frozenset({Keyword.GO_AGAIN}),
    )
    # Put on stack and resolve into combat chain
    game.stack_mgr.add_card_layer(state, attack, 0)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    state.players[1].hand = []
    game._ask = lambda d: PlayerResponse(selected_option_ids=["pass"])

    # Run the combat steps -- damage should kill player 1
    game._defend_step()
    game._damage_step()

    assert state.game_over is True
    assert state.winner == 0
    # Even though attack had Go Again, game is over
    assert state.players[1].life_total == 0


def test_both_alive_combat_continues():
    """If damage doesn't kill anyone, combat chain proceeds normally."""
    game = make_game_shell(action_points={0: 1, 1: 0}, life=20)
    state = game.state

    attack = make_card(instance_id=1, name="Normal Attack", power=4, cost=0)
    game.combat_mgr.open_chain(state)
    link = game.combat_mgr.add_chain_link(state, attack, attack_target_index=1)

    state.players[1].hand = []
    game._ask = lambda d: PlayerResponse(selected_option_ids=["pass"])

    game._defend_step()
    game._damage_step()

    # Player 1 took 4 damage: 20 - 4 = 16
    assert state.players[1].life_total == 16
    assert state.game_over is False
    assert link.hit is True
    assert link.damage_dealt == 4
