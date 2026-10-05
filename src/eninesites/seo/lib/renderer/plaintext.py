"""The seo views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import CreateSeo, DeleteSeo, GetSeo, ListSeo, UpdateSeo

COLUMNS = ["id", "canonical", "page_name", "page_title"]


def print_list(result: ListSeo) -> None:
    """``seo list`` as text: one row per SEO page."""
    text.table(result["results"], COLUMNS)


def print_create(result: CreateSeo) -> None:
    """``seo create`` as text."""
    text.record(result, COLUMNS)


def print_get(result: GetSeo) -> None:
    """``seo get`` as text."""
    text.record(result, COLUMNS)


def print_update(result: UpdateSeo) -> None:
    """``seo update`` as text."""
    text.record(result, COLUMNS)


def print_delete(result: DeleteSeo) -> None:
    """``seo delete`` as text."""
    text.line(f"Deleted SEO page {result['id']} from {result['domain']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
