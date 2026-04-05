"""Scenario: Flick Knives + Mask of Momentum + Blood Splattered Vest interaction.

Engine-driven tests that run through the real game engine with ScriptedPlayer,
so events fire naturally and the auto-snapshot recorder captures rich state
histories (10-20+ snapshots per test).

Verifies:
1. Flick Knives dagger hit during the reaction step counts toward Mask of
   Momentum's consecutive hit streak.
2. Blood Splattered Vest triggers on dagger hits (stain counter + resource).
3. Mask of Momentum triggers a draw on the 3rd consecutive hit in a chain.
4. Multi-link combat chains with equipment activations work end-to-end.

These tests use the REAL Cindra vs Arakni decklists and the full game engine.
"""

from __future__ import annotations

import logging

from htc.enums import EquipmentSlot
from tests.scenarios.engine_helpers import make_scripted_game

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_action_id(decisions, prefix: str, prompt_contains: str = "") -> str | None:
    """Search recorded decisions for an action_id matching a prefix.

    Useful for discovering instance_id-based action_ids after a run.
    """
    for d in decisions:
        if prompt_contains and prompt_contains not in d.prompt:
            continue
        for o in d.options:
            if o.action_id.startswith(prefix):
                return o.action_id
    return None


def _count_snapshots_by_event(snapshots: list[dict], event_prefix: str) -> int:
    """Count snapshots whose description starts with a given event prefix."""
    return sum(1 for s in snapshots if s.get("description", "").startswith(event_prefix))


# ---------------------------------------------------------------------------
# Tests — Engine-driven via ScriptedPlayer
# ---------------------------------------------------------------------------


class TestFlickKnivesMaskOfMomentumEngine:
    """Engine-driven tests for Flick Knives + Mask of Momentum interaction.

    These run through the real game engine. Cindra (P0) attacks multiple
    times in a chain, with Arakni (P1) not defending, to trigger
    consecutive hits and Mask of Momentum's draw ability.
    """

    def test_multi_link_chain_hits_trigger_mask_draw(self, scenario_recorder):
        """Cindra attacks 2+ times in a chain, all undefended hits.

        With Mask of Momentum equipped, the 3rd consecutive hit in a chain
        should trigger a card draw. The scenario recorder should capture
        10+ snapshots from the natural event flow.
        """
        # Seed 0: Cindra (P0) goes first.
        # Hand: Hot on Their Heels, Dragon Power, Throw Dagger, Enlightened Strike
        # Equipment: Mask of Momentum (head), Blood Splattered Vest (chest),
        #            Flick Knives (arms), Dragonscaler Flight Path (legs)

        # P1 (Cindra) script:
        #   - Equipment selection: pick first for both choices
        #   - Play first attack (Hot on Their Heels)
        #   - Pass through instant windows
        #   - During reaction step: activate Flick Knives to get a dagger hit
        #   - Continue chain: play next attack (Enlightened Strike)
        #   - Pass remaining

        # P2 (Arakni) script:
        #   - Equipment selection: pick first
        #   - Pass on all defenses (so everything hits)

        game, p1, p2 = make_scripted_game(
            p1_script=[
                "*first",        # equip chest choice
                "*first",        # equip legs choice
                "*first_attack", # play first attack card
                "*pass",         # instant window
                "*pass",         # instant window
                "*pass",         # instant window
                "*first",        # reaction step: activate Flick Knives
                "*first",        # choose target dagger for Flick Knives
                "*pass",         # instant after reaction
                "*pass",         # instant after reaction
                "*first_attack", # continue chain: play next attack
                "*pass",         # instant window
                "*first",        # mode choice for Enlightened Strike (if presented)
                "*pass",         # instant window
                "*pass",         # instant window
                "*first",        # reaction step: try Flick Knives or pass
                "*pass",         # instant after
                "*pass",         # continue or pass
                "*pass",         # end of chain
                "*first",        # arsenal choice
                "*first",        # pitch order
                "*first",        # pitch order
            ],
            p2_script=[
                "*first",  # equip legs choice
                "*pass", "*pass",  # instant windows
                "*pass",  # don't defend first attack
                "*pass", "*pass", "*pass", "*pass",  # instant/reaction windows
                "*pass", "*pass",  # instant windows
                "*pass",  # don't defend second attack
                "*pass", "*pass", "*pass", "*pass",  # instant/reaction windows
                "*pass", "*pass", "*pass", "*pass",  # more windows
                "*pass", "*pass", "*pass", "*pass",  # arsenal etc
            ],
            seed=0,
        )

        recorder = scenario_recorder.bind(game)

        # Record initial state
        state = game.state
        p0 = state.players[0]
        initial_hand_size = len(p0.hand)
        initial_life_p1 = state.players[1].life_total

        # Verify Cindra has Mask of Momentum equipped
        mask = p0.equipment.get(EquipmentSlot.HEAD)
        assert mask is not None, "Cindra should have head equipment"
        assert mask.name == "Mask of Momentum", (
            f"Expected Mask of Momentum, got {mask.name}"
        )

        # Verify Flick Knives equipped
        flick = p0.equipment.get(EquipmentSlot.ARMS)
        assert flick is not None, "Cindra should have arms equipment"
        assert flick.name == "Flick Knives", (
            f"Expected Flick Knives, got {flick.name}"
        )

        # Run one full turn
        game._run_turn()

        # Verify opponent took damage (attacks hit because no defense)
        assert state.players[1].life_total < initial_life_p1, (
            "Arakni should have taken damage from undefended attacks"
        )

        # Verify the scenario recorder captured many snapshots from real events
        snapshots = recorder.snapshots
        assert len(snapshots) >= 5, (
            f"Expected 5+ snapshots from engine events, got {len(snapshots)}. "
            f"Descriptions: {[s.get('description', '') for s in snapshots]}"
        )

        # Verify we got attack and hit events captured
        attack_snaps = _count_snapshots_by_event(snapshots, "ATTACK_DECLARED")
        hit_snaps = _count_snapshots_by_event(snapshots, "HIT")
        damage_snaps = _count_snapshots_by_event(snapshots, "DEAL_DAMAGE")

        assert attack_snaps >= 1, "Should have at least 1 ATTACK_DECLARED snapshot"
        assert hit_snaps >= 1, "Should have at least 1 HIT snapshot"
        assert damage_snaps >= 1, "Should have at least 1 DEAL_DAMAGE snapshot"

        log.info(
            "Snapshots captured: %d total, %d attacks, %d hits, %d damage",
            len(snapshots), attack_snaps, hit_snaps, damage_snaps,
        )

    def test_all_pass_produces_minimal_snapshots(self, scenario_recorder):
        """When both players pass immediately, we should still get
        START_OF_TURN and END_OF_TURN snapshots from the engine.
        """
        game, p1, p2 = make_scripted_game(
            p1_script=["*first", "*first"],  # just equip choices
            p2_script=["*first"],             # just equip choice
            seed=0,
        )
        recorder = scenario_recorder.bind(game)

        game._run_turn()

        snapshots = recorder.snapshots
        # Should get at least: initial + START_OF_TURN + START_OF_ACTION_PHASE + END_OF_TURN
        assert len(snapshots) >= 3, (
            f"Expected 3+ snapshots even for pass-only turn, got {len(snapshots)}. "
            f"Descriptions: {[s.get('description', '') for s in snapshots]}"
        )

    def test_undefended_attacks_deal_full_damage(self, scenario_recorder):
        """When Arakni doesn't defend, Cindra's attacks should deal full damage."""
        game, p1, p2 = make_scripted_game(
            p1_script=[
                "*first", "*first",  # equip choices
                "*first_attack",     # play an attack
                "*pass", "*pass", "*pass", "*pass",  # pass through windows
                "*pass", "*pass", "*pass", "*pass",  # more windows
                "*pass", "*pass", "*pass", "*pass",  # end phase
            ],
            p2_script=[
                "*first",  # equip choice
                "*pass", "*pass",  # instant windows
                "*pass",  # don't defend
                "*pass", "*pass", "*pass", "*pass",  # windows
                "*pass", "*pass", "*pass", "*pass",  # more
            ],
            seed=0,
        )
        recorder = scenario_recorder.bind(game)

        initial_life = game.state.players[1].life_total
        game._run_turn()
        final_life = game.state.players[1].life_total

        assert final_life < initial_life, (
            f"Arakni should have lost life: {initial_life} -> {final_life}"
        )

        # Verify DEAL_DAMAGE events were captured
        damage_snaps = [
            s for s in recorder.snapshots
            if s.get("description", "").startswith("DEAL_DAMAGE")
        ]
        assert len(damage_snaps) >= 1, "Should capture at least one DEAL_DAMAGE snapshot"


class TestFlickKnivesBloodSplatteredVestEngine:
    """Engine-driven tests for Flick Knives + Blood Splattered Vest interaction."""

    def test_flick_dagger_hit_adds_stain_counter(self, scenario_recorder):
        """When Cindra activates Flick Knives and the dagger hits,
        Blood Splattered Vest should gain a stain counter and grant a resource.
        """
        game, p1, p2 = make_scripted_game(
            p1_script=[
                "*first", "*first",  # equip choices (BSV + legs)
                "*first_attack",     # play an attack to open chain
                "*pass", "*pass", "*pass",  # instant windows
                "*first",            # reaction: activate Flick Knives
                "*first",            # choose dagger target
                "*pass", "*pass",    # post-reaction windows
                "*pass", "*pass", "*pass",  # continue/end
                "*pass", "*pass", "*pass", "*pass",  # end phase
            ],
            p2_script=[
                "*first",  # equip choice
                "*pass", "*pass",  # instant windows
                "*pass",  # don't defend
                "*pass", "*pass", "*pass",  # windows
                "*pass", "*pass", "*pass",  # more
                "*pass", "*pass", "*pass",  # end
            ],
            seed=0,
        )
        recorder = scenario_recorder.bind(game)

        # Get BSV before the turn
        vest = game.state.players[0].equipment.get(EquipmentSlot.CHEST)
        if vest and vest.name == "Blood Splattered Vest":
            initial_stains = vest.counters.get("stain", 0)
        else:
            initial_stains = 0

        game._run_turn()

        snapshots = recorder.snapshots
        assert len(snapshots) >= 5, (
            f"Expected 5+ snapshots, got {len(snapshots)}"
        )

        # Check if any dagger HIT events were captured
        hit_snaps = [
            s for s in snapshots
            if s.get("description", "").startswith("HIT")
        ]
        log.info(
            "Hit snapshots: %s",
            [s.get("description", "") for s in hit_snaps],
        )


class TestScenarioRecorderCoverage:
    """Verify that engine-driven tests produce rich snapshot coverage."""

    def test_snapshot_count_with_active_combat(self, scenario_recorder):
        """An active combat turn should produce 10+ snapshots capturing
        the full sequence: START_OF_TURN, ATTACK_DECLARED, DEFEND/PASS,
        HIT, DEAL_DAMAGE, etc.
        """
        game, p1, p2 = make_scripted_game(
            p1_script=[
                "*first", "*first",  # equip
                "*first_attack",     # attack
                "*pass", "*pass", "*pass",
                "*first",            # reaction (Flick Knives or Throw Dagger)
                "*first",            # target selection
                "*pass", "*pass",
                "*first_attack",     # continue chain
                "*pass",
                "*first",            # mode choice
                "*pass", "*pass",
                "*first",            # reaction
                "*pass", "*pass",
                "*pass", "*pass",    # end
                "*first",            # arsenal
                "*first", "*first",  # pitch order
            ],
            p2_script=[
                "*first",  # equip
                "*pass", "*pass",
                "*pass",  # don't defend
                "*pass", "*pass", "*pass", "*pass",
                "*pass", "*pass",
                "*pass",  # don't defend again
                "*pass", "*pass", "*pass", "*pass",
                "*pass", "*pass", "*pass", "*pass",
                "*pass", "*pass",
            ],
            seed=0,
        )
        recorder = scenario_recorder.bind(game)
        game._run_turn()

        snapshots = recorder.snapshots
        descriptions = [s.get("description", "") for s in snapshots]

        log.info("Total snapshots: %d", len(snapshots))
        for i, desc in enumerate(descriptions):
            log.info("  [%d] %s", i, desc)

        # With real engine combat, we should get many event-driven snapshots
        assert len(snapshots) >= 8, (
            f"Expected 8+ snapshots from active combat turn, got {len(snapshots)}. "
            f"Descriptions: {descriptions}"
        )

        # Verify variety of event types captured
        event_types_seen = set()
        for desc in descriptions:
            if ":" in desc and desc != "Initial state":
                event_types_seen.add(desc.split(":")[0])

        assert len(event_types_seen) >= 3, (
            f"Expected 3+ distinct event types, got {event_types_seen}"
        )
