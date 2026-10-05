"""The shapes the artifact map api returns: one TypedDict per verb, and its rows.

The one home of every map result shape. Fields follow the server's
``ArtifactMapSerializer`` (``rest.py:304-326``) and the candidates view
(``resources.py:394-415``). Server rows are ``total=False``.
"""

from __future__ import annotations

from typing import TypedDict


class MapRow(TypedDict, total=False):
    """One cross-reference edge between two artifacts."""

    id: int
    artifact_a: int
    artifact_b: int
    artifact_a_name: str
    artifact_b_name: str
    order: int | None


class CandidateChild(TypedDict, total=False):
    """An artifact this one may map to."""

    id: int
    label: str


class CandidateRow(TypedDict, total=False):
    """A parent artifact and the children under it that are valid map targets."""

    id: int
    label: str
    children: list[CandidateChild]


class ListMap(TypedDict):
    """What ``artifact map list`` returns: every edge touching the artifact."""

    count: int
    results: list[MapRow]


class CreateMap(MapRow):
    """What ``artifact map create`` returns: the edge created."""


class GetMap(MapRow):
    """What ``artifact map get`` returns: the edge."""


class UpdateMap(MapRow):
    """What ``artifact map update`` returns: the edge as updated."""


class DeleteMap(TypedDict):
    """What ``artifact map delete`` returns."""

    domain: str
    slug: str
    id: str
    deleted: bool


class CandidatesMap(TypedDict):
    """What ``artifact map candidates`` returns: valid targets, grouped by parent."""

    count: int
    results: list[CandidateRow]
