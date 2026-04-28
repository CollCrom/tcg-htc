"""HTTP match server: two PlayerInterface seats served over JSON HTTP.

Wraps :class:`engine.rules.game.Game` so two external agents can drive
both seats via short-lived HTTP requests. Wire payloads are identical to
the JSONL stdio protocol (``engine.player.stdio_player``); only the
transport differs.

Usage::

    python tools/match_server.py --port 8080 --seed 7 \\
        --deck-a ref/decks/decklist-cindra-blue.md \\
        --deck-b ref/decks/decklist-arakni.md

Endpoints
---------
``GET  /pending?player=A`` →
    ``{"pending": {<decision payload>} | null, "status": {<status>}}``
    The decision payload mirrors the JSONL stdio ``decision`` message
    (decision_type, prompt, options, redacted ``state``). Pending is
    ``null`` when it is not this player's turn to choose, when the
    engine is mid-resolution between decisions, or after the game ends.

``POST /action?player=A`` (body: ``{"selected_option_ids": ["..."]}``) →
    ``{"ok": true, "status": {<status>}}``
    Submits an action for the player's currently-pending decision. 409
    if there is no pending decision; 400 if action_ids are unknown for
    the current decision.

``GET  /status`` →
    ``{"status": "in_progress" | "game_over" | "error", ...}``

The engine runs on a worker thread; HTTP runs on a thread pool. The
``decide`` callback blocks the engine thread on a per-player condition
variable until ``POST /action`` delivers a response.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from engine.cards.card_db import CardDatabase
from engine.decks.deck_list import DeckList, parse_markdown_decklist
from engine.rules.actions import Decision, PlayerResponse
from engine.rules.game import Game
from engine.state.game_state import GameState
from engine.state.snapshot import snapshot_for

log = logging.getLogger("match_server")


# ---------------------------------------------------------------------------
# PlayerInterface bridged to HTTP
# ---------------------------------------------------------------------------


class HttpBridgePlayer:
    """A PlayerInterface that exposes its current decision to HTTP clients.

    The engine thread calls :meth:`decide` and blocks on a Condition until
    an HTTP handler thread delivers a response via :meth:`submit`.
    """

    def __init__(self, player_index: int) -> None:
        self.player_index = player_index
        self.effect_engine: Any = None  # set by the server before play() starts
        self._cv = threading.Condition()
        self._pending: dict | None = None
        self._allowed_ids: set[str] = set()
        self._response: PlayerResponse | None = None
        self._closed = False

    # ----- PlayerInterface -----

    def decide(self, game_state: GameState, decision: Decision) -> PlayerResponse:
        if self.effect_engine is None:
            raise RuntimeError("HttpBridgePlayer.effect_engine must be set before decide()")
        payload = self._encode(decision, game_state)
        with self._cv:
            self._pending = payload
            self._allowed_ids = {opt.action_id for opt in decision.options}
            self._cv.notify_all()
            while self._response is None and not self._closed:
                self._cv.wait()
            if self._closed and self._response is None:
                raise RuntimeError("match server closed mid-decision")
            response = self._response
            self._response = None
            self._pending = None
            self._allowed_ids = set()
            self._cv.notify_all()
        assert response is not None
        return response

    # ----- HTTP-side ops -----

    def get_pending(self) -> dict | None:
        with self._cv:
            return self._pending

    def submit(self, ids: list[str]) -> tuple[bool, str]:
        with self._cv:
            if self._pending is None:
                return False, "no pending decision for this player"
            unknown = [i for i in ids if i not in self._allowed_ids]
            if unknown:
                return False, f"unknown action_ids for current decision: {unknown}"
            self._response = PlayerResponse(selected_option_ids=list(ids))
            self._cv.notify_all()
        return True, "ok"

    def close(self) -> None:
        """Unblock any pending decide() so the engine thread can exit."""
        with self._cv:
            self._closed = True
            self._cv.notify_all()

    # ----- helpers -----

    def _encode(self, decision: Decision, game_state: GameState) -> dict:
        # During _setup_game, equipment-selection decisions can fire before
        # state.players is fully populated. snapshot_for requires 2 players,
        # so emit a minimal placeholder state for those pre-setup prompts.
        if len(game_state.players) < 2:
            snap = {
                "phase": "pre_game_setup",
                "note": (
                    "Pre-game equipment / hero selection. Full per-player "
                    "state is not yet available; pick from `options` based on "
                    "their description."
                ),
            }
        else:
            snap = snapshot_for(game_state, self.player_index, self.effect_engine)
        return {
            "type": "decision",
            "player_index": decision.player_index,
            "decision_type": decision.decision_type.value,
            "prompt": decision.prompt,
            "min_selections": decision.min_selections,
            "max_selections": decision.max_selections,
            "options": [
                {**asdict(opt), "action_type": opt.action_type.value}
                for opt in decision.options
            ],
            "state": snap,
        }


# ---------------------------------------------------------------------------
# Match orchestration
# ---------------------------------------------------------------------------


class MatchServer:
    def __init__(
        self,
        db: CardDatabase,
        deck_a: DeckList,
        deck_b: DeckList,
        seed: int,
    ) -> None:
        self.player_a = HttpBridgePlayer(0)
        self.player_b = HttpBridgePlayer(1)
        self.players: dict[str, HttpBridgePlayer] = {"A": self.player_a, "B": self.player_b}
        self.game = Game(db, deck_a, deck_b, self.player_a, self.player_b, seed=seed)
        self.player_a.effect_engine = self.game.effect_engine
        self.player_b.effect_engine = self.game.effect_engine
        self.deck_a_hero = deck_a.hero_name
        self.deck_b_hero = deck_b.hero_name
        self.seed = seed
        self.result: Any = None
        self.error: str | None = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="game-thread")

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            self.result = self.game.play()
        except Exception as exc:  # noqa: BLE001 — surfaced via /status
            self.error = f"{type(exc).__name__}: {exc}"
            log.exception("game thread crashed")

    def is_done(self) -> bool:
        return self.result is not None or self.error is not None

    def status(self) -> dict:
        if self.error is not None:
            return {"status": "error", "error": self.error}
        if self.result is not None:
            return {
                "status": "game_over",
                "winner": self.result.winner,
                "winner_seat": (
                    None if self.result.winner is None
                    else ("A" if self.result.winner == 0 else "B")
                ),
                "turns": self.result.turns,
                "final_life": list(self.result.final_life),
                "heroes": {"A": self.deck_a_hero, "B": self.deck_b_hero},
            }
        return {
            "status": "in_progress",
            "turn": self.game.state.turn_number,
            "heroes": {"A": self.deck_a_hero, "B": self.deck_b_hero},
            "seed": self.seed,
        }

    def shutdown(self) -> None:
        self.player_a.close()
        self.player_b.close()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def make_handler(match: MatchServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            log.debug("%s - - %s", self.address_string(), format % args)

        # ----- response helpers -----

        def _json(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _player(self, query: dict[str, list[str]]):
            p = (query.get("player") or [""])[0].upper()
            return match.players.get(p), p

        # ----- routes -----

        def do_GET(self) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == "/status":
                self._json(200, {"status": match.status()})
                return
            if url.path == "/pending":
                player, p_id = self._player(query)
                if player is None:
                    self._json(400, {"error": f"unknown player {p_id!r}, want A or B"})
                    return
                self._json(
                    200,
                    {"pending": player.get_pending(), "status": match.status()},
                )
                return
            self._json(404, {"error": f"not found: {url.path}"})

        def do_POST(self) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == "/action":
                player, p_id = self._player(query)
                if player is None:
                    self._json(400, {"error": f"unknown player {p_id!r}"})
                    return
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                try:
                    body = json.loads(raw) if raw else {}
                except json.JSONDecodeError as exc:
                    self._json(400, {"error": f"invalid JSON: {exc}"})
                    return
                ids = body.get("selected_option_ids")
                if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                    self._json(
                        400,
                        {"error": "body must be {\"selected_option_ids\": [str, ...]}"},
                    )
                    return
                ok, msg = player.submit(ids)
                if not ok:
                    self._json(409, {"error": msg, "status": match.status()})
                    return
                self._json(200, {"ok": True, "status": match.status()})
                return
            self._json(404, {"error": f"not found: {url.path}"})

    return Handler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    repo = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="python tools/match_server.py")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--cards", type=Path, default=repo / "data" / "cards.tsv",
        help="Path to the card database TSV.",
    )
    p.add_argument(
        "--deck-a", type=Path,
        default=repo / "ref" / "decks" / "decklist-cindra-blue.md",
        help="Markdown decklist for seat A (player_index 0).",
    )
    p.add_argument(
        "--deck-b", type=Path,
        default=repo / "ref" / "decks" / "decklist-arakni.md",
        help="Markdown decklist for seat B (player_index 1).",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not args.cards.exists():
        print(f"error: card database not found: {args.cards}", file=sys.stderr)
        return 2

    db = CardDatabase.load(args.cards)
    deck_a = parse_markdown_decklist(args.deck_a.read_text(encoding="utf-8"))
    deck_b = parse_markdown_decklist(args.deck_b.read_text(encoding="utf-8"))

    match = MatchServer(db, deck_a, deck_b, seed=args.seed)
    match.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(match))
    server_thread = threading.Thread(
        target=server.serve_forever, daemon=True, name="http-thread",
    )
    server_thread.start()

    print(
        f"match server listening on http://{args.host}:{args.port}\n"
        f"  seat A ({deck_a.hero_name}) vs seat B ({deck_b.hero_name})\n"
        f"  seed={args.seed}\n"
        f"  endpoints:\n"
        f"    GET  /pending?player=A|B\n"
        f"    POST /action?player=A|B   body: {{\"selected_option_ids\": [...]}}\n"
        f"    GET  /status",
        file=sys.stderr,
        flush=True,
    )

    try:
        while not match.is_done():
            time.sleep(0.2)
        # Allow inflight clients to read game_over status before we close.
        time.sleep(1.0)
    except KeyboardInterrupt:
        log.info("interrupted; shutting down")
    finally:
        match.shutdown()
        server.shutdown()
        server.server_close()

    final = match.status()
    print(f"final status: {json.dumps(final)}", file=sys.stderr)
    return 0 if match.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
