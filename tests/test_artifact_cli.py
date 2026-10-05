"""The artifact noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only artifact knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.artifact import __main__ as cli
from eninesites.artifact import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "list": {},
    "get": {"slug": "services"},
    "create": {"name": "services", "title": "Services", "published": "true"},
    "update": {"slug": "services", "title": "New"},
    "delete": {"slug": "services"},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "list": ("GET", "/api/v1/site/example.com/artifacts/"),
    "get": ("GET", "/api/v1/site/example.com/artifacts/services/"),
    "create": ("POST", "/api/v1/site/example.com/artifacts/"),
    "update": ("POST", "/api/v1/site/example.com/artifacts/services/"),
    "delete": ("DELETE", "/api/v1/site/example.com/artifacts/services/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_artifact_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_artifact_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_artifact_verbs_send_the_documented_request(
    verb: str, server: FakeServer
) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


# -- artifact specifics -----------------------------------------------------------------


def test_create_maps_flags_onto_the_servers_field_names(server: FakeServer) -> None:
    api.create_artifact(
        name="faq", pnode="services", published="no", data=Path("navbar.json")
    )
    assert server.last.json() == {
        "navbar": True,
        "name": "faq",
        "parent": "services",
        "is_published": False,
    }


def test_list_walks_every_page_and_keeps_declared_fields(server: FakeServer) -> None:
    path = "/api/v1/site/example.com/artifacts/"
    server.add(
        "GET", path, {"next": "x", "results": [{"id": 1, "name": "a", "zzz": 1}]}
    )
    server.add("GET", path, {"next": None, "results": [{"id": 2, "name": "b"}]})
    result = api.list_artifact()
    assert result == {
        "count": 2,
        "results": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
    }


def test_a_404_reaches_the_terminal_as_one_line_and_exit_2(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    server.add(
        "GET",
        "/api/v1/site/example.com/artifacts/nope/",
        {
            "code": "not_found",
            "detail": "No Artifact matches the given query.",
            "status": 404,
        },
        status=404,
        content_type="application/problem+json",
    )
    code, out, err = run_cli(cli.main, ["get", "--slug", "nope"])
    assert (code, out) == (2, "")
    assert "HTTP 404 not_found: No Artifact matches the given query." in err


def test_update_with_nothing_to_change_sends_nothing(server: FakeServer) -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel

    with pytest.raises(ApiError, match="nothing to update"):
        api.update_artifact(slug="services")
    assert not server.calls


def test_the_cli_reads_data_from_a_file(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    code, _, err = run_cli(
        cli.main, ["update", "--slug", "services", "--data", "navbar.json"]
    )
    assert (code, err) == (0, "")
    assert server.last.json() == {"navbar": True}
