"""The shapes the media api returns: one TypedDict per verb, and its rows.

The one home of every media result shape. A row follows the server's ``MediaSerializer``
(``rest.py:329-342``).
"""

from __future__ import annotations

from typing import TypedDict


class MediaRow(TypedDict, total=False):
    """One uploaded file in the site's media library."""

    id: int
    slug: str
    filename: str
    file_type: str
    is_image: bool
    url: str | None
    filehash: str


class ListMedia(TypedDict):
    """What ``media list`` returns: the library, newest first."""

    count: int
    results: list[MediaRow]


class UploadMedia(TypedDict):
    """What ``media upload`` returns: one row per file (an existing row for a duplicate)."""

    count: int
    results: list[MediaRow]


class GetMedia(MediaRow):
    """What ``media get`` returns: the media item."""


class UpdateMedia(MediaRow):
    """What ``media update`` returns: the media item as updated."""


class DeleteMedia(TypedDict):
    """What ``media delete`` returns."""

    domain: str
    slug: str
    deleted: bool
