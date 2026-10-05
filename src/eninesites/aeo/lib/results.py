"""The shapes the aeo api returns: one TypedDict per verb, and its rows.

The one home of every AEO-inspection result shape. A page follows the server's inspect
envelope (``services/visitor/inspect.py:162-215``, ``354-376``); ``json_ld`` is the
structured data the page emits, free-form, so it is bounded JSON.
"""

from __future__ import annotations

from typing import TypedDict

from eninesites.lib.jsonvalue import JsonObject


class PageArtifact(TypedDict, total=False):
    """An artifact a page renders, with its XEO role."""

    id: int
    name: str
    slug: str
    depth: int
    pnode_id: int | None
    title: str | None
    is_published: bool
    description: str | None
    role: str | None
    effective_role: str | None


class AeoPage(TypedDict, total=False):
    """One URL's AEO surface: what view it is, which artifacts, and the JSON-LD it emits."""

    url: str
    view: str
    site_subject: str
    page_artifacts: list[PageArtifact]
    json_ld: list[JsonObject]


class InspectAeo(TypedDict):
    """What ``aeo inspect`` returns: one page for ``--url``, every sitemap URL for a site."""

    count: int
    results: list[AeoPage]
