"""The shapes the artifact role api returns: one TypedDict per verb.

The one home of every role result shape. The server answers every role call with the
artifact's sorted role codes, ``{"roles": [...]}`` (``resources.py:201-253``).
"""

from __future__ import annotations

from typing import TypedDict


class Roles(TypedDict):
    """An artifact's XEO role codes after the call."""

    domain: str
    slug: str
    roles: list[str]


class ListRole(Roles):
    """What ``artifact role list`` returns."""


class ReplaceRole(Roles):
    """What ``artifact role replace`` returns: the roles now assigned."""


class AssignRole(Roles):
    """What ``artifact role assign`` returns: the roles now assigned."""


class UnassignRole(Roles):
    """What ``artifact role unassign`` returns: the roles now assigned."""
