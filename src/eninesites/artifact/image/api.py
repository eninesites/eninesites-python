"""The artifact image api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:454-506``): ``.../artifacts/<slug>/images/`` (GET paginated,
POST ``{"image": <media id>, "order"?: int}``, idempotent) and ``.../images/<id>/`` (GET,
PATCH ``{"order": int}``, DELETE). An image sent without an order, or with 0, goes last.
``--media`` is the media item's id (``media list`` shows it); ``--id`` is a gallery entry's.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client import credentials
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import (
    integer,
    project,
    required,
    required_int,
    rows,
)
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import (
    AttachImage,
    DetachImage,
    GetImage,
    ImageRow,
    ListImage,
    UpdateImage,
)

SLUG = "the artifact's name or slug"
ENTRY = "the gallery entry's id"


def list_image(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListImage:
    """The artifact's gallery: ``GET .../images/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "images")
    found = rows(client.list_all(path), ImageRow)
    return {"count": len(found), "results": found}


@writes
def attach_image(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    media: str | None = None,
    order: str | None = None,
    dry_run: bool = False,
) -> AttachImage | PlannedRequest:
    """Add a media item to the gallery (idempotent): ``POST .../images/``.

    Without ``--order`` (or with 0) the server puts it after the last image. A media item
    already in the gallery comes back as it is, and the order sent is ignored.
    """
    body: dict[str, object] = {
        "image": required_int(
            media, "--media", "the media item's id, from `media list`"
        )
    }
    position = integer(order, "--order")
    if position is not None:
        body["order"] = position
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("artifacts", required(slug, "--slug", SLUG), "images")
    result: AttachImage = project(client.json("POST", path, body=body), AttachImage)
    return result


def get_image(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetImage:
    """One gallery entry: ``GET .../images/<id>/``."""
    entry = required(id_, "--id", ENTRY)
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path(
        "artifacts", required(slug, "--slug", SLUG), "images", entry
    )
    result: GetImage = project(client.get(path), GetImage)
    return result


@writes
def detach_image(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DetachImage | PlannedRequest:
    """Remove a gallery entry (the media item stays): ``DELETE .../images/<id>/`` (204)."""
    entry = required(id_, "--id", ENTRY)
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("artifacts", target, "images", entry))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "id": entry,
        "detached": True,
    }


@writes
def update_image(
    *,
    slug: str | None = None,
    id_: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    order: str | None = None,
    dry_run: bool = False,
) -> UpdateImage | PlannedRequest:
    """Move a gallery entry: ``PATCH .../images/<id>/`` with ``{"order": ...}``."""
    entry = required(id_, "--id", ENTRY)
    position = required_int(order, "--order", "the image's position, 0 or more")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path(
        "artifacts", required(slug, "--slug", SLUG), "images", entry
    )
    result: UpdateImage = project(
        client.json("PATCH", path, body={"order": position}), UpdateImage
    )
    return result


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_image,
    "attach": attach_image,
    "get": get_image,
    "detach": detach_image,
    "update": update_image,
}
