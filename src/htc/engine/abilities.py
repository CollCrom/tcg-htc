"""AbilityRegistry — card ability dispatch system.

Maps card names to ability handlers keyed by timing (on_play, on_attack,
on_hit, attack_reaction_effect, defense_reaction_effect). Cards without
registered abilities simply have no effect (graceful degradation).

Lookup is by card NAME (not unique_id) so color variants share abilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from htc.cards.instance import CardInstance
    from htc.engine.combat import CombatManager
    from htc.engine.effects import EffectEngine
    from htc.engine.events import EventBus
    from htc.engine.keyword_engine import KeywordEngine
    from htc.state.combat_state import ChainLink
    from htc.state.game_state import GameState

log = logging.getLogger(__name__)

# All recognized timing keys
TIMINGS = (
    "on_play",
    "on_attack",
    "on_hit",
    "attack_reaction_effect",
    "defense_reaction_effect",
    "equipment_instant_effect",
    "permanent_instant_effect",
    "permanent_action_effect",
    "on_become",
    "instant_discard_effect",
    "on_pitch",
)

# Type alias for ability handler functions
AbilityHandler = Callable[["AbilityContext"], None]


@dataclass
class AbilityContext:
    """Everything an ability function needs."""

    state: GameState
    source_card: CardInstance
    controller_index: int
    chain_link: ChainLink | None
    effect_engine: EffectEngine
    events: EventBus
    ask: Callable  # ask callback for player decisions
    keyword_engine: KeywordEngine
    combat_mgr: CombatManager
    extra_data: dict = field(default_factory=dict)

    @property
    def target_was_marked(self) -> bool:
        """Whether the defending hero was marked before the HIT event fired.

        On-hit abilities must use this instead of checking ``is_marked``
        directly, because the HIT handler clears the mark before on_hit
        abilities run.
        """
        return self.extra_data.get("target_was_marked", False)

    def banish_card(
        self, card: "CardInstance", player_index: int, *, face_down: bool = False,
    ) -> None:
        """Move a card to the banish zone and emit a BANISH event.

        This is the preferred way for ability handlers to banish cards,
        instead of manually manipulating zone/lists.
        """
        from htc.engine.events import EventType, GameEvent
        from htc.enums import Zone as _Zone

        player = self.state.players[player_index]
        player.remove_card(card)
        card.zone = _Zone.BANISHED
        card.face_up = not face_down
        player.banished.append(card)
        self.events.emit(GameEvent(
            event_type=EventType.BANISH,
            source=None,
            target_player=player_index,
            card=card,
            data={"face_down": face_down},
        ))
        log.info(
            f"  Banish: {card.name} ({'face-down' if face_down else 'face-up'}) "
            f"for Player {player_index}"
        )


class AbilityRegistry:
    """Registry mapping (timing, card_name) to ability handler functions."""

    def __init__(self) -> None:
        self.on_play: dict[str, AbilityHandler] = {}
        self.on_attack: dict[str, AbilityHandler] = {}
        self.on_hit: dict[str, AbilityHandler] = {}
        self.attack_reaction_effect: dict[str, AbilityHandler] = {}
        self.defense_reaction_effect: dict[str, AbilityHandler] = {}
        self.equipment_instant_effect: dict[str, AbilityHandler] = {}
        self.permanent_instant_effect: dict[str, AbilityHandler] = {}
        self.permanent_action_effect: dict[str, AbilityHandler] = {}
        self.on_become: dict[str, AbilityHandler] = {}
        self.instant_discard_effect: dict[str, AbilityHandler] = {}
        self.on_pitch: dict[str, AbilityHandler] = {}

    def register(self, timing: str, card_name: str, handler: AbilityHandler) -> None:
        """Register an ability handler for a card at a specific timing."""
        if timing not in TIMINGS:
            raise ValueError(f"Unknown timing {timing!r}; valid: {TIMINGS}")
        registry: dict[str, AbilityHandler] = getattr(self, timing)
        registry[card_name] = handler

    def lookup(self, timing: str, card_name: str) -> AbilityHandler | None:
        """Look up the ability handler for a card at a specific timing.

        Returns None if no ability is registered (graceful degradation).
        """
        if timing not in TIMINGS:
            return None
        registry: dict[str, AbilityHandler] = getattr(self, timing)
        return registry.get(card_name)
