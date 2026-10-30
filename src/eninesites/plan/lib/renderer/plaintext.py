"""The plan views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing, and it reads the same types
the api returns, so what it prints cannot drift from them.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import ListPlan


def print_list(result: ListPlan) -> None:
    """``plan list`` as text: one row per plan; a null ``max_sites`` reads as unlimited."""
    shown = [
        {
            **row,
            "max_sites": (
                "unlimited" if row.get("max_sites") is None else row["max_sites"]
            ),
        }
        for row in result["results"]
    ]
    text.table(shown, ["slug", "name", "price", "max_sites"])


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
