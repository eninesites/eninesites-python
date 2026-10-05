"""The urlmap views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import CreateUrlmap, DeleteUrlmap, GetUrlmap, ListUrlmap, UpdateUrlmap

COLUMNS = ["id", "path", "projection", "artifact", "is_canonical"]


def print_list(result: ListUrlmap) -> None:
    """``urlmap list`` as text: one row per mapping."""
    text.table(result["results"], COLUMNS)


def print_create(result: CreateUrlmap) -> None:
    """``urlmap create`` as text."""
    text.record(result, COLUMNS)


def print_get(result: GetUrlmap) -> None:
    """``urlmap get`` as text."""
    text.record(result, COLUMNS)


def print_update(result: UpdateUrlmap) -> None:
    """``urlmap update`` as text."""
    text.record(result, COLUMNS)


def print_delete(result: DeleteUrlmap) -> None:
    """``urlmap delete`` as text."""
    text.line(f"Deleted URL map {result['id']} from {result['domain']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
