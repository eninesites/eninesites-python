"""The theme custom api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server route: ``/api/v1/site/<d>/custom-themes/`` (``CustomThemeExportImportView``,
``rest.py:1085-1177``): GET ``?name=`` exports, POST imports (creating or replacing the
templates) and makes the imported theme the site's active theme.
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
from eninesites.lib.client.records import json_file, project

from .lib.results import CustomTheme, ExportCustom, ImportCustom


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


def import_custom(
    *,
    name: str | None = None,
    parent: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    path: Path | None = None,
) -> ImportCustom:
    """Import a custom theme from a JSON file: ``POST .../custom-themes/``.

    ``--path`` is either an export (``theme custom export --json`` output, or the bare
    ``{"custom_theme": ...}`` the server sends) or a ``{"<path>": "<source>"}`` map.
    ``--name`` and ``--parent`` override the file's; both must end up set.
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
    client = connect(api_key, base_url, project_name, domain)
    payload = client.json(
        "POST", client.site_path("custom-themes"), body={"custom_theme": theme}
    )
    reply = payload if isinstance(payload, dict) else {}
    return {
        "domain": credentials.require_site(client.settings),
        "name": str(reply.get("name", theme["name"])),
        "theme": str(reply.get("theme", "")),
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "export": export_custom,
    "import": import_custom,
}
