"""Shared Anthropic API client and constants for the LLM player modules."""

from __future__ import annotations

import os

DEFAULT_MODEL = "claude-sonnet-4-6"

_anthropic_client = None


def get_client():  # type: ignore[no-untyped-def]
    """Lazily initialize and return the Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Set it to use the LLM player."
            )
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client
