"""The artifact url api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (#186): ``.../artifacts/<slug>/urls/`` (GET paginated by ``order, id``; POST
``{"external_url": <catalog id or name>, "order"?: int}``) and ``.../urls/<id>/`` (GET,
PATCH ``{"external_url"?, "order"?}``, DELETE). A row links a catalog entry (``url list``)
to the artifact: attach never creates an entry, and detach leaves it. Attaching an entry
the artifact already has, or one not in the catalog, is the server's 400.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from eninesites.errors import ApiError
from eninesites.lib.client import credentials
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import (
    integer,
    project,
    request_body,
    required,
    rows,
)
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import (
    ArtifactUrlRow,
    AttachUrl,
    DetachUrl,
    GetUrl,
    ListUrl,
    UpdateUrl,
)

SLUG = "the artifact's name or slug"
NAME = "the saved URL's name, from `url list`"
ENTRY = "the artifact's URL row id, from `artifact.url list`"


def list_url(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListUrl:
    """The artifact's external URLs, in order: ``GET .../urls/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "urls")
    found = rows(client.list_all(path), ArtifactUrlRow)
    return {"count": len(found), "results": found}


@writes
def attach_url(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    name: str | None = None,
    order: str | None = None,
    dry_run: bool = False,
) -> AttachUrl | PlannedRequest:
    """Link a saved URL to the artifact: ``POST .../urls/`` (201).

    Without ``--order`` the server places it at 0, which sorts before any row whose order
    is 1 or more; ``--order`` sets its position in the same call.
    """
    body: dict[str, object] = {"external_url": required(name, "--name", NAME)}
    position = integer(order, "--order")
    if position is not None:
        body["order"] = position
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "urls")
    result: AttachUrl = project(client.json("POST", path, body=body), AttachUrl)
    return result


def get_url(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetUrl:
    """One of the artifact's external URLs: ``GET .../urls/<id>/``."""
    entry = required(id_, "--id", ENTRY)
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "urls", entry)
    result: GetUrl = project(client.get(path), GetUrl)
    return result


@writes
def update_url(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateUrl | PlannedRequest:
    """Reorder or re-point a row with the ``--data`` fields: ``PATCH .../urls/<id>/``.

    ``--data`` holds ``order`` and/or ``external_url`` (another saved URL's name or id).
    """
    body = request_body(data)
    if not body:
        raise ApiError("artifact url update: --data is required (the fields to change)")
    entry = required(id_, "--id", ENTRY)
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "urls", entry)
    result: UpdateUrl = project(client.json("PATCH", path, body=body), UpdateUrl)
    return result


@writes
def detach_url(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DetachUrl | PlannedRequest:
    """Unlink a row (the saved URL stays): ``DELETE .../urls/<id>/`` (204)."""
    entry = required(id_, "--id", ENTRY)
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("artifacts", target, "urls", entry))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "id": entry,
        "detached": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_url,
    "attach": attach_url,
    "get": get_url,
    "update": update_url,
    "detach": detach_url,
}
