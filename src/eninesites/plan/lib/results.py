"""The shapes the plan api returns: one TypedDict per verb, and its rows.

The one home of every plan result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. They live in
``lib`` so the api and the renderers can both import them while nothing in ``lib``
imports the api. A result holds JSON types only: a date is an ISO string, an exact
amount a decimal string, never a float.

A row the server sends is ``total=False``: the api keeps only the keys declared here, and a
key the server omits is absent rather than invented.
"""

from __future__ import annotations

from typing import TypedDict


class PlanRow(TypedDict, total=False):
    """One plan the caller may create a site on (``GET /api/v1/plans/``)."""

    slug: str
    name: str
    description: str
    price: str
    max_sites: int | None


class ListPlan(TypedDict):
    """What ``plan list`` returns: the plans ``site create --plan`` accepts, cheapest first."""

    count: int
    results: list[PlanRow]
