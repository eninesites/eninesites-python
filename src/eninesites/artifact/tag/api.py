"""The artifact tag api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:887-946``): ``.../artifacts/<slug>/tags/`` (GET a bare array,
POST ``{"tag": <tag slug>}``, idempotent) and ``.../tags/<tag slug>/`` (DELETE). Tags go on
depth-1 and depth-2 artifacts only; the server refuses others with a 400.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client import credentials
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import required, rows

from .lib.results import AttachTag, DetachTag, ListTag, TagRow

SLUG = "the artifact's name or slug"
TAG = "the tag's slug"


def list_tag(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListTag:
    """The tags on the artifact: ``GET .../artifacts/<slug>/tags/``."""
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    tags = rows(client.get(client.site_path("artifacts", target, "tags")), TagRow)
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "tags": tags,
    }


def attach_tag(
    *,
    slug: str | None = None,
    tag: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> AttachTag:
    """Put a site tag on the artifact (idempotent): ``POST .../tags/``."""
    chosen = required(tag, "--tag", TAG)
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    path = client.site_path("artifacts", target, "tags")
    tags = rows(client.json("POST", path, body={"tag": chosen}), TagRow)
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "tags": tags,
    }


def detach_tag(
    *,
    slug: str | None = None,
    tag: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> DetachTag:
    """Take a tag off the artifact: ``DELETE .../tags/<tag slug>/`` (204)."""
    chosen = required(tag, "--tag", TAG)
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    client.request("DELETE", client.site_path("artifacts", target, "tags", chosen))
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "tag": chosen,
        "detached": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_tag,
    "attach": attach_tag,
    "detach": detach_tag,
}
