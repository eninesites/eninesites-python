"""The page noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only page knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.errors import ApiError
from eninesites.page import __main__ as cli
from eninesites.page import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "crawl": {},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set(api.NOT_OVER_REST)

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_page_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_page_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


def test_page_sends_nothing(server: FakeServer) -> None:
    for verb, fn in api.VERBS.items():
        with pytest.raises(ApiError):
            fn(**SAMPLES[verb])
    assert not server.calls


def test_page_verbs_without_an_endpoint_are_the_documented_ones() -> None:
    # Pinned independently of the api: the server's URL conf has no route for these.
    assert api.NOT_OVER_REST == frozenset({"crawl"})
