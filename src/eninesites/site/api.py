"""The site api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Each verb reaches the eninesites REST API through ``lib.client`` (server routes in
``services/manager/urls/apiurls/sites.py``). ``site select`` is local: it records the site
later commands use when ``--domain`` is not given. ``delete``, ``check``, ``review``,
``propose`` and ``build`` have no REST endpoint and refuse.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from eninesites.errors import ApiError
from eninesites.lib.client import config, credentials
from eninesites.lib.client.http import connect, filename_from
from eninesites.lib.client.records import (
    json_file,
    merged,
    not_over_rest,
    refuse_unsupported,
    rows,
)

from .lib.results import (
    BuildSite,
    CheckSite,
    ConfigureSite,
    CopySite,
    CreateSite,
    DeleteSite,
    DumpSite,
    ListSite,
    LoadSite,
    ProposeSite,
    RandomizeSubdomainSite,
    RestoreSite,
    ReviewSite,
    SelectSite,
    SiteRow,
)

#: ``?dl=`` formats ``SiteDetailView.get`` serves, and the extension each is saved under.
DUMP_FORMATS = {
    "json": "json",
    "yaml": "yaml",
    "csv": "csv",
    "zip": "zip",
    "media": "zip",
}
#: What ``POST /api/v1/site/<d>/`` parses as an upsert; a .zip is ``site restore``.
LOAD_SUFFIXES = (".json", ".yml", ".yaml", ".csv")
RESTORE_MODES = ("merge", "clobber", "replace")


def create_site(
    *,
    name: str | None = None,
    user: str | None = None,
    domain: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    theme: str | None = None,
    plan: Path | None = None,
    sample: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    data: Path | None = None,
) -> CreateSite:
    """Create a site owned by the caller: ``POST /api/v1/site/``.

    ``--domain`` is the NEW site's domain; without it a free plan is served on an allocated
    subdomain. ``--data`` carries any other body field (``config``, ``colors``, ``content``,
    ``template``); the named flags override it.
    """
    refuse_unsupported(
        "site create",
        "the server makes the caller the owner, and sample content is a manage.py option",
        user=user,
        sample=sample,
    )
    body = merged(
        data,
        domain=domain,
        name=name,
        email=email,
        phone=phone,
        plan=str(plan) if plan else None,
    )
    if theme:
        site_config = body.setdefault("config", {})
        if not isinstance(site_config, dict):
            raise ApiError("--data: 'config' must be a JSON object")
        site_config["theme"] = {"name": theme, "path": f"{theme}/templates"}
    client = connect(api_key, base_url, project_name)
    payload = client.json("POST", "/api/v1/site/", body=body)
    return {"domain": str((payload or {}).get("domain", ""))}


def list_site(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListSite:
    """Every site the caller is a member of: ``GET /api/v1/site/`` (a bare array)."""
    client = connect(api_key, base_url, project_name)
    found = rows(client.get("/api/v1/site/"), SiteRow)
    return {"count": len(found), "results": found}


def dump_site(
    *,
    domain: str | None = None,
    output: Path | None = None,
    format_: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> DumpSite:
    """Save the site's export to a file: ``GET /api/v1/site/<d>/?dl=<format>``.

    Formats: json (default), yaml, csv, zip (the portable archive ``site restore`` takes
    back) and media. The file is named by ``--output`` (a file, or a directory to put it
    in), else by the server's ``Content-Disposition``; an existing file is replaced.
    """
    fmt = (format_ or "json").lower()
    if fmt not in DUMP_FORMATS:
        raise ApiError(f"--format {fmt!r}: expected one of {', '.join(DUMP_FORMATS)}")
    client = connect(api_key, base_url, project_name, domain)
    reply = client.request("GET", client.site_path(), query={"dl": fmt})
    site = credentials.require_site(client.settings)
    name = filename_from(reply) or f"{site}.{DUMP_FORMATS[fmt]}"
    target = Path(output).expanduser() if output else Path(name)
    if target.is_dir():
        target = target / name
    _write_atomically(target, reply.body)
    return {
        "domain": site,
        "format": fmt,
        "path": str(target),
        "bytes": len(reply.body),
    }


def _write_atomically(target: Path, content: bytes) -> None:
    """Write ``content`` to ``target`` via a temporary file: a failure leaves no half file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _source(path: Path | None, verb: str, kinds: str) -> Path:
    """The file a verb sends: ``--path``."""
    if path is None:
        raise ApiError(f"{verb}: --path is required ({kinds})")
    return Path(path).expanduser()


def load_site(
    *,
    domain: str | None = None,
    name: str | None = None,
    user: str | None = None,
    email: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    path: Path | None = None,
) -> LoadSite:
    """Upsert a .json/.yml/.yaml/.csv file into an existing site: ``POST /api/v1/site/<d>/``.

    An upsert, not a replace (``docs/API.md``, "Import is an upsert"). Creating a new site
    from a file is ``manage.py site --load``; over REST, create the site first.
    """
    refuse_unsupported(
        "site load",
        "they create a new site, which only manage.py site --load does; "
        "create the site with `site create`, then load into it",
        name=name,
        user=user,
        email=email,
    )
    source = _source(path, "site load", ".json, .yml, .yaml or .csv")
    suffix = source.suffix.lower()
    if suffix not in LOAD_SUFFIXES:
        hint = " (a .zip archive is `site restore`)" if suffix == ".zip" else ""
        raise ApiError(f"--path {source}: expected .json, .yml, .yaml or .csv{hint}")
    client = connect(api_key, base_url, project_name, domain)
    payload = client.json("POST", client.site_path(), files=[source])
    site = (payload or {}).get("domain") or credentials.require_site(client.settings)
    return {"domain": str(site), "file": str(source)}


def restore_site(
    *,
    mode: str | None = None,
    domain: str | None = None,
    name: str | None = None,
    user: str | None = None,
    plan: Path | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    path: Path | None = None,
) -> RestoreSite:
    """Restore a portable .zip over an existing site: ``POST /api/v1/site/<d>/?mode=``.

    ``merge`` (default) keeps rows the archive does not mention, ``clobber`` overwrites rows
    it carries, ``replace`` wipes the site's content and media first. Restoring into a
    fresh site is ``manage.py site --load x.zip``.
    """
    refuse_unsupported(
        "site restore",
        "restoring into a fresh site is manage.py only; restore over an existing --domain",
        name=name,
        user=user,
        plan=plan,
    )
    chosen = (mode or "merge").lower()
    if chosen not in RESTORE_MODES:
        raise ApiError(f"--mode {chosen!r}: expected one of {', '.join(RESTORE_MODES)}")
    source = _source(path, "site restore", "a .zip from `site dump --format zip`")
    if source.suffix.lower() != ".zip":
        raise ApiError(f"--path {source}: expected a .zip archive")
    client = connect(api_key, base_url, project_name, domain)
    payload = client.json(
        "POST", client.site_path(), query={"mode": chosen}, files=[source]
    )
    site = (payload or {}).get("domain") or credentials.require_site(client.settings)
    return {"domain": str(site), "file": str(source), "mode": chosen}


def copy_site(
    *,
    domain: str | None = None,
    to: str | None = None,
    user: str | None = None,
    name: str | None = None,
    plan: Path | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> CopySite:
    """Copy a site losslessly into a new domain: ``POST /api/v1/site/<d>/copy/``."""
    refuse_unsupported("site copy", "the copy is owned by the caller", user=user)
    if not to:
        raise ApiError("site copy: --to <new-domain> is required")
    client = connect(api_key, base_url, project_name, domain)
    body = merged(None, to=to, name=name, plan=str(plan) if plan else None)
    payload = client.json("POST", client.site_path("copy"), body=body)
    return {
        "source": credentials.require_site(client.settings),
        "domain": str((payload or {}).get("domain", to)),
    }


def configure_site(
    *,
    domain: str | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    copyright_: str | None = None,
    theme: str | None = None,
    colors_primary: str | None = None,
    colors_secondary: str | None = None,
    colors_accent: str | None = None,
    colors_body: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    path: Path | None = None,
) -> ConfigureSite:
    """Update theme, config and colors: ``POST /api/v1/site/<d>/configure/``.

    ``--path`` is a JSON file holding an object in the endpoint's own shape (``theme``,
    ``config``, ``colors``, ``design``, ``style``, ``site``); the flags are laid over it.
    """
    body: dict[str, object] = {}
    if path is not None:
        source = _source(path, "site configure", "a JSON file")
        loaded = json_file(source, "--path")
        if not isinstance(loaded, dict):
            raise ApiError(f"--path {source}: must hold a JSON object")
        body = loaded
    if theme:
        body["theme"] = theme
    _section(body, "config", title=title, subtitle=subtitle, copyright=copyright_)
    _section(
        body,
        "colors",
        bg_primary=colors_primary,
        bg_secondary=colors_secondary,
        bg_accent=colors_accent,
        bg_body=colors_body,
    )
    if not body:
        raise ApiError("site configure: no configuration fields provided")
    client = connect(api_key, base_url, project_name, domain)
    payload = client.json("POST", client.site_path("configure"), body=body)
    updated = (payload or {}).get("updated") or []
    return {
        "domain": credentials.require_site(client.settings),
        "updated": [str(u) for u in updated],
    }


def _section(body: dict[str, object], key: str, **fields: str | None) -> None:
    """Lay the given flags into one object of the request body, creating it if needed."""
    given = {k: v for k, v in fields.items() if v is not None}
    if not given:
        return
    section = body.setdefault(key, {})
    if not isinstance(section, dict):
        raise ApiError(f"--path: '{key}' must be a JSON object")
    section.update(given)


def delete_site(*, domain: str | None = None) -> DeleteSite:
    """Refuse: the REST API has no site DELETE (``SiteDetailView`` serves GET and POST)."""
    del domain
    raise not_over_rest("site delete", "it exists only as `manage.py site --delete`")


def check_site(*, domain: str | None = None) -> CheckSite:
    """Refuse: the site health check exists only as ``manage.py site --check``."""
    del domain
    raise not_over_rest("site check", "it exists only as `manage.py site --check`")


def review_site(*, domain: str | None = None) -> ReviewSite:
    """Refuse: the site overview exists only as ``manage.py site --review``."""
    del domain
    raise not_over_rest("site review", "it exists only as `manage.py site --review`")


def select_site(
    *,
    domain: str | None = None,
    project_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> SelectSite:
    """Record the site later commands act on when ``--domain`` is not given.

    Written as the profile's ``site``; ``ENINESITES_SITE`` and ``--domain`` still win. The site
    is checked first, as the server's own ``select_site`` chat tool does: ``GET
    /api/v1/site/<d>/configure/`` answers only for a site that exists (any of its domains) and
    that the key's user is a member of, so a typo or a site without access is refused and
    nothing is saved.
    """
    if not domain or not domain.strip():
        raise ApiError("site select: --domain is required")
    chosen = domain.strip().lower()
    client = connect(api_key, base_url, project_name, chosen)
    try:
        client.json("GET", client.site_path("configure"))
    except ApiError as exc:
        raise ApiError(f"site select: {chosen} was not saved: {exc}") from exc
    path = config.update_profile(client.settings.project_name, site=chosen)
    return {
        "project_name": client.settings.project_name,
        "site": chosen,
        "config_path": str(path),
    }


def randomize_subdomain_site(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> RandomizeSubdomainSite:
    """Give the site a new random subdomain: ``POST /api/v1/site/<d>/random-subdomain/``."""
    client = connect(api_key, base_url, project_name, domain)
    payload = client.json("POST", client.site_path("random-subdomain"))
    return {
        "domain": credentials.require_site(client.settings),
        "subdomain": str((payload or {}).get("subdomain", "")),
    }


def propose_site(
    *, description: str | None = None, name_hint: str | None = None
) -> ProposeSite:
    """Refuse: proposing a site is the chat tool ``propose_site_from_description``."""
    del description, name_hint
    raise not_over_rest(
        "site propose",
        "it exists only as the chat tool `propose_site_from_description`",
    )


def build_site(*, proposal: str | None = None) -> BuildSite:
    """Refuse: building a site from a proposal is the chat tool ``build_site_from_spec``."""
    del proposal
    raise not_over_rest(
        "site build", "it exists only as the chat tool `build_site_from_spec`"
    )


# The verbs the eninesites REST API has no endpoint for: each raises `ApiError` saying
# where the operation lives instead. Read mechanically by the tests, one home.
NOT_OVER_REST: frozenset[str] = frozenset(
    {"delete", "check", "review", "propose", "build"}
)

# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "create": create_site,
    "list": list_site,
    "dump": dump_site,
    "load": load_site,
    "restore": restore_site,
    "copy": copy_site,
    "configure": configure_site,
    "delete": delete_site,
    "check": check_site,
    "review": review_site,
    "select": select_site,
    "randomize-subdomain": randomize_subdomain_site,
    "propose": propose_site,
    "build": build_site,
}
