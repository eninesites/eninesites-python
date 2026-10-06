"""The url api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:590-642``): ``/api/v1/site/<d>/urls/`` (GET paginated, POST;
a duplicate URL is 409 ``url_already_exists``) and ``.../urls/<name>/`` (GET, POST partial,
DELETE). ``--name`` is the entry's server-derived ``name``. Body fields (``label``, ``url``,
``params``) come in ``--data``.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from eninesites.errors import ApiError
from eninesites.lib.client import credentials
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import project, request_body, required, rows
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import CreateUrl, DeleteUrl, GetUrl, ListUrl, UpdateUrl, UrlRow

NAME = "the catalog entry's name, from `url list`"


def list_url(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListUrl:
    """The site's external URL catalog: ``GET .../urls/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("urls")), UrlRow)
    return {"count": len(found), "results": found}


@writes
def create_url(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> CreateUrl | PlannedRequest:
    """Add an entry: ``POST .../urls/``; the ``--data`` file holds ``label``, ``url``."""
    body = request_body(data)
    if not body.get("url"):
        raise ApiError(
            "url create: the --data file must hold at least 'url', e.g. "
            '{"label": "Docs", "url": "https://example.com/docs"}'
        )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    result: CreateUrl = project(
        client.json("POST", client.site_path("urls"), body=body), CreateUrl
    )
    return result


def get_url(
    *,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetUrl:
    """One entry: ``GET .../urls/<name>/``."""
    client = connect(api_key, base_url, project_name, domain)
    result: GetUrl = project(
        client.get(client.site_path("urls", required(name, "--name", NAME))), GetUrl
    )
    return result


@writes
def update_url(
    *,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
    dry_run: bool = False,
) -> UpdateUrl | PlannedRequest:
    """Change the fields in ``--data``: ``POST .../urls/<name>/`` (partial)."""
    body = request_body(data)
    if not body:
        raise ApiError("url update: --data is required (the fields to change)")
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    path = client.site_path("urls", required(name, "--name", NAME))
    result: UpdateUrl = project(client.json("POST", path, body=body), UpdateUrl)
    return result


@writes
def delete_url(
    *,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteUrl | PlannedRequest:
    """Delete an entry: ``DELETE .../urls/<name>/`` (204)."""
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    name = required(name, "--name", NAME)
    client.request("DELETE", client.site_path("urls", name))
    return {
        "domain": credentials.require_site(client.settings),
        "name": name,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_url,
    "create": create_url,
    "get": get_url,
    "update": update_url,
    "delete": delete_url,
}
