"""The shapes the artifact AEO api returns: one TypedDict per verb, and its rows.

The one home of every AEO result shape. Fields follow the server's
``ArtifactXEODataSerializer`` (``rest.py:255-301``): the six W's plus FAQs. ``when_info``,
``where_info``, ``how`` and ``extra_data`` are free-form JSON on the server, so they are
typed as bounded JSON values (``lib.jsonvalue``).
"""

from __future__ import annotations

from typing import TypedDict

from eninesites.lib.jsonvalue import Json, JsonObject


class FaqRow(TypedDict, total=False):
    """One FAQ question/answer pair on the artifact."""

    id: int
    question: str
    answer: str


class AeoRow(TypedDict, total=False):
    """An artifact's XEO (six-W) data."""

    id: int
    who: str | None
    what: str | None
    when_info: JsonObject | None
    where_info: JsonObject | None
    why: str | None
    how: list[JsonObject] | None
    extra_data: Json
    faqs: list[FaqRow]


class GetAeo(TypedDict):
    """What ``artifact aeo get`` returns: the data, or null when the artifact has none."""

    domain: str
    slug: str
    aeo: AeoRow | None


class CreateAeo(TypedDict):
    """What ``artifact aeo create`` returns: the data as saved."""

    domain: str
    slug: str
    aeo: AeoRow


class UpdateAeo(TypedDict):
    """What ``artifact aeo update`` returns: the data as saved."""

    domain: str
    slug: str
    aeo: AeoRow


class DeleteAeo(TypedDict):
    """What ``artifact aeo delete`` returns."""

    domain: str
    slug: str
    deleted: bool
