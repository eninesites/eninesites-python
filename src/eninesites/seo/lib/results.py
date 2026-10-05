"""The shapes the seo api returns: one TypedDict per verb, and its rows.

The one home of every SEO-page result shape. A row follows the server's ``SEOPageSerializer``:
``canonical`` is the page's canonical URL, unique per site.
"""

from __future__ import annotations

from typing import TypedDict


class SeoPageRow(TypedDict, total=False):
    """One SEO page: the metadata a canonical URL is served with."""

    id: int
    canonical: str
    page_name: str
    page_title: str
    description: str
    keywords: str


class ListSeo(TypedDict):
    """What ``seo list`` returns: the site's SEO pages, by canonical URL."""

    count: int
    results: list[SeoPageRow]


class CreateSeo(SeoPageRow):
    """What ``seo create`` returns: the SEO page created."""


class GetSeo(SeoPageRow):
    """What ``seo get`` returns: the SEO page."""


class UpdateSeo(SeoPageRow):
    """What ``seo update`` returns: the SEO page as updated."""


class DeleteSeo(TypedDict):
    """What ``seo delete`` returns."""

    domain: str
    id: str
    deleted: bool
