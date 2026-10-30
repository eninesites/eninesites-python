"""The plan noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only plan knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.plan import __main__ as cli
from eninesites.plan import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "list": {},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "list": ("GET", "/api/v1/plans/"),
}

PLANS = [
    {
        "slug": "free",
        "name": "Free",
        "description": "",
        "price": "0.00",
        "max_sites": 1,
    },
    {
        "slug": "enine",
        "name": "Enine",
        "description": "Every feature",
        "price": "49.00",
        "max_sites": None,
    },
]


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_plan_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_plan_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_plan_verbs_send_the_documented_request(verb: str, server: FakeServer) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


def test_list_keeps_the_servers_order_and_fields(server: FakeServer) -> None:
    server.add("GET", "/api/v1/plans/", PLANS)
    assert api.list_plan() == {"count": 2, "results": PLANS}


def test_list_shows_a_null_max_sites_as_unlimited(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    server.add("GET", "/api/v1/plans/", PLANS)
    code, out, _ = run_cli(cli.main, ["list"])
    assert code == 0
    assert "unlimited" in out.splitlines()[-1]
    assert "Every feature" not in out


def test_list_with_no_plan_says_none(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    server.add("GET", "/api/v1/plans/", [])
    code, out, _ = run_cli(cli.main, ["list"])
    assert (code, out.strip()) == (0, "(none)")
