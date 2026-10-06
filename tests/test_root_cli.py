"""The eninesites root noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only eninesites knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import pytest
from conftest import API_KEY, FakeServer

from eninesites import __main__ as cli
from eninesites.lib import dryrun
from eninesites.root import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "login": {"api_key": API_KEY},
    "logout": {},
    "config": {},
    "describe": {},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set()

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "login": ("GET", "/api/v1/site/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_root_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_root_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_root_verbs_send_the_documented_request(verb: str, server: FakeServer) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


# -- login / logout / config ------------------------------------------------------------


def _main() -> Callable[[list[str] | None], int]:
    return cli.main


def test_login_checks_the_key_before_storing_it(server: FakeServer) -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel
    from eninesites.lib.client import config  # pylint: disable=import-outside-toplevel

    server.add("GET", "/api/v1/site/", {"detail": "Invalid token."}, status=401)
    with pytest.raises(ApiError, match="401"):
        api.login_root(api_key="bad-key-0000000000000000")
    assert not config.config_path().exists()


def test_login_stores_the_key_0600_and_prints_it_redacted(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    import stat  # pylint: disable=import-outside-toplevel

    from eninesites.lib.client import config  # pylint: disable=import-outside-toplevel

    server.add("GET", "/api/v1/site/", [{"domain": "a.example", "name": "A"}])
    code, out, err = run_cli(_main(), ["login", "--api-key", API_KEY])
    assert (code, err) == (0, "")
    assert API_KEY not in out
    assert API_KEY[-4:] in out and "1 site(s)" in out
    assert config.load()["default"]["api_key"] == API_KEY
    assert stat.S_IMODE(config.config_path().stat().st_mode) == 0o600
    assert server.last.headers["authorization"] == f"Token {API_KEY}"


def test_login_reads_the_key_from_stdin_when_not_a_terminal(
    monkeypatch: pytest.MonkeyPatch, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    import io  # pylint: disable=import-outside-toplevel

    from eninesites.lib.client import config  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr("sys.stdin", io.StringIO("piped-key-0000000000000000\n"))
    code, _, _ = run_cli(_main(), ["login", "--project-name", "ci"])
    assert code == 0
    assert config.load()["ci"]["api_key"] == "piped-key-0000000000000000"


def test_login_with_nothing_to_read_refuses(
    monkeypatch: pytest.MonkeyPatch, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    import io  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    code, out, err = run_cli(_main(), ["login"])
    assert (code, out) == (2, "")
    assert "no API key given" in err


def test_login_keeps_a_dev_base_url_with_the_key(server: FakeServer) -> None:
    from eninesites.lib.client import config  # pylint: disable=import-outside-toplevel

    result = dryrun.done(
        api.login_root(
            api_key=API_KEY, base_url="http://localhost:8000", project_name="dev"
        )
    )
    assert result["base_url"] == "http://localhost:8000"
    assert config.load()["dev"] == {
        "api_key": API_KEY,
        "base_url": "http://localhost:8000",
    }
    assert server.calls


def test_logout_clears_the_key_and_keeps_the_rest(
    run_cli: Callable[..., tuple[int, str, str]],
) -> None:
    from eninesites.lib.client import config  # pylint: disable=import-outside-toplevel

    config.save(
        {"default": {"api_key": "k" * 40, "site": "a.example"}, "dev": {"api_key": "d"}}
    )
    code, out, _ = run_cli(_main(), ["logout"])
    assert code == 0 and "cleared for the default project" in out
    assert "ENINESITES_API_KEY is still set" in out
    assert config.load() == {"default": {"site": "a.example"}, "dev": {"api_key": "d"}}
    code, out, _ = run_cli(_main(), ["logout"])
    assert "You are already logged out." in out
    run_cli(_main(), ["logout", "--all"])
    assert config.load() == {"default": {"site": "a.example"}}


def test_config_reports_each_setting_with_its_source_and_never_the_key(
    run_cli: Callable[..., tuple[int, str, str]],
) -> None:
    code, out, _ = run_cli(_main(), ["config", "--json"])
    assert code == 0
    shown = json.loads(out)
    assert shown["api_key"] == "*" * 36 + API_KEY[-4:]
    assert shown["api_key_source"] == "env ENINESITES_API_KEY"
    assert shown["base_url"] == "https://eninesites.com"
    assert shown["site_source"] == "env ENINESITES_SITE"
    assert API_KEY not in out
    _, text_out, _ = run_cli(_main(), ["config"])
    assert API_KEY not in text_out and "[env ENINESITES_API_KEY]" in text_out
