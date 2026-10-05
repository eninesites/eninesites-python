"""The shapes the theme api returns: one TypedDict per verb, and its rows.

The one home of every theme result shape. A row follows ``ThemeListView``
(``rest.py:1056-1082``). ``create``, ``delete``, ``check`` and ``review`` have no REST
endpoint, so their types stay empty: they never return.
"""

from __future__ import annotations

from typing import TypedDict


class ThemeRow(TypedDict, total=False):
    """A theme the site may select: canon, public, or one of its own custom themes."""

    name: str
    label: str
    is_public: bool
    is_canon: bool


class CreateTheme(TypedDict):
    """What ``theme create`` would return. It has no REST endpoint, so it never returns."""


class ListTheme(TypedDict):
    """What ``theme list`` returns: the themes the site may select, by name."""

    domain: str
    count: int
    results: list[ThemeRow]


class DeleteTheme(TypedDict):
    """What ``theme delete`` would return. It has no REST endpoint, so it never returns."""


class CheckTheme(TypedDict):
    """What ``theme check`` would return. It has no REST endpoint, so it never returns."""


class ReviewTheme(TypedDict):
    """What ``theme review`` would return. It has no REST endpoint, so it never returns."""
