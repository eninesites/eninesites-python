"""The urlmap api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:677-732``): ``/api/v1/site/<d>/urlmaps/`` (GET paginated,
POST) and ``.../urlmaps/<id>/`` (GET, PATCH, DELETE). Body fields (``path``,
``projection``: detail, catalog or landing, ``artifact``: a name, ``is_canonical``) come in
``--data``.
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
    CreateUrlmap,
    DeleteUrlmap,
    GetUrlmap,
    ListUrlmap,
    UpdateUrlmap,
    UrlMapRow,
)

ID = "the URL map's id, from `urlmap list`"


def list_urlmap(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListUrlmap:
    """The site's custom paths: ``GET .../urlmaps/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("urlmaps")), UrlMapRow)
    return {"count": len(found), "results": found}


@writes
def create_urlmap(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> CreateUrlmap | PlannedRequest:
    """Map a path: ``POST .../urlmaps/``.

    The ``--data`` file holds ``path``, ``projection`` and ``artifact``.
    """
    body = request_body(data)
    missing = [k for k in ("path", "projection", "artifact") if not body.get(k)]
    if missing:
        raise ApiError(
            f"urlmap create: the --data file lacks {', '.join(missing)}; it holds e.g. "
            '{"path": "legal/terms", "projection": "detail", "artifact": "terms"}'
        )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    payload = client.json("POST", client.site_path("urlmaps"), body=body)
    result: CreateUrlmap = project(payload, CreateUrlmap)
    return result


def get_urlmap(
    *,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetUrlmap:
    """One mapping: ``GET .../urlmaps/<id>/``."""
    entry = required(id_, "--id", ID)
    client = connect(api_key, base_url, project_name, domain)
    result: GetUrlmap = project(
        client.get(client.site_path("urlmaps", entry)), GetUrlmap
    )
    return result


@writes
def update_urlmap(
    *,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateUrlmap | PlannedRequest:
    """Change the fields in ``--data``: ``PATCH .../urlmaps/<id>/``."""
    entry = required(id_, "--id", ID)
    body = request_body(data)
    if not body:
        raise ApiError("urlmap update: --data is required (the fields to change)")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    payload = client.json("PATCH", client.site_path("urlmaps", entry), body=body)
    result: UpdateUrlmap = project(payload, UpdateUrlmap)
    return result


@writes
def delete_urlmap(
    *,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteUrlmap | PlannedRequest:
    """Delete a mapping: ``DELETE .../urlmaps/<id>/`` (204)."""
    entry = required(id_, "--id", ID)
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    client.request("DELETE", client.site_path("urlmaps", entry))
    return {
        "domain": credentials.require_site(client.settings),
        "id": entry,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_urlmap,
    "create": create_urlmap,
    "get": get_urlmap,
    "update": update_urlmap,
    "delete": delete_urlmap,
}
