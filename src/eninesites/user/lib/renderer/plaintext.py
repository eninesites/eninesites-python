"""The user views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import AddUser, GetUser, ListUser, UpdateUser

COLUMNS = ["username", "email", "role", "first_name", "last_name"]


def print_list(result: ListUser) -> None:
    """``user list`` as text: one row per member."""
    text.table(result["results"], COLUMNS)


def print_add(result: AddUser) -> None:
    """``user add`` as text."""
    text.record(result)


def print_get(result: GetUser) -> None:
    """``user get`` as text."""
    text.record(result)


def print_update(result: UpdateUser) -> None:
    """``user update`` as text."""
    text.record(result)


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
