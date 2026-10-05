"""The shapes the artifact image api returns: one TypedDict per verb, and its rows.

The one home of every gallery result shape. Fields follow the server's
``ArtifactImageSerializer`` with its nested ``MediaSerializer`` (``rest.py:329-358``).
"""

from __future__ import annotations

from typing import TypedDict


class MediaDetail(TypedDict, total=False):
    """The media item a gallery entry shows."""

    id: int
    slug: str
    filename: str
    file_type: str
    is_image: bool
    url: str | None
    filehash: str


class ImageRow(TypedDict, total=False):
    """One gallery entry: an artifact and the media item attached to it."""

    id: int
    artifact: int
    image: int
    image_detail: MediaDetail


class ListImage(TypedDict):
    """What ``artifact image list`` returns: the artifact's gallery."""

    count: int
    results: list[ImageRow]


class AttachImage(ImageRow):
    """What ``artifact image attach`` returns: the gallery entry (existing or new)."""


class GetImage(ImageRow):
    """What ``artifact image get`` returns: the gallery entry."""


class DetachImage(TypedDict):
    """What ``artifact image detach`` returns."""

    domain: str
    slug: str
    id: str
    detached: bool
