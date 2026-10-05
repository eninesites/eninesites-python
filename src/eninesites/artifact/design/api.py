"""The artifact design api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server route: ``/api/v1/site/<d>/artifacts/<slug>/design/`` (``ArtifactDesignView``,
``resources.py:155-173``). The POST is a partial create-or-update.
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

from .lib.results import DesignRow, GetDesign, UpdateDesign

SLUG = "the artifact's name or slug"


def get_design(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetDesign:
    """The artifact's design: ``GET .../design/`` (``{"design": null}`` when none)."""
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    payload = client.get(client.site_path("artifacts", target, "design"))
    design = None
    if isinstance(payload, dict) and payload.get("design", 0) is not None:
        design = project(payload, DesignRow)
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "design": design,
    }


def update_design(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
) -> UpdateDesign:
    """Set design fields from the ``--data`` JSON file, e.g. ``{"card_template": "card-media"}``.

    ``POST .../design/``: creates the design when absent, else updates the fields given.
    """
    body = request_body(data)
    if not body:
        raise ApiError(
            "artifact design update: --data is required (the design fields to set)"
        )
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    payload = client.json(
        "POST", client.site_path("artifacts", target, "design"), body=body
    )
    return {
        "domain": credentials.require_site(client.settings),
        "slug": target,
        "design": project(payload, DesignRow),
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "get": get_design,
    "update": update_design,
}
