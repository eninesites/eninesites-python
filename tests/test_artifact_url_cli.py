"""The artifact url noun: each verb sends its documented request and returns its type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only artifact url knows. The API is the fake
``server`` fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.artifact.url import __main__ as cli
from eninesites.artifact.url import api
from eninesites.errors import ApiError
from eninesites.lib import dryrun

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "list": {"slug": "services"},
    "attach": {"slug": "services", "name": "docs"},
    "get": {"slug": "services", "id_": "5"},
    "update": {"slug": "services", "id_": "5", "data": Path("order.json")},
    "detach": {"slug": "services", "id_": "5"},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

BASE = "/api/v1/site/example.com/artifacts/services/urls/"

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "list": ("GET", BASE),
    "attach": ("POST", BASE),
    "get": ("GET", f"{BASE}5/"),
    "update": ("PATCH", f"{BASE}5/"),
    "detach": ("DELETE", f"{BASE}5/"),
}

ROW = {
    "id": 5,
    "external_url": 9,
    "name": "docs",
    "label": "Docs",
    "href": "https://docs.example/",
    "order": 0,
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_artifact_url_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_artifact_url_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_artifact_url_verbs_send_the_documented_request(
    verb: str, server: FakeServer
) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


def test_attach_sends_the_saved_urls_name_and_no_order_by_default(
    server: FakeServer,
) -> None:
    server.add("POST", BASE, ROW, status=201)
    assert dryrun.done(api.attach_url(slug="services", name="docs")) == ROW
    assert server.last.json() == {"external_url": "docs"}


def test_attach_places_the_url_with_order(server: FakeServer) -> None:
    api.attach_url(slug="services", name="docs", order="2")
    assert server.last.json() == {"external_url": "docs", "order": 2}
    with pytest.raises(ApiError, match="--order"):
        api.attach_url(slug="services", name="docs", order="first")


def test_attach_passes_the_servers_refusal_of_a_duplicate_through(
    server: FakeServer,
) -> None:
    server.add(
        "POST",
        BASE,
        {
            "type": "about:blank",
            "status": 400,
            "code": "validation_error",
            "detail": "The fields artifact, external_url must make a unique set.",
        },
        status=400,
        content_type="application/problem+json",
    )
    with pytest.raises(ApiError, match="unique"):
        api.attach_url(slug="services", name="docs")


def test_update_sends_the_data_as_a_patch_and_needs_some(server: FakeServer) -> None:
    api.update_url(slug="services", id_="5", data=Path("order.json"))
    assert (server.last.method, server.last.json()) == ("PATCH", {"order": 2})
    with pytest.raises(ApiError, match="--data is required"):
        api.update_url(slug="services", id_="5")


def test_detach_reports_the_row_it_removed(server: FakeServer) -> None:
    server.add("DELETE", f"{BASE}5/", None, status=204)
    assert dryrun.done(api.detach_url(slug="services", id_="5")) == {
        "domain": "example.com",
        "slug": "services",
        "id": "5",
        "detached": True,
    }


def test_list_shows_each_url_in_order(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    server.add("GET", BASE, {"next": None, "results": [ROW]})
    code, out, _ = run_cli(cli.main, ["list", "--slug", "services"])
    assert code == 0 and "https://docs.example/" in out
