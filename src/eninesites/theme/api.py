"""The theme api: the one place a request becomes a decision.

Every surface (this noun's cli, an MCP tool, a REST route) calls these functions and
nothing below them. Each verb is one function returning one result type from
``lib.results``, plain JSON. A request the api cannot run raises ``ApiError``.

``theme list`` is ``GET /api/v1/site/<d>/themes/`` (a bare array). Creating, deleting,
checking and reviewing themes exist only as the server's ``manage.py theme`` command
(``services/manager/management/commands/theme.py``), so those verbs refuse.
"""

# A verb's signature is its lexicon params, one keyword per flag, so the count is the
# lexicon's to decide; pylint's argument cap does not apply to these functions.
# pylint: disable=too-many-arguments

from __future__ import annotations

from collections.abc import Callable

from eninesites.lib.client import credentials
from eninesites.lib.client.http import connect
from eninesites.lib.client.records import not_over_rest, rows

from .lib.results import (
    CheckTheme,
    CreateTheme,
    DeleteTheme,
    ListTheme,
    ReviewTheme,
    ThemeRow,
)


def create_theme(*, name: str | None = None) -> CreateTheme:
    """Refuse: scaffolding a theme is ``manage.py theme --create``."""
    del name
    raise not_over_rest("theme create", "it exists only as `manage.py theme --create`")


def list_theme(
    *,
    domain: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
) -> ListTheme:
    """The themes the site may select: ``GET /api/v1/site/<d>/themes/``."""
    client = connect(api_key, base_url, project_name, domain)
    found = rows(client.get(client.site_path("themes")), ThemeRow)
    return {
        "domain": credentials.require_site(client.settings),
        "count": len(found),
        "results": found,
    }


def delete_theme(*, name: str | None = None, force: bool = False) -> DeleteTheme:
    """Refuse: deleting a theme is ``manage.py theme --delete``."""
    del name, force
    raise not_over_rest("theme delete", "it exists only as `manage.py theme --delete`")


def check_theme(*, name: str | None = None, apply: bool = False) -> CheckTheme:
    """Refuse: linting a theme is ``manage.py theme --check``."""
    del name, apply
    raise not_over_rest("theme check", "it exists only as `manage.py theme --check`")


def review_theme(*, name: str | None = None) -> ReviewTheme:
    """Refuse: a theme overview is ``manage.py theme --review``."""
    del name
    raise not_over_rest("theme review", "it exists only as `manage.py theme --review`")


# The verbs the eninesites REST API has no endpoint for: each raises `ApiError` saying
# where the operation lives instead. Read mechanically by the tests, one home.
NOT_OVER_REST: frozenset[str] = frozenset({"create", "delete", "check", "review"})

# CLI spelling -> the function it binds. A verb spelled like a keyword or a builtin
# (`import`, `list`) is a key here rather than a function name; the lexicon reads this
# literal to find each verb.
VERBS: dict[str, Callable[..., object]] = {
    "create": create_theme,
    "list": list_theme,
    "delete": delete_theme,
    "check": check_theme,
    "review": review_theme,
}
