"""The tag api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:835-884``): ``/api/v1/site/<d>/tags/`` (GET paginated, POST;
a duplicate name is 409 ``tag_already_exists``) and ``.../tags/<slug>/`` (GET, POST
partial, DELETE).
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client import credentials
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import project, required, rows

from .lib.results import CreateTag, DeleteTag, GetTag, ListTag, TagRow, UpdateTag

SLUG = "the tag's slug"


def list_tag(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListTag:
    """Every tag on the site: ``GET .../tags/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("tags")), TagRow)
    return {"count": len(found), "results": found}


def create_tag(
    *,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> CreateTag:
    """Create a tag: ``POST .../tags/`` with ``{"name": ...}``."""
    body = {"name": required(name, "--name", "the tag's name")}
    client = connect(api_key, base_url, project_name, domain)
    result: CreateTag = project(
        client.json("POST", client.site_path("tags"), body=body), CreateTag
    )
    return result


def get_tag(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetTag:
    """One tag: ``GET .../tags/<slug>/``."""
    client = connect(api_key, base_url, project_name, domain)
    result: GetTag = project(
        client.get(client.site_path("tags", required(slug, "--slug", SLUG))), GetTag
    )
    return result


def update_tag(
    *,
    slug: str | None = None,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> UpdateTag:
    """Rename a tag: ``POST .../tags/<slug>/`` with ``{"name": ...}``."""
    body = {"name": required(name, "--name", "the tag's new name")}
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("tags", required(slug, "--slug", SLUG))
    result: UpdateTag = project(client.json("POST", path, body=body), UpdateTag)
    return result


def delete_tag(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> DeleteTag:
    """Delete a tag: ``DELETE .../tags/<slug>/`` (204)."""
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("tags", target))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_tag,
    "create": create_tag,
    "get": get_tag,
    "update": update_tag,
    "delete": delete_tag,
}
