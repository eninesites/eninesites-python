"""The user api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

Server routes (``resources.py:756-827``): ``/api/v1/site/<d>/users/`` (GET paginated, POST
``{username, role}``) and ``.../users/<username>/`` (GET, POST ``{role}``). Adding and
changing members needs the site's admin role. The server adds only users that already
exist; it does not create accounts.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client.http import connect
from eninesites.lib.client.records import project, required, rows

from .lib.results import AddUser, GetUser, ListUser, UpdateUser, UserRow

USERNAME = "the user's username"
ROLE = "admin, editor or reader"


def list_user(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListUser:
    """The site's members: ``GET .../users/`` (all pages)."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.list_all(client.site_path("users")), UserRow)
    return {"count": len(found), "results": found}


def add_user(
    *,
    username: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    role: str | None = None,
) -> AddUser:
    """Make an existing user a member with ``--role``: ``POST .../users/``."""
    body = {
        "username": required(username, "--username", USERNAME),
        "role": required(role, "--role", ROLE),
    }
    client = connect(api_key, base_url, project_name, domain)
    result: AddUser = project(
        client.json("POST", client.site_path("users"), body=body), AddUser
    )
    return result


def get_user(
    *,
    username: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> GetUser:
    """One membership: ``GET .../users/<username>/``."""
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("users", required(username, "--username", USERNAME))
    result: GetUser = project(client.get(path), GetUser)
    return result


def update_user(
    *,
    username: str | None = None,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    role: str | None = None,
) -> UpdateUser:
    """Change a member's role: ``POST .../users/<username>/`` with ``{"role": ...}``."""
    body = {"role": required(role, "--role", ROLE)}
    client = connect(api_key, base_url, project_name, domain)
    path = client.site_path("users", required(username, "--username", USERNAME))
    result: UpdateUser = project(client.json("POST", path, body=body), UpdateUser)
    return result


# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "list": list_user,
    "add": add_user,
    "get": get_user,
    "update": update_user,
}
