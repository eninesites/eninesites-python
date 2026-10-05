"""The shapes the artifact api returns: one TypedDict per verb, and its rows.

The one home of every artifact result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. A result
holds JSON types only. Server rows are ``total=False``: only declared keys are kept, and a
key the server omits is absent.

Fields follow the server's ``ArtifactReadSerializer`` (``rest.py:113-138``: ``id``,
``slug``, ``depth``, ``pnode_id``, ``children``, ``url``, ``pnc`` plus
``ARTIFACT_EDITABLE_FIELDS``) and ``ArtifactSummarySerializer`` for children.
"""

from __future__ import annotations

from typing import TypedDict


class ArtifactSummary(TypedDict, total=False):
    """An immediate child, as the server summarises it."""

    id: int
    name: str
    slug: str
    title: str | None
    short_title: str | None
    tagline: str | None
    icon: str | None
    order: int
    depth: int
    is_published: bool
    is_featured: bool


class ArtifactRow(TypedDict, total=False):
    """One artifact, with its immediate children."""

    id: int
    slug: str
    depth: int
    pnode_id: int | None
    children: list[ArtifactSummary]
    url: str | None
    pnc: str
    name: str
    display_name: str | None
    display_plural: str | None
    title: str | None
    short_title: str | None
    tagline: str | None
    content: str | None
    description: str | None
    icon: str | None
    media: int | None
    link: int | None
    order: int
    navbar: bool
    footer: bool
    is_meta: bool
    is_published: bool
    is_routable: bool
    is_featured: bool
    html_content: str | None


class ListArtifact(TypedDict):
    """What ``artifact list`` returns: the site's root artifacts, in order."""

    count: int
    results: list[ArtifactRow]


class GetArtifact(ArtifactRow):
    """What ``artifact get`` returns: the artifact."""


class CreateArtifact(ArtifactRow):
    """What ``artifact create`` returns: the artifact as created."""


class UpdateArtifact(ArtifactRow):
    """What ``artifact update`` returns: the artifact as updated."""


class DeleteArtifact(TypedDict):
    """What ``artifact delete`` returns: what was deleted."""

    domain: str
    slug: str
    deleted: bool
