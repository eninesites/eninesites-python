"""The theme views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing, and it reads the same types
the api returns, so what it prints cannot drift from them.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import CheckTheme, CreateTheme, DeleteTheme, ListTheme, ReviewTheme


def print_create(result: CreateTheme) -> None:
    """``theme create`` as text, one ``key: value`` line per field."""
    for key, value in result.items():
        print(f"{key}: {value}")


def print_list(result: ListTheme) -> None:
    """``theme list`` as text: one row per selectable theme."""
    text.table(result["results"], ["name", "label", "is_canon", "is_public"])


def print_delete(result: DeleteTheme) -> None:
    """``theme delete`` as text, one ``key: value`` line per field."""
    for key, value in result.items():
        print(f"{key}: {value}")


def print_check(result: CheckTheme) -> None:
    """``theme check`` as text, one ``key: value`` line per field."""
    for key, value in result.items():
        print(f"{key}: {value}")


def print_review(result: ReviewTheme) -> None:
    """``theme review`` as text, one ``key: value`` line per field."""
    for key, value in result.items():
        print(f"{key}: {value}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
