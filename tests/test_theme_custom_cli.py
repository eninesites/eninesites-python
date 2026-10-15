"""The theme custom noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only theme custom knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.lib import dryrun
from eninesites.theme.custom import __main__ as cli
from eninesites.theme.custom import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "export": {"name": "mine"},
    "import": {"path": Path("theme.json")},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "export": ("GET", "/api/v1/site/example.com/custom-themes/"),
    "import": ("POST", "/api/v1/site/example.com/custom-themes/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_theme_custom_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_theme_custom_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_theme_custom_verbs_send_the_documented_request(
    verb: str, server: FakeServer
) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


def test_import_takes_back_an_export(server: FakeServer) -> None:
    server.add(
        "POST",
        "/api/v1/site/example.com/custom-themes/",
        {"name": "mine", "theme": "c-1", "active": True, "previous_theme": "bauhaus"},
    )
    result = api.import_custom(path=Path("theme.json"), parent="bauhaus")
    assert server.last.json() == {
        "custom_theme": {
            "name": "mine",
            "parent": "bauhaus",
            "templates": {"home.html": "<h1>hi</h1>"},
        }
    }
    assert result == {
        "domain": "example.com",
        "name": "mine",
        "theme": "c-1",
        "active": True,
        "previous_theme": "bauhaus",
    }


def test_import_sends_activate_only_when_given(server: FakeServer) -> None:
    server.add(
        "POST",
        "/api/v1/site/example.com/custom-themes/",
        {"name": "mine", "theme": "c-1", "active": False, "previous_theme": "bauhaus"},
    )
    result = dryrun.done(
        api.import_custom(path=Path("theme.json"), parent="bauhaus", activate="no")
    )
    assert server.last.json()["activate"] is False
    assert (result["active"], result["previous_theme"]) == (False, "bauhaus")


def test_import_refuses_an_activate_that_is_not_yes_or_no() -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel

    with pytest.raises(ApiError, match="--activate"):
        api.import_custom(path=Path("theme.json"), parent="bauhaus", activate="maybe")


def test_import_says_whether_the_theme_went_live(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    path = "/api/v1/site/example.com/custom-themes/"
    server.add("POST", path, {"theme": "c-1", "active": False, "previous_theme": None})
    argv = ["import", "--path", "theme.json", "--parent", "bauhaus"]
    code, out, _ = run_cli(cli.main, [*argv, "--activate", "false"])
    assert code == 0 and "Live theme unchanged: none" in out
