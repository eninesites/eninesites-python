"""The plan api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server route: ``GET /api/v1/plans/`` (#191), a bare array, cheapest first. Every slug it
lists is a ``plan`` that ``POST /api/v1/site/`` accepts for the caller right now, so it is
what ``site create --plan`` and ``site copy --plan`` take. Plans are not per site: the
route takes no domain.
"""

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client.http import connect
from eninesites.lib.client.records import rows

from .lib.results import ListPlan, PlanRow


def list_plan(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListPlan:
    """The plans the caller may create a site on: ``GET /api/v1/plans/`` (a bare array)."""
    client = connect(api_key, base_url, project_name)
    found = rows(client.get("/api/v1/plans/"), PlanRow)
    return {"count": len(found), "results": found}


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_plan,
}
