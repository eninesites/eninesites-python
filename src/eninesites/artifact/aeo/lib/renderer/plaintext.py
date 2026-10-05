"""The artifact AEO views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import AeoRow, CreateAeo, DeleteAeo, GetAeo, UpdateAeo

FIELDS = ("who", "what", "when_info", "where_info", "why", "how", "extra_data")


def _aeo(aeo: AeoRow) -> None:
    text.record(aeo, FIELDS)
    faqs = aeo.get("faqs") or []
    if faqs:
        text.line("")
        text.table(faqs, ["id", "question", "answer"])


def print_get(result: GetAeo) -> None:
    """``artifact aeo get`` as text."""
    if result["aeo"] is None:
        text.line(f"{result['slug']} has no AEO data")
        return
    _aeo(result["aeo"])


def print_create(result: CreateAeo) -> None:
    """``artifact aeo create`` as text."""
    _aeo(result["aeo"])


def print_update(result: UpdateAeo) -> None:
    """``artifact aeo update`` as text."""
    _aeo(result["aeo"])


def print_delete(result: DeleteAeo) -> None:
    """``artifact aeo delete`` as text."""
    text.line(f"Deleted the AEO data of {result['slug']}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
