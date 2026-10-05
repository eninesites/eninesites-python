"""The artifact tag views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import AttachTag, DetachTag, ListTag


def print_list(result: ListTag) -> None:
    """``artifact tag list`` as text."""
    text.table(result["tags"], ["id", "slug", "name"])


def print_attach(result: AttachTag) -> None:
    """``artifact tag attach`` as text: the tags now on the artifact."""
    text.table(result["tags"], ["id", "slug", "name"])


def print_detach(result: DetachTag) -> None:
    """``artifact tag detach`` as text."""
    text.line(f"Removed tag {result['tag']} from {result['slug']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
