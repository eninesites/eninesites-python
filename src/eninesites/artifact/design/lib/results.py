"""The shapes the artifact design api returns: one TypedDict per verb, and its rows.

The one home of every design result shape. Fields follow the server's
``ArtifactDesignSerializer`` (``rest.py:225-242``). Server rows are ``total=False``.
"""

from __future__ import annotations

from typing import TypedDict


class DesignRow(TypedDict, total=False):
    """An artifact's design: which templates render it (depth-0 and depth-1 artifacts only)."""

    id: int
    icon_template: str | None
    card_template: str | None
    list_template: str | None
    section_view: str | None
    catalog_view: str | None


class GetDesign(TypedDict):
    """What ``artifact design get`` returns: the design, or null when the artifact has none."""

    domain: str
    slug: str
    design: DesignRow | None


class UpdateDesign(TypedDict):
    """What ``artifact design update`` returns: the design as saved."""

    domain: str
    slug: str
    design: DesignRow
