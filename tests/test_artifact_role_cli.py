"""The artifact role noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only artifact role knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.artifact.role import __main__ as cli
from eninesites.artifact.role import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "list": {"slug": "services"},
    "replace": {"slug": "services", "role": "what,who"},
    "assign": {"slug": "services", "role": "what"},
    "unassign": {"slug": "services", "role": "what"},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "list": ("GET", "/api/v1/site/example.com/artifacts/services/roles/"),
    "replace": ("PUT", "/api/v1/site/example.com/artifacts/services/roles/"),
    "assign": ("POST", "/api/v1/site/example.com/artifacts/services/roles/"),
    "unassign": ("GET", "/api/v1/site/example.com/artifacts/services/roles/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_artifact_role_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_artifact_role_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_artifact_role_verbs_send_the_documented_request(
    verb: str, server: FakeServer
) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


def test_unassign_puts_back_the_other_roles(server: FakeServer) -> None:
    path = "/api/v1/site/example.com/artifacts/services/roles/"
    server.add("GET", path, {"roles": ["what", "who"]})
    server.add("PUT", path, {"roles": ["who"]})
    assert api.unassign_role(slug="services", role="what")["roles"] == ["who"]
    assert [c.method for c in server.calls] == ["GET", "PUT"]
    assert server.last.json() == {"roles": ["who"]}


def test_unassigning_an_absent_role_writes_nothing(server: FakeServer) -> None:
    server.add(
        "GET", "/api/v1/site/example.com/artifacts/services/roles/", {"roles": ["who"]}
    )
    assert api.unassign_role(slug="services", role="what")["roles"] == ["who"]
    assert [c.method for c in server.calls] == ["GET"]


def test_replace_with_an_empty_role_clears(server: FakeServer) -> None:
    api.replace_role(slug="services", role="")
    assert server.last.json() == {"roles": []}
