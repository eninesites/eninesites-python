"""The shapes the artifact.url api returns: one TypedDict per verb, and its rows.

The one home of every artifact.url result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. They live in
``lib`` so the api and the renderers can both import them while nothing in ``lib``
imports the api. A result holds JSON types only: a date is an ISO string, an exact
amount a decimal string, never a float.

A row the server sends is ``total=False``: the api keeps only the keys declared here, and a
key the server omits is absent rather than invented. The shape is the server's
``ArtifactURL``: ``external_url`` is the catalog entry's id, and ``name``, ``label`` and
``href`` are that entry's, read-only.
"""

from __future__ import annotations

from typing import TypedDict


class ArtifactUrlRow(TypedDict, total=False):
    """One of an artifact's external URLs: a saved URL and its position."""

    id: int
    external_url: int
    name: str
    label: str
    href: str
    order: int


class ListUrl(TypedDict):
    """What ``artifact url list`` returns: the artifact's external URLs, in order."""

    count: int
    results: list[ArtifactUrlRow]


class AttachUrl(ArtifactUrlRow):
    """What ``artifact url attach`` returns: the new row."""


class GetUrl(ArtifactUrlRow):
    """What ``artifact url get`` returns: the row."""


class UpdateUrl(ArtifactUrlRow):
    """What ``artifact url update`` returns: the row after the change."""


class DetachUrl(TypedDict):
    """What ``artifact url detach`` returns."""

    domain: str
    slug: str
    id: str
    detached: bool
