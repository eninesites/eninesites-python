"""The shapes the artifact tag api returns: one TypedDict per verb, and its rows.

The one home of every artifact-tag result shape. A tag row follows the server's
``TagSerializer`` (``rest.py:428-434``).
"""

from __future__ import annotations

from typing import TypedDict


class TagRow(TypedDict, total=False):
    """One site tag."""

    id: int
    slug: str
    name: str


class ListTag(TypedDict):
    """What ``artifact tag list`` returns: the tags on the artifact."""

    domain: str
    slug: str
    tags: list[TagRow]


class AttachTag(TypedDict):
    """What ``artifact tag attach`` returns: the tags on the artifact afterwards."""

    domain: str
    slug: str
    tags: list[TagRow]


class DetachTag(TypedDict):
    """What ``artifact tag detach`` returns."""

    domain: str
    slug: str
    tag: str
    detached: bool
