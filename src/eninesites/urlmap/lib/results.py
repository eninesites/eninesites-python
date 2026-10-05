"""The shapes the urlmap api returns: one TypedDict per verb, and its rows.

The one home of every URL-map result shape. A row follows the server's
``URLMapSerializer`` (``rest.py:379-408``): ``artifact`` is the artifact's name;
``is_canonical`` true is the address the projection renders at, null a redirect to it.
"""

from __future__ import annotations

from typing import TypedDict


class UrlMapRow(TypedDict, total=False):
    """One custom path mapped to an artifact projection."""

    id: int
    path: str
    projection: str
    artifact: str
    is_canonical: bool | None


class ListUrlmap(TypedDict):
    """What ``urlmap list`` returns: the site's custom paths, by path."""

    count: int
    results: list[UrlMapRow]


class CreateUrlmap(UrlMapRow):
    """What ``urlmap create`` returns: the mapping created."""


class GetUrlmap(UrlMapRow):
    """What ``urlmap get`` returns: the mapping."""


class UpdateUrlmap(UrlMapRow):
    """What ``urlmap update`` returns: the mapping as updated."""


class DeleteUrlmap(TypedDict):
    """What ``urlmap delete`` returns."""

    domain: str
    id: str
    deleted: bool
