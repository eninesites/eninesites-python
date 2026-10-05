"""The shapes the audit api returns: one TypedDict per verb, and its rows.

The one home of every XEO audit result shape. Fields follow ``XEOAuditRunView`` and
``XEOCheckView`` (``siteops.py:296-373``), whose bodies the server wraps in
``{"success": true, "data": ...}``; the api unwraps them. Finding entries are free-form on
the server (strings, or objects for artifact-stage findings), so they are bounded JSON.
"""

from __future__ import annotations

from typing import TypedDict

from eninesites.lib.jsonvalue import Json


class SeoFindings(TypedDict, total=False):
    """The SEO half of one audited URL."""

    status_code: int | None
    title: str | None
    errors: list[Json]
    warnings: list[Json]


class AeoFindings(TypedDict, total=False):
    """The AEO half of one audited URL."""

    faq_count: int | None
    sixw_keys: Json
    errors: list[str]
    warnings: list[str]


class ArtifactFindings(TypedDict, total=False):
    """Artifact-stage findings for one artifact on one URL."""

    name: str | None
    slug: str | None
    stage: str | None
    errors: list[str | None]
    warnings: list[str | None]


class AuditUrl(TypedDict, total=False):
    """One URL of the latest audit, with its counts and findings."""

    url: str
    total_errors: int
    total_warnings: int
    seo: SeoFindings
    aeo: AeoFindings
    artifacts: list[ArtifactFindings]


class RunAudit(TypedDict, total=False):
    """What ``audit run`` returns: the audit the server ran and stored."""

    audit_id: int
    domain: str
    status: str
    total_urls: int
    total_errors: int
    total_warnings: int


class GetAudit(TypedDict):
    """What ``audit get`` returns: the latest stored audit, per URL (empty when none ran)."""

    domain: str
    audited: bool
    count: int
    results: list[AuditUrl]
