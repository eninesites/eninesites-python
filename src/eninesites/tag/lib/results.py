"""The shapes the tag api returns: one TypedDict per verb, and its rows.

The one home of every tag result shape. A row follows the server's ``TagSerializer``
(``rest.py:428-434``).
"""

from __future__ import annotations

from typing import TypedDict


class TagRow(TypedDict, total=False):
    """One site tag."""

    id: int
    slug: str
    name: str


class ListTag(TypedDict):
    """What ``tag list`` returns: the site's tags, by name."""

    count: int
    results: list[TagRow]


class CreateTag(TagRow):
    """What ``tag create`` returns: the tag created."""


class GetTag(TagRow):
    """What ``tag get`` returns: the tag."""


class UpdateTag(TagRow):
    """What ``tag update`` returns: the tag as renamed."""


class DeleteTag(TypedDict):
    """What ``tag delete`` returns."""

    domain: str
    slug: str
    deleted: bool
