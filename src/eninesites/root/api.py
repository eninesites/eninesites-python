"""The eninesites root api: credentials and configuration, the Stripe CLI's way.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

``login`` validates a key against the server (``GET /api/v1/site/``) and only then stores it
in the profile; ``logout`` removes it; ``config`` reports what a command would use. The key
is the server's ``CustomToken`` (``Authorization: Token <key>``), minted by an eninesites
operator; there is no browser pairing flow on the server to log in through.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Callable

from eninesites.errors import ApiError
from eninesites.lib.client import config, credentials
from eninesites.lib.client.http import Client

from .lib.results import ConfigRoot, LoginRoot, LogoutRoot


def login_root(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> LoginRoot:
    """Check ``api_key`` against the server, then store it in the project's profile.

    The key must be given (the cli asks for it, hidden, or reads it from stdin); a key from
    the environment or the file is not "logged in" again. ``--base-url``, when given, is
    stored beside the key, so a dev-server profile keeps pointing at the dev server. A key
    the server refuses is not stored.
    """
    key = (api_key or "").strip()
    if not key:
        raise ApiError(
            "login: no API key given. Type it at the prompt, pipe it on stdin, or pass "
            "--api-key <key>. An eninesites operator issues keys."
        )
    resolved = credentials.resolve(base_url=base_url, project_name=project_name)
    settings = dataclasses.replace(resolved, api_key=key, api_key_source="flag")
    sites = Client(settings).get("/api/v1/site/")
    path = config.update_profile(
        settings.project_name,
        api_key=key,
        base_url=settings.base_url if base_url else _stored_base_url(settings),
    )
    return {
        "project_name": settings.project_name,
        "config_path": str(path),
        "base_url": settings.base_url,
        "api_key": credentials.redact(key),
        "sites": len(sites) if isinstance(sites, list) else 0,
    }


def _stored_base_url(settings: credentials.Settings) -> str | None:
    """The base URL already stored in the profile, kept as it is when ``--base-url`` is absent."""
    return (
        config.load(settings.config_path).get(settings.project_name, {}).get("base_url")
    )


def logout_root(*, project_name: str | None = None, all_: bool = False) -> LogoutRoot:
    """Remove the stored key from the project's profile, or from every profile with ``--all``.

    The profile's other settings (``base_url``, ``site``) stay, as Stripe's logout keeps
    non-auth fields. A key in ``ENINESITES_API_KEY`` is not the file's to remove; the
    result says when one is still set.
    """
    project = credentials.resolve(project_name=project_name).project_name
    path = config.config_path()
    profiles = config.load(path)
    names = sorted(profiles) if all_ else [project]
    cleared = [n for n in names if profiles.get(n, {}).get("api_key")]
    for name in cleared:
        config.update_profile(name, path, api_key=None)
    return {
        "project_name": project,
        "all": all_,
        "cleared": cleared,
        "config_path": str(path),
        "env_key_set": bool(os.environ.get(credentials.ENV_API_KEY)),
    }


def config_root(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ConfigRoot:
    """Each setting a command run with these flags would use, and where it came from.

    Local only: nothing is sent. The key is shown redacted, always.
    """
    settings = credentials.resolve(api_key, base_url, project_name)
    return {
        "project_name": settings.project_name,
        "project_source": settings.project_source,
        "config_path": str(settings.config_path),
        "config_exists": settings.config_path.is_file(),
        "base_url": settings.base_url,
        "base_url_source": settings.base_url_source,
        "api_key": credentials.redact(settings.api_key),
        "api_key_source": settings.api_key_source,
        "site": settings.site,
        "site_source": settings.site_source,
    }


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "login": login_root,
    "logout": logout_root,
    "config": config_root,
}
