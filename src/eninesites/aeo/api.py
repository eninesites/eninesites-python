"""The aeo api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``inspect.py:408-460``): ``GET /api/v1/manager/inspect/aeo/?url=`` inspects
one URL (any authenticated user) and ``GET /api/v1/site/<d>/aeo/`` every sitemap URL of a
site the caller is a member of.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable

from eninesites.errors import ApiError
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import rows

from .lib.results import AeoPage, InspectAeo


def inspect_aeo(
    *,
    url: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> InspectAeo:
    """The AEO surface of one ``--url``, else of every sitemap URL of the site."""
    if url and domain:
        raise ApiError("aeo inspect: pass --url or --domain, not both")
    client = connect(api_key, base_url, project_name, domain)
    if url:
        payload = client.get("/api/v1/manager/inspect/aeo/", {"url": url})
        found = rows([payload], AeoPage)
    else:
        found = rows(client.get(client.site_path("aeo")), AeoPage)
    return {"count": len(found), "results": found}


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "inspect": inspect_aeo,
}
