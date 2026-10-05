"""The page api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Crawling a page exists on the server only as the chat tool ``crawl_url``
(``apps/chat/tools/catalog_read.py:29``); the REST API has no endpoint for it, so the verb
refuses.
"""

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client.records import not_over_rest

from .lib.results import CrawlPage


def crawl_page(*, url: str | None = None) -> CrawlPage:
    """Refuse: the REST API has no crawl endpoint (the chat tool ``crawl_url`` does it)."""
    del url
    raise not_over_rest("page crawl", "it exists only as the chat tool `crawl_url`")


# The verbs the eninesites REST API has no endpoint for: each raises `ApiError` saying
# where the operation lives instead. Read mechanically by the tests, one home.
NOT_OVER_REST: frozenset[str] = frozenset({"crawl"})

# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "crawl": crawl_page,
}
