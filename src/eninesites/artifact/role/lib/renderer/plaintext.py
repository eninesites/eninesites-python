"""The artifact role views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import AssignRole, ListRole, ReplaceRole, Roles, UnassignRole


def _roles(result: Roles) -> None:
    text.line(f"{result['slug']}: {', '.join(result['roles']) or '(no roles)'}")


def print_list(result: ListRole) -> None:
    """``artifact role list`` as text."""
    _roles(result)


def print_replace(result: ReplaceRole) -> None:
    """``artifact role replace`` as text."""
    _roles(result)


def print_assign(result: AssignRole) -> None:
    """``artifact role assign`` as text."""
    _roles(result)


def print_unassign(result: UnassignRole) -> None:
    """``artifact role unassign`` as text."""
    _roles(result)


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
