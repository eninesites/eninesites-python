"""The chat api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

The chat endpoints are browser endpoints, not part of the token-authenticated REST API, so
both verbs refuse: ``/api/chat/stream/`` authenticates by Django session only (``await
request.auser()``, ``apps/chat/views.py:206``), so an API key is ignored and the caller is
anonymous; ``/api/chat/magic-link/`` is a plain Django view without ``csrf_exempt``
(``views.py:118``; only the stream view is exempt, ``:183``), so a non-browser POST fails
CSRF.
"""

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client.records import not_over_rest
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import MagicLinkChat, StreamChat


@writes
def stream_chat(*, dry_run: bool = False) -> StreamChat | PlannedRequest:
    """Refuse: chat streaming authenticates by browser session only, not by API key."""
    del dry_run
    raise not_over_rest(
        "chat stream",
        "/api/chat/stream/ authenticates by browser session only, so an API key is ignored",
    )


@writes
def magic_link_chat(*, dry_run: bool = False) -> MagicLinkChat | PlannedRequest:
    """Refuse: the magic-link endpoint is CSRF-protected, so only a browser can call it."""
    del dry_run
    raise not_over_rest(
        "chat magic-link",
        "/api/chat/magic-link/ is CSRF-protected, so only a browser session can call it",
    )


# The verbs the eninesites REST API has no endpoint for: each raises `ApiError` saying
# where the operation lives instead. Read mechanically by the tests, one home.
NOT_OVER_REST: frozenset[str] = frozenset({"stream", "magic-link"})

# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "stream": stream_chat,
    "magic-link": magic_link_chat,
}
