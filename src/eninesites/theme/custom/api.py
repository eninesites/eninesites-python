"""The theme custom api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server route: ``/api/v1/site/<d>/custom-themes/`` (``CustomThemeExportImportView``,
``rest.py:1085-1177``): GET ``?name=`` exports, POST imports (creating or replacing the
templates) and makes it the live theme only when asked, DELETE ``?name=`` removes one.
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
from eninesites.lib.client.records import boolean, json_file, project, required
from eninesites.lib.dryrun import PlannedRequest, writes

from .lib.results import CustomTheme, DeleteCustom, ExportCustom, ImportCustom


def export_custom(
    *,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ExportCustom:
    """One custom theme with its templates: ``GET .../custom-themes/?name=<label>``."""
    client = connect(api_key, base_url, project_name, domain)
    # Without --name the server answers 400 `missing_name`, which names the problem.
    query: dict[str, str | int] = (
        {"name": name.strip()} if name and name.strip() else {}
    )
    payload = client.get(client.site_path("custom-themes"), query)
    theme = payload.get("custom_theme") if isinstance(payload, dict) else None
    return {
        "domain": credentials.require_site(client.settings),
        "custom_theme": project(theme or {}, CustomTheme),
    }


@writes
def import_custom(
    *,
    name: str | None = None,
    parent: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    path: Path | None = None,
    activate: str | None = None,
    dry_run: bool = False,
) -> ImportCustom | PlannedRequest:
    """Import a custom theme from a JSON file: ``POST .../custom-themes/``.

    ``--path`` is either an export (``theme custom export --json`` output, or the bare
    ``{"custom_theme": ...}`` the server sends) or a ``{"<path>": "<source>"}`` map.
    ``--name`` and ``--parent`` override the file's; both must end up set. Without
    ``--activate true`` the live theme stays: the server makes an import live only when asked.
    """
    theme: dict[str, object] = {}
    if path is not None:
        loaded = json_file(Path(path), "--path")
        if not isinstance(loaded, dict):
            raise ApiError(f"--path {path}: must hold a JSON object")
        exported = loaded.get("custom_theme")
        theme = dict(exported) if isinstance(exported, dict) else {"templates": loaded}
    if name:
        theme["name"] = name
    if parent:
        theme["parent"] = parent
    for key in ("name", "parent"):
        if not theme.get(key):
            raise ApiError(
                f"theme custom import: --{key} is required (or in the --path file)"
            )
    theme.setdefault("templates", {})
    body: dict[str, object] = {"custom_theme": theme}
    live = boolean(activate, "--activate")
    if live is not None:
        body["activate"] = live
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    payload = client.json("POST", client.site_path("custom-themes"), body=body)
    reply = payload if isinstance(payload, dict) else {}
    previous = reply.get("previous_theme")
    return {
        "domain": credentials.require_site(client.settings),
        "name": str(reply.get("name", theme["name"])),
        "theme": str(reply.get("theme", "")),
        "active": reply.get("active") is True,
        "previous_theme": None if previous is None else str(previous),
    }


@writes
def delete_custom(
    *,
    name: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
) -> DeleteCustom | PlannedRequest:
    """Delete a custom theme and its templates: ``DELETE .../custom-themes/?name=`` (204).

    The server refuses with 409 a theme that is public (``theme_public``), any site's live
    theme (``theme_in_use``), or the parent of another theme (``theme_has_children``).
    """
    label = required(
        name, "--name", "the custom theme's name, from `theme custom export`"
    )
    client = connect(api_key, base_url, project_name, domain, dry_run=dry_run)
    client.request("DELETE", client.site_path("custom-themes"), query={"name": label})
    return {
        "domain": credentials.require_site(client.settings),
        "name": label,
        "deleted": True,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "export": export_custom,
    "import": import_custom,
    "delete": delete_custom,
}
