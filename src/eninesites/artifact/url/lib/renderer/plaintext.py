"""The artifact.url views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing, and it reads the same types
the api returns, so what it prints cannot drift from them.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import AttachUrl, DetachUrl, GetUrl, ListUrl, UpdateUrl


def print_list(result: ListUrl) -> None:
    """``artifact url list`` as text: one row per external URL, in order."""
    text.table(result["results"], ["id", "order", "name", "href"])


def print_attach(result: AttachUrl) -> None:
    """``artifact url attach`` as text."""
    text.record(dict(result))


def print_get(result: GetUrl) -> None:
    """``artifact url get`` as text."""
    text.record(dict(result))


def print_update(result: UpdateUrl) -> None:
    """``artifact url update`` as text."""
    text.record(dict(result))


def print_detach(result: DetachUrl) -> None:
    """``artifact url detach`` as text."""
    text.line(f"Detached external URL {result['id']} from {result['slug']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
