"""The media views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import DeleteMedia, GetMedia, ListMedia, UpdateMedia, UploadMedia

COLUMNS = ["id", "slug", "filename", "file_type", "url"]


def print_list(result: ListMedia) -> None:
    """``media list`` as text: one row per media item."""
    text.table(result["results"], COLUMNS)


def print_upload(result: UploadMedia) -> None:
    """``media upload`` as text: the rows created or matched."""
    text.table(result["results"], COLUMNS)


def print_get(result: GetMedia) -> None:
    """``media get`` as text."""
    text.record(result)


def print_update(result: UpdateMedia) -> None:
    """``media update`` as text."""
    text.record(result)


def print_delete(result: DeleteMedia) -> None:
    """``media delete`` as text."""
    text.line(f"Deleted media {result['slug']} from {result['domain']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
