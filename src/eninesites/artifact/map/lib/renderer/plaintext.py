"""The artifact map views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import CandidatesMap, CreateMap, DeleteMap, GetMap, ListMap, UpdateMap

COLUMNS = [
    "id",
    "artifact_a",
    "artifact_a_name",
    "artifact_b",
    "artifact_b_name",
    "order",
]


def print_list(result: ListMap) -> None:
    """``artifact map list`` as text: one row per edge."""
    text.table(result["results"], COLUMNS)


def print_create(result: CreateMap) -> None:
    """``artifact map create`` as text."""
    text.record(result, COLUMNS)


def print_get(result: GetMap) -> None:
    """``artifact map get`` as text."""
    text.record(result, COLUMNS)


def print_update(result: UpdateMap) -> None:
    """``artifact map update`` as text."""
    text.record(result, COLUMNS)


def print_delete(result: DeleteMap) -> None:
    """``artifact map delete`` as text."""
    text.line(f"Deleted map {result['id']} of {result['slug']}")


def print_candidates(result: CandidatesMap) -> None:
    """``artifact map candidates`` as text: each parent, then its children by id."""
    if not result["results"]:
        text.line("(none)")
    for parent in result["results"]:
        text.line(f"{parent.get('label', '')} ({parent.get('id', '')})")
        for child in parent.get("children") or []:
            text.line(f"  {child.get('id', '')}  {child.get('label', '')}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
