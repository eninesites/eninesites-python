"""The user noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only user knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.errors import ApiError
from eninesites.lib import dryrun
from eninesites.user import __main__ as cli
from eninesites.user import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "list": {},
    "add": {"username": "jo", "role": "editor"},
    "get": {"username": "jo"},
    "update": {"username": "jo", "role": "reader"},
    "remove": {"username": "jo"},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "list": ("GET", "/api/v1/site/example.com/users/"),
    "add": ("POST", "/api/v1/site/example.com/users/"),
    "get": ("GET", "/api/v1/site/example.com/users/jo/"),
    "update": ("POST", "/api/v1/site/example.com/users/jo/"),
    "remove": ("DELETE", "/api/v1/site/example.com/users/jo/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_user_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_user_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_user_verbs_send_the_documented_request(verb: str, server: FakeServer) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


def test_remove_reports_the_member_it_removed(server: FakeServer) -> None:
    server.add("DELETE", "/api/v1/site/example.com/users/jo/", None, status=204)
    assert dryrun.done(api.remove_user(username="jo")) == {
        "domain": "example.com",
        "username": "jo",
        "removed": True,
    }


def test_remove_passes_the_last_admin_refusal_through(server: FakeServer) -> None:
    server.add(
        "DELETE",
        "/api/v1/site/example.com/users/jo/",
        {
            "type": "about:blank",
            "status": 409,
            "code": "last_admin",
            "detail": "A site must keep at least one admin.",
        },
        status=409,
        content_type="application/problem+json",
    )
    with pytest.raises(ApiError, match="at least one admin"):
        api.remove_user(username="jo")
