"""The shapes the site api returns: one TypedDict per verb, and its rows.

The one home of every site result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. They live in
``lib`` so the api and the renderers can both import them while nothing in ``lib``
imports the api. A result holds JSON types only: a date is an ISO string, an exact
amount a decimal string, never a float.

A row the server sends is ``total=False``: the api keeps only the keys declared here, and a
key the server omits is absent rather than invented. A verb with no REST endpoint never
returns; its type stays empty.
"""

from __future__ import annotations

from typing import TypedDict


class SiteRow(TypedDict, total=False):
    """One site the caller can reach (``GET /api/v1/site/``)."""

    domain: str
    name: str


class CreateSite(TypedDict):
    """What ``site create`` returns: the domain the server created (it may allocate one)."""

    domain: str


class ListSite(TypedDict):
    """What ``site list`` returns: every site the caller is a member of."""

    count: int
    results: list[SiteRow]


class DumpSite(TypedDict):
    """What ``site dump`` returns: where the export was saved, and how big it is."""

    domain: str
    format: str
    path: str
    bytes: int


class LoadSite(TypedDict):
    """What ``site load`` returns: the site the file was upserted into."""

    domain: str
    file: str


class RestoreSite(TypedDict):
    """What ``site restore`` returns: the site the archive was restored over, and how."""

    domain: str
    file: str
    mode: str


class CopySite(TypedDict):
    """What ``site copy`` returns: the source and the new domain."""

    source: str
    domain: str


class ConfigureSite(TypedDict):
    """What ``site configure`` returns: the sections the server updated."""

    domain: str
    updated: list[str]


class DeleteSite(TypedDict):
    """What ``site delete`` would return. It has no REST endpoint, so it never returns."""


class CheckSite(TypedDict):
    """What ``site check`` would return. It has no REST endpoint, so it never returns."""


class ReviewSite(TypedDict):
    """What ``site review`` would return. It has no REST endpoint, so it never returns."""


class SelectSite(TypedDict):
    """What ``site select`` returns: the site now used when ``--domain`` is not given."""

    project_name: str
    site: str
    config_path: str


class RandomizeSubdomainSite(TypedDict):
    """What ``site randomize-subdomain`` returns: the new subdomain."""

    domain: str
    subdomain: str


class ProposeSite(TypedDict):
    """What ``site propose`` would return. It has no REST endpoint, so it never returns."""


class BuildSite(TypedDict):
    """What ``site build`` would return. It has no REST endpoint, so it never returns."""
