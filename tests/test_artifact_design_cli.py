"""The artifact design noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only artifact design knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.artifact.design import __main__ as cli
from eninesites.artifact.design import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "get": {"slug": "services"},
    "update": {"slug": "services", "data": Path("design.json")},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "get": ("GET", "/api/v1/site/example.com/artifacts/services/design/"),
    "update": ("POST", "/api/v1/site/example.com/artifacts/services/design/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_artifact_design_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_artifact_design_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_artifact_design_verbs_send_the_documented_request(
    verb: str, server: FakeServer
) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)
