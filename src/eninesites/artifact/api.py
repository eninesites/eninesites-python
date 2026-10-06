"""The artifact api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes: ``/api/v1/site/<d>/artifacts/`` (``ArtifactListView``) and
``/api/v1/site/<d>/artifacts/<slug>/`` (``ArtifactDetailView``), ``resources.py:93-147``.
``<slug>`` may be the artifact's name or its slug; the server tries the name first.
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
from eninesites.lib.client.records import boolean, merged, project, required, rows
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import (
    ArtifactRow,
    CreateArtifact,
    DeleteArtifact,
    GetArtifact,
    ListArtifact,
    UpdateArtifact,
)

SLUG = "the artifact's name or slug"


def list_artifact(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListArtifact:
    """The site's root artifacts with their children: ``GET .../artifacts/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("artifacts")), ArtifactRow)
    return {"count": len(found), "results": found}


def get_artifact(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetArtifact:
    """One artifact: ``GET .../artifacts/<slug>/``."""
    client = connect(api_key, base_url, project_name, domain)
    result: GetArtifact = project(
        client.get(client.site_path("artifacts", required(slug, "--slug", SLUG))),
        GetArtifact,
    )
    return result


@writes
def create_artifact(
    *,
    name: str | None = None,
    title: str | None = None,
    pnode: str | None = None,
    content: str | None = None,
    published: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> CreateArtifact | PlannedRequest:
    """Create an artifact, under ``--pnode`` (a parent's name or slug) when given.

    ``POST .../artifacts/``. ``--data`` carries any other writable field (``display_name``,
    ``description``, ``navbar``, ...); the named flags override it.
    """
    body = merged(
        data,
        name=name,
        title=title,
        parent=pnode,
        content=content,
        is_published=boolean(published, "--published"),
    )
    if not body.get("name"):
        raise ApiError("artifact create: --name is required")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    result: CreateArtifact = project(
        client.json("POST", client.site_path("artifacts"), body=body), CreateArtifact
    )
    return result


@writes
def update_artifact(
    *,
    slug: str | None = None,
    title: str | None = None,
    content: str | None = None,
    published: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateArtifact | PlannedRequest:
    """Update the fields given, leaving the rest: ``POST .../artifacts/<slug>/`` (partial)."""
    body = merged(
        data,
        title=title,
        content=content,
        is_published=boolean(published, "--published"),
    )
    if not body:
        raise ApiError(
            "artifact update: nothing to update; pass a field flag or --data"
        )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG))
    result: UpdateArtifact = project(
        client.json("POST", path, body=body), UpdateArtifact
    )
    return result


@writes
def delete_artifact(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteArtifact | PlannedRequest:
    """Delete an artifact and its subtree: ``DELETE .../artifacts/<slug>/`` (204)."""
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("artifacts", target))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_artifact,
    "get": get_artifact,
    "create": create_artifact,
    "update": update_artifact,
    "delete": delete_artifact,
}
