"""The seo api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:1027-1078``): ``/api/v1/site/<d>/seo/pages/`` (GET paginated,
POST; a duplicate ``canonical`` is 409 ``seo_page_already_exists``) and ``.../seo/pages/<id>/``
(GET, POST partial, DELETE). Body fields (``canonical``, ``page_name``, ``page_title``,
``description``, ``keywords``) come in ``--data``.
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
from eninesites.lib.client.records import project, request_body, required, rows
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import (
    CreateSeo,
    DeleteSeo,
    GetSeo,
    ListSeo,
    SeoPageRow,
    UpdateSeo,
)

ID = "the SEO page's id, from `seo list`"


def list_seo(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListSeo:
    """The site's SEO pages: ``GET .../seo/pages/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("seo", "pages")), SeoPageRow)
    return {"count": len(found), "results": found}


@writes
def create_seo(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> CreateSeo | PlannedRequest:
    """Create an SEO page: ``POST .../seo/pages/``.

    The ``--data`` file holds ``canonical`` and any of ``page_name``, ``page_title``,
    ``description``, ``keywords``.
    """
    body = request_body(data)
    if not body.get("canonical"):
        raise ApiError(
            "seo create: the --data file lacks canonical; it holds e.g. "
            '{"canonical": "https://example.com/about/", "page_title": "About us"}'
        )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    payload = client.json("POST", client.site_path("seo", "pages"), body=body)
    result: CreateSeo = project(payload, CreateSeo)
    return result


def get_seo(
    *,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetSeo:
    """One SEO page: ``GET .../seo/pages/<id>/``."""
    entry = required(id_, "--id", ID)
    client = connect(api_key, base_url, project_name, domain)
    result: GetSeo = project(
        client.get(client.site_path("seo", "pages", entry)), GetSeo
    )
    return result


@writes
def update_seo(
    *,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateSeo | PlannedRequest:
    """Change the fields in ``--data``: ``POST .../seo/pages/<id>/`` (partial)."""
    entry = required(id_, "--id", ID)
    body = request_body(data)
    if not body:
        raise ApiError("seo update: --data is required (the fields to change)")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    payload = client.json("POST", client.site_path("seo", "pages", entry), body=body)
    result: UpdateSeo = project(payload, UpdateSeo)
    return result


@writes
def delete_seo(
    *,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteSeo | PlannedRequest:
    """Delete an SEO page: ``DELETE .../seo/pages/<id>/`` (204)."""
    entry = required(id_, "--id", ID)
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    client.request("DELETE", client.site_path("seo", "pages", entry))
    return {
        "domain": credentials.require_site(client.settings),
        "id": entry,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_seo,
    "create": create_seo,
    "get": get_seo,
    "update": update_seo,
    "delete": delete_seo,
}
