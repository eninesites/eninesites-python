"""The shapes the chat api returns: one TypedDict per verb, and its rows.

The one home of every chat result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. They live in
``lib`` so the api and the renderers can both import them while nothing in ``lib``
imports the api. A result holds JSON types only: a date is an ISO string, an exact
amount a decimal string, never a float.
"""

from __future__ import annotations

from typing import TypedDict


class StreamChat(TypedDict):
    """What ``chat stream`` returns. It has no REST endpoint, so it never returns."""


class MagicLinkChat(TypedDict):
    """What ``chat magic-link`` returns. It has no REST endpoint, so it never returns."""
