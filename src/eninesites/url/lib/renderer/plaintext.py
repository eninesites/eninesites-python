"""The url views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import CreateUrl, DeleteUrl, GetUrl, ListUrl, UpdateUrl

COLUMNS = ["id", "name", "label", "href"]


def print_list(result: ListUrl) -> None:
    """``url list`` as text: one row per catalog entry."""
    text.table(result["results"], COLUMNS)


def print_create(result: CreateUrl) -> None:
    """``url create`` as text."""
    text.record(result)


def print_get(result: GetUrl) -> None:
    """``url get`` as text."""
    text.record(result)


def print_update(result: UpdateUrl) -> None:
    """``url update`` as text."""
    text.record(result)


def print_delete(result: DeleteUrl) -> None:
    """``url delete`` as text."""
    text.line(f"Deleted URL {result['name']} from {result['domain']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
