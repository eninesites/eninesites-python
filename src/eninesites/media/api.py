"""The media api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:514-587``): ``/api/v1/site/<d>/media/`` (GET paginated, POST
multipart with one ``file`` part per file, 10 MB each; a duplicate returns the existing
row) and ``.../media/<slug>/`` (GET, POST partial, DELETE).
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
    DeleteMedia,
    GetMedia,
    ListMedia,
    MediaRow,
    UpdateMedia,
    UploadMedia,
)

SLUG = "the media item's slug, from `media list`"


def list_media(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListMedia:
    """The site's media library: ``GET .../media/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("media")), MediaRow)
    return {"count": len(found), "results": found}


@writes
def upload_media(
    *,
    files: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> UploadMedia | PlannedRequest:
    """Upload files (``--files a.png,b.jpg``): ``POST .../media/`` multipart."""
    paths = [
        Path(p.strip()).expanduser() for p in (files or "").split(",") if p.strip()
    ]
    if not paths:
        raise ApiError("media upload: --files is required (comma-separated paths)")
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise ApiError(f"media upload: not a file: {', '.join(missing)}")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    found = rows(client.json("POST", client.site_path("media"), files=paths), MediaRow)
    return {"count": len(found), "results": found}


def get_media(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetMedia:
    """One media item: ``GET .../media/<slug>/``."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("media", required(slug, "--slug", SLUG))
    result: GetMedia = project(client.get(path), GetMedia)
    return result


@writes
def update_media(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateMedia | PlannedRequest:
    """Change metadata from ``--data`` (e.g. ``filename``): ``POST .../media/<slug>/``."""
    body = request_body(data)
    if not body:
        raise ApiError(
            'media update: --data is required: a JSON file such as {"filename": "hero"}'
        )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("media", required(slug, "--slug", SLUG))
    result: UpdateMedia = project(client.json("POST", path, body=body), UpdateMedia)
    return result


@writes
def delete_media(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteMedia | PlannedRequest:
    """Delete a media item: ``DELETE .../media/<slug>/`` (204)."""
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("media", target))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_media,
    "upload": upload_media,
    "get": get_media,
    "update": update_media,
    "delete": delete_media,
}
