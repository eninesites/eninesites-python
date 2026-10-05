"""Which API key, base URL, project and site a command uses, and where each came from.

One precedence for every setting, in the Stripe CLI's shape (``Profile.GetAPIKey``,
``--project-name``): the command-line flag, then the environment, then the profile in the
config file, then the built-in default.

- project: ``--project-name``, ``ENINESITES_PROJECT_NAME``, else ``default``.
- API key: ``--api-key``, ``ENINESITES_API_KEY``, the profile's ``api_key``; no default.
- base URL: ``--base-url``, ``ENINESITES_BASE_URL``, the profile's ``base_url``, else
  ``https://eninesites.com`` (the platform host; the API answers nowhere else).
- site: ``--domain``, ``ENINESITES_SITE``, the profile's ``site`` (``site select``); no default.

One deliberate departure from Stripe: its ``STRIPE_API_KEY`` beats ``--api-key``. Here the
flag wins, because a flag typed on this command is the more specific instruction.

The key is the server's ``CustomToken``, sent as ``Authorization: Token <key>``. It is never
printed; ``redact`` is the only form that reaches output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from eninesites.errors import ApiError

from . import config

DEFAULT_BASE_URL = "https://eninesites.com"
ENV_API_KEY = "ENINESITES_API_KEY"
ENV_BASE_URL = "ENINESITES_BASE_URL"
ENV_PROJECT = "ENINESITES_PROJECT_NAME"
ENV_SITE = "ENINESITES_SITE"
#: Hosts a key may be sent to over plain http: a local development server only.
LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class Settings:
    """Everything a request needs, resolved once, with the tier each value came from."""

    project_name: str
    project_source: str
    config_path: Path
    api_key: str | None
    api_key_source: str | None
    base_url: str
    base_url_source: str
    site: str | None
    site_source: str | None


def _pick(
    flag: str | None, env: str, stored: str | None, default: str | None = None
) -> tuple[str | None, str | None]:
    """The first non-empty of flag, environment and profile, and which tier answered."""
    if flag:
        return flag, "flag"
    if os.environ.get(env):
        return os.environ[env], f"env {env}"
    if stored:
        return stored, "config"
    return default, "default" if default else None


def resolve(
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    site: str | None = None,
) -> Settings:
    """Resolve every setting for one command from its flags, the environment and the file."""
    project, project_source = _pick(
        project_name, ENV_PROJECT, None, config.DEFAULT_PROFILE
    )
    assert project is not None and project_source is not None
    path = config.config_path()
    profile = config.load(path).get(project, {})
    key, key_source = _pick(api_key, ENV_API_KEY, profile.get("api_key"))
    url, url_source = _pick(
        base_url, ENV_BASE_URL, profile.get("base_url"), DEFAULT_BASE_URL
    )
    assert url is not None and url_source is not None
    chosen, site_source = _pick(site, ENV_SITE, profile.get("site"))
    return Settings(
        project_name=project,
        project_source=project_source,
        config_path=path,
        api_key=key.strip() if key else None,
        api_key_source=key_source,
        base_url=normalize_base_url(url),
        base_url_source=url_source,
        site=chosen,
        site_source=site_source,
    )


def normalize_base_url(url: str) -> str:
    """The base URL without a trailing slash, refused unless it is safe to send a key to.

    https anywhere; plain http only to a loopback host (a local dev server), which is the
    rule the Stripe CLI applies to ``--api-base``. A key sent over http to a real host would
    cross the network in clear.
    """
    parts = urlsplit(url.strip())
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ApiError(
            f"base URL {url!r} is not an http(s) URL, e.g. https://eninesites.com"
        )
    if parts.scheme == "http" and parts.hostname not in LOOPBACK:
        raise ApiError(
            f"base URL {url!r} uses http to a non-local host; the API key would travel "
            "unencrypted. Use https, or http://localhost:<port> for a dev server."
        )
    if parts.query or parts.fragment:
        raise ApiError(f"base URL {url!r} must not carry a query or fragment")
    return url.strip().rstrip("/")


def require_key(settings: Settings) -> str:
    """The API key, or the Stripe-style refusal that says how to provide one."""
    if settings.api_key:
        return settings.api_key
    if settings.project_name != config.DEFAULT_PROFILE:
        raise ApiError(
            f'You provided the project name "{settings.project_name}" (either via the '
            f'"--project-name" flag or the "{ENV_PROJECT}" environment variable), but no '
            "API key for that project was found. Run "
            f"`python -m eninesites login --project-name={settings.project_name}`."
        )
    raise ApiError(
        "You have not configured an API key yet. Run `python -m eninesites login`, "
        f"set {ENV_API_KEY}, or pass --api-key <key>."
    )


def require_site(settings: Settings) -> str:
    """The site a site-scoped command acts on, or a refusal naming the three ways to set it."""
    if settings.site:
        return settings.site.strip()
    raise ApiError(
        "No site given. Pass --domain <domain>, set "
        f"{ENV_SITE}, or run `python -m eninesites.site select --domain <domain>`."
    )


def redact(key: str | None) -> str | None:
    """A key as it may be shown: its last four characters, the rest masked.

    Stripe keeps the first eight as well, but those are its public ``sk_test_`` prefix; an
    eninesites key is 40 hex characters with no prefix, so every leading character is secret.
    """
    if not key:
        return None
    if len(key) < 16:
        return "*" * len(key)
    return "*" * (len(key) - 4) + key[-4:]
