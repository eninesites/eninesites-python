"""The artifact role api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server route: ``/api/v1/site/<d>/artifacts/<slug>/roles/`` (``ArtifactRoleView``,
``resources.py:176-253``): GET lists, PUT replaces, POST adds one. The server has no route
to remove one role (its own docstring, ``resources.py:190-191``), so ``unassign`` is a GET
followed by a PUT of the remaining roles: two real endpoints, and not atomic, so a
concurrent change between the two calls can be lost.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from eninesites.lib.client import credentials
from eninesites.lib.client.http import Client, connect
from eninesites.lib.client.records import required

from .lib.results import AssignRole, ListRole, ReplaceRole, Roles, UnassignRole

SLUG = "the artifact's name or slug"


def _roles(client: Client, slug: str, payload: Any) -> Roles:
    codes = payload.get("roles", []) if isinstance(payload, dict) else []
    return {
        "domain": credentials.require_site(client.settings),
        "slug": slug,
        "roles": [str(c) for c in codes],
    }


def list_role(
    *,
    slug: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListRole:
    """The artifact's role codes: ``GET .../roles/``."""
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    return _roles(
        client, target, client.get(client.site_path("artifacts", target, "roles"))
    )


def replace_role(
    *,
    slug: str | None = None,
    role: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ReplaceRole:
    """Replace every role with ``--role`` (comma-separated; ``""`` clears): ``PUT .../roles/``."""
    codes = [c.strip() for c in (role or "").split(",") if c.strip()]
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    path = client.site_path("artifacts", target, "roles")
    return _roles(client, target, client.json("PUT", path, body={"roles": codes}))


def assign_role(
    *,
    slug: str | None = None,
    role: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> AssignRole:
    """Add one role (idempotent): ``POST .../roles/`` with ``{"role": <code>}``."""
    code = required(
        role,
        "--role",
        "a role code: article, faq, org, person, place, product, review or service",
    )
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    path = client.site_path("artifacts", target, "roles")
    return _roles(client, target, client.json("POST", path, body={"role": code}))


def unassign_role(
    *,
    slug: str | None = None,
    role: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> UnassignRole:
    """Remove one role: GET the codes, then PUT them back without it (no-op if absent)."""
    code = required(
        role,
        "--role",
        "a role code: article, faq, org, person, place, product, review or service",
    )
    client = connect(api_key, base_url, project_name, domain)
    target = required(slug, "--slug", SLUG)
    path = client.site_path("artifacts", target, "roles")
    current = _roles(client, target, client.get(path))
    if code not in current["roles"]:
        return current
    remaining = [c for c in current["roles"] if c != code]
    return _roles(client, target, client.json("PUT", path, body={"roles": remaining}))


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_role,
    "replace": replace_role,
    "assign": assign_role,
    "unassign": unassign_role,
}
