"""The tag views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import CreateTag, DeleteTag, GetTag, ListTag, UpdateTag

COLUMNS = ["id", "slug", "name"]


def print_list(result: ListTag) -> None:
    """``tag list`` as text: one row per tag."""
    text.table(result["results"], COLUMNS)


def print_create(result: CreateTag) -> None:
    """``tag create`` as text."""
    text.record(result, COLUMNS)


def print_get(result: GetTag) -> None:
    """``tag get`` as text."""
    text.record(result, COLUMNS)


def print_update(result: UpdateTag) -> None:
    """``tag update`` as text."""
    text.record(result, COLUMNS)


def print_delete(result: DeleteTag) -> None:
    """``tag delete`` as text."""
    text.line(f"Deleted tag {result['slug']} from {result['domain']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
