"""The artifact AEO api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server route: ``/api/v1/site/<d>/artifacts/<slug>/aeo/`` (``ArtifactXEODataView``,
``resources.py:256-337``): GET, POST (create or replace), PATCH (partial; 404 when there is
no data yet), DELETE. ``faqs`` in ``--data`` syncs the FAQ list: an item with ``id``
updates, without creates, and an FAQ left out is deleted.
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
from eninesites.lib.client.records import project, request_body, required

from .lib.results import AeoRow, CreateAeo, DeleteAeo, GetAeo, UpdateAeo

SLUG = "the artifact's name or slug"


def get_aeo(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetAeo:
    """The artifact's XEO data: ``GET .../aeo/`` (``{"xeo_data": null}`` when none)."""
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    payload = client.get(client.site_path("artifacts", target, "aeo"))
    aeo = None
    if isinstance(payload, dict) and payload.get("xeo_data", 0) is not None:
        aeo = project(payload, AeoRow)
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "aeo": aeo,
    }


def _write(
    method: str,
    verb: str,
    slug: str | None,
    data: Path | None,
    connection: tuple[str | None, str | None, str | None, str | None],
) -> tuple[str, str, AeoRow]:
    body = request_body(data)
    if not body:
        raise ApiError(
            f"artifact aeo {verb}: --data is required (the six-W fields to set)"
        )
    client = connect(*connection)
    target = required(slug, "--slug", SLUG)
    payload = client.json(
        method, client.site_path("artifacts", target, "aeo"), body=body
    )
    return credentials.require_site(client.settings), target, project(payload, AeoRow)


def create_aeo(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
) -> CreateAeo:
    """Create or replace the XEO data from ``--data``: ``POST .../aeo/``."""
    site, target, aeo = _write(
        "POST", "create", slug, data, (api_key, base_url, project_name, domain)
    )
    return {"domain": site, "slug": target, "aeo": aeo}


def update_aeo(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
) -> UpdateAeo:
    """Change only the fields in ``--data``: ``PATCH .../aeo/``."""
    site, target, aeo = _write(
        "PATCH", "update", slug, data, (api_key, base_url, project_name, domain)
    )
    return {"domain": site, "slug": target, "aeo": aeo}


def delete_aeo(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> DeleteAeo:
    """Delete the artifact's XEO data: ``DELETE .../aeo/`` (204)."""
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("artifacts", target, "aeo"))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "get": get_aeo,
    "create": create_aeo,
    "update": update_aeo,
    "delete": delete_aeo,
}
