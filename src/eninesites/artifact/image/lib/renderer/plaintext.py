"""The artifact image views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import AttachImage, DetachImage, GetImage, ImageRow, ListImage


def _flat(row: ImageRow) -> dict[str, object]:
    detail = row.get("image_detail") or {}
    return {
        "id": row.get("id"),
        "image": row.get("image"),
        "media_slug": detail.get("slug"),
        "filename": detail.get("filename"),
        "url": detail.get("url"),
    }


def print_list(result: ListImage) -> None:
    """``artifact image list`` as text: one row per gallery entry."""
    text.table(
        [_flat(r) for r in result["results"]],
        ["id", "image", "media_slug", "filename", "url"],
    )


def print_attach(result: AttachImage) -> None:
    """``artifact image attach`` as text."""
    text.record(_flat(result))


def print_get(result: GetImage) -> None:
    """``artifact image get`` as text."""
    text.record(_flat(result))


def print_detach(result: DetachImage) -> None:
    """``artifact image detach`` as text."""
    text.line(f"Removed gallery entry {result['id']} from {result['slug']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
