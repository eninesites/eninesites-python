"""The shapes the user api returns: one TypedDict per verb, and its rows.

The one home of every site-user result shape. A row follows the server's
``UserSerializer`` (``rest.py:411-425``): a site membership and its role.
"""

from __future__ import annotations

from typing import TypedDict


class UserRow(TypedDict, total=False):
    """One member of the site and their role (admin, editor or reader)."""

    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    job_title: str


class ListUser(TypedDict):
    """What ``user list`` returns: the site's members."""

    count: int
    results: list[UserRow]


class AddUser(UserRow):
    """What ``user add`` returns: the membership created or changed."""


class GetUser(UserRow):
    """What ``user get`` returns: the membership."""


class UpdateUser(UserRow):
    """What ``user update`` returns: the membership with its new role."""
