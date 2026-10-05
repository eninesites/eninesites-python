"""The artifact design views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import GetDesign, UpdateDesign


def print_get(result: GetDesign) -> None:
    """``artifact design get`` as text: the design's fields, or that there is none."""
    if result["design"] is None:
        text.line(f"{result['slug']} has no design")
        return
    text.record(result["design"])


def print_update(result: UpdateDesign) -> None:
    """``artifact design update`` as text: the design as saved."""
    text.record(result["design"])


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
