"""The audit api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``services/manager/urls/apiurls/xeo.py``): ``POST
/api/v1/manager/<d>/xeo-audit/`` runs a full XEO audit synchronously (crawls the sitemap;
can take a while) and ``GET /api/v1/manager/<d>/xeo-check/`` returns the latest stored one.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from eninesites.lib.client import credentials
from eninesites.lib.client.http import Client, connect, segment
from eninesites.lib.client.records import project, refuse_unsupported, rows
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import AuditUrl, GetAudit, RunAudit


def _manager_path(client: Client, action: str) -> tuple[str, str]:
    site = credentials.require_site(client.settings)
    return site, f"/api/v1/manager/{segment(site)}/{action}/"


def _data(payload: Any) -> Any:
    """The body inside the ``{"success": true, "data": ...}`` wrapper these views use."""
    return payload.get("data") if isinstance(payload, dict) else None


@writes
def run_audit(
    *,
    domain: str | None = None,
    limit: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> RunAudit | PlannedRequest:
    """Run and store a full XEO audit of the site: ``POST .../xeo-audit/``."""
    refuse_unsupported("audit run", "the server audits every sitemap URL", limit=limit)
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    _, path = _manager_path(client, "xeo-audit")
    result: RunAudit = project(_data(client.json("POST", path)), RunAudit)
    return result


def get_audit(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetAudit:
    """The latest stored audit, per URL: ``GET .../xeo-check/``."""
    client = connect(api_key, base_url, project_name, domain)
    site, path = _manager_path(client, "xeo-check")
    data = _data(client.get(path)) or {}
    found = rows(data.get("results") or [], AuditUrl) if isinstance(data, dict) else []
    audited = isinstance(data, dict) and "results" in data
    return {"domain": site, "audited": audited, "count": len(found), "results": found}


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "run": run_audit,
    "get": get_audit,
}
