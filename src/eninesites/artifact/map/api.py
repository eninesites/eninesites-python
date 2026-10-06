"""The artifact map api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:345-446``): ``.../artifacts/<slug>/maps/`` (GET paginated,
POST), ``.../maps/<id>/`` (GET, POST partial update, DELETE) and
``.../artifacts/<slug>/map-candidates/`` (a bare array).
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
    project,
    request_body,
    required,
    rows,
)
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import (
    CandidateRow,
    CandidatesMap,
    CreateMap,
    DeleteMap,
    GetMap,
    ListMap,
    MapRow,
    UpdateMap,
)

SLUG = "the artifact's name or slug"


def _id(id_: str | None) -> str:
    return required(id_, "--id", "the map edge's id")


def list_map(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListMap:
    """Every edge with the artifact on either side: ``GET .../maps/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "maps")
    found = rows(client.list_all(path), MapRow)
    return {"count": len(found), "results": found}


@writes
def create_map(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> CreateMap | PlannedRequest:
    """Map the artifact to another: ``POST .../maps/``; the ``--data`` file holds ``artifact_b``."""
    body = request_body(data)
    if "artifact_b" not in body:
        raise ApiError(
            'artifact map create: the --data file must name the target, e.g. {"artifact_b": 42} '
            "(`artifact map candidates` lists valid ids)"
        )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "maps")
    result: CreateMap = project(client.json("POST", path, body=body), CreateMap)
    return result


def get_map(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetMap:
    """One edge: ``GET .../maps/<id>/``."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path(
        "artifacts", required(slug, "--slug", SLUG), "maps", _id(id_)
    )
    result: GetMap = project(client.get(path), GetMap)
    return result


@writes
def update_map(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateMap | PlannedRequest:
    """Change the fields in ``--data`` (e.g. ``order``): ``POST .../maps/<id>/`` (partial)."""
    body = request_body(data)
    if not body:
        raise ApiError("artifact map update: --data is required (the fields to change)")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path(
        "artifacts", required(slug, "--slug", SLUG), "maps", _id(id_)
    )
    result: UpdateMap = project(client.json("POST", path, body=body), UpdateMap)
    return result


@writes
def delete_map(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteMap | PlannedRequest:
    """Delete one edge: ``DELETE .../maps/<id>/`` (204)."""
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    target, edge = required(slug, "--slug", SLUG), _id(id_)
    client.request("DELETE", client.site_path("artifacts", target, "maps", edge))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "id": edge,
        "deleted": True,
    }


def candidates_map(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> CandidatesMap:
    """Valid map targets, grouped by parent: ``GET .../map-candidates/``."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path(
        "artifacts", required(slug, "--slug", SLUG), "map-candidates"
    )
    found = rows(client.get(path), CandidateRow)
    return {"count": len(found), "results": found}


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_map,
    "create": create_map,
    "get": get_map,
    "update": update_map,
    "delete": delete_map,
    "candidates": candidates_map,
}
