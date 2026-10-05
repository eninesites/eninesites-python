"""The shapes the url api returns: one TypedDict per verb, and its rows.

The one home of every external-URL result shape. A row follows the server's
``ExternalURLSerializer`` (``rest.py:361-376``): ``name`` is derived from the label by the
server and is the entry's handle in every other call.
"""

from __future__ import annotations

from typing import TypedDict


class UrlRow(TypedDict, total=False):
    """One entry of the site's external URL catalog."""

    id: int
    name: str
    label: str
    url: str
    params: str
    href: str
    urlhash: str


class ListUrl(TypedDict):
    """What ``url list`` returns: the catalog, by name."""

    count: int
    results: list[UrlRow]


class CreateUrl(UrlRow):
    """What ``url create`` returns: the entry created."""


class GetUrl(UrlRow):
    """What ``url get`` returns: the entry."""


class UpdateUrl(UrlRow):
    """What ``url update`` returns: the entry as updated."""


class DeleteUrl(TypedDict):
    """What ``url delete`` returns."""

    domain: str
    name: str
    deleted: bool
