"""The artifact views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing, and it reads the same types
the api returns, so what it prints cannot drift from them.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import (
    ArtifactRow,
    CreateArtifact,
    DeleteArtifact,
    GetArtifact,
    ListArtifact,
    UpdateArtifact,
)

#: The fields an artifact's text view shows, in order; children print as a table after.
FIELDS = (
    "id",
    "name",
    "slug",
    "title",
    "depth",
    "pnode_id",
    "order",
    "is_published",
    "is_featured",
    "navbar",
    "footer",
    "pnc",
    "url",
    "description",
)


def _artifact(result: ArtifactRow) -> None:
    text.record(result, FIELDS)
    children = result.get("children") or []
    if children:
        text.line("")
        text.table(children, ["id", "name", "slug", "title", "order", "is_published"])


def print_list(result: ListArtifact) -> None:
    """``artifact list`` as text: one row per root artifact."""
    text.table(
        [
            {**row, "children": len(row.get("children") or [])}
            for row in result["results"]
        ],
        ["id", "name", "slug", "title", "order", "is_published", "children"],
    )


def print_get(result: GetArtifact) -> None:
    """``artifact get`` as text: its fields, then its children."""
    _artifact(result)


def print_create(result: CreateArtifact) -> None:
    """``artifact create`` as text: the artifact as created."""
    _artifact(result)


def print_update(result: UpdateArtifact) -> None:
    """``artifact update`` as text: the artifact as updated."""
    _artifact(result)


def print_delete(result: DeleteArtifact) -> None:
    """``artifact delete`` as text."""
    text.line(f"Deleted artifact {result['slug']} from {result['domain']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
