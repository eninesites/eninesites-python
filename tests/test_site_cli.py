"""The site noun: each verb sends its documented request and returns its declared type.

What every node shares (bare invocation, argument errors) is tested once, over all nodes,
in ``test_cli.py``. This file holds what only site knows. The API is the fake ``server``
fixture in ``conftest.py``; nothing here reaches a real host.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import FakeServer

from eninesites.lib import dryrun
from eninesites.site import __main__ as cli
from eninesites.site import api

# One real call per verb, for the test that checks each result against its type.
SAMPLES: dict[str, dict[str, Any]] = {
    "create": {
        "name": "Acme",
        "domain": "acme.example",
        "theme": "bauhaus",
        "plan": Path("free"),
    },
    "list": {},
    "dump": {"format_": "yaml"},
    "load": {"path": Path("site.json")},
    "restore": {"path": Path("site.zip"), "mode": "replace"},
    "copy": {"to": "copy.example", "plan": Path("free")},
    "configure": {"title": "Acme", "colors_primary": "#112233"},
    "delete": {},
    "check": {},
    "review": {},
    "select": {"domain": "other.example"},
    "randomize-subdomain": {},
    "propose": {},
    "build": {},
}

# Verbs with no REST endpoint: they refuse instead of returning.
UNAVAILABLE: set[str] = set(api.NOT_OVER_REST)

# The request each verb's sample sends (method, path), from the server's URL conf.
ROUTES: dict[str, tuple[str, str]] = {
    "create": ("POST", "/api/v1/site/"),
    "list": ("GET", "/api/v1/site/"),
    "dump": ("GET", "/api/v1/site/example.com/"),
    "load": ("POST", "/api/v1/site/example.com/"),
    "restore": ("POST", "/api/v1/site/example.com/"),
    "copy": ("POST", "/api/v1/site/example.com/copy/"),
    "configure": ("POST", "/api/v1/site/example.com/configure/"),
    "randomize-subdomain": ("POST", "/api/v1/site/example.com/random-subdomain/"),
}


@pytest.mark.parametrize("verb", sorted(api.VERBS))
def test_site_verbs_return_the_type_they_declare(
    verb: str, returns_declared: Callable[..., None]
) -> None:
    returns_declared(api.VERBS[verb], SAMPLES[verb], verb in UNAVAILABLE)


def test_site_output_publishes_one_schema_per_verb() -> None:
    phases = sorted(str(params["phase"]) for params, _ in cli.output())
    assert phases == sorted(api.VERBS)


@pytest.mark.parametrize("verb", sorted(ROUTES))
def test_site_verbs_send_the_documented_request(verb: str, server: FakeServer) -> None:
    api.VERBS[verb](**SAMPLES[verb])
    method, path = ROUTES[verb]
    sent = server.calls[0]
    assert (sent.method, sent.path) == (method, path)


# -- site specifics ---------------------------------------------------------------------


def test_create_sends_the_theme_as_config_and_refuses_a_user(
    server: FakeServer,
) -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel

    server.add("POST", "/api/v1/site/", {"domain": "acme.example"}, status=201)
    assert api.create_site(**SAMPLES["create"]) == {"domain": "acme.example"}
    assert server.last.json() == {
        "domain": "acme.example",
        "name": "Acme",
        "plan": "free",
        "config": {"theme": {"name": "bauhaus", "path": "bauhaus/templates"}},
    }
    with pytest.raises(ApiError, match="--user not accepted"):
        api.create_site(name="x", user="a@b.example")


def test_dump_saves_under_the_servers_file_name(server: FakeServer) -> None:
    server.add(
        "GET",
        "/api/v1/site/example.com/",
        raw=b"domain: example.com\n",
        content_type="application/x-yaml",
        headers={"content-disposition": 'attachment; filename="example.com.yaml"'},
    )
    result = api.dump_site(format_="yaml")
    assert result == {
        "domain": "example.com",
        "format": "yaml",
        "path": "example.com.yaml",
        "bytes": 20,
    }
    assert Path("example.com.yaml").read_bytes() == b"domain: example.com\n"
    assert server.last.query == {"dl": ["yaml"]}


def test_dump_refuses_an_unknown_format() -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel

    with pytest.raises(ApiError, match="--format"):
        api.dump_site(format_="xml")


def test_load_sends_the_file_and_points_a_zip_at_restore(server: FakeServer) -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel

    api.load_site(path=Path("site.json"))
    assert server.last.body is not None and b'filename="site.json"' in server.last.body
    with pytest.raises(ApiError, match="site restore"):
        api.load_site(path=Path("site.zip"))


def test_restore_sends_the_mode_and_the_archive(server: FakeServer) -> None:
    result = dryrun.done(api.restore_site(path=Path("site.zip"), mode="replace"))
    assert result["mode"] == "replace"
    assert server.last.query == {"mode": ["replace"]}
    assert server.last.body is not None and b'filename="site.zip"' in server.last.body


def test_configure_nests_flags_over_the_file(server: FakeServer) -> None:
    server.add(
        "POST", "/api/v1/site/example.com/configure/", {"updated": ["theme", "config"]}
    )
    result = api.configure_site(
        path=Path("config.json"), title="Acme", colors_body="#ffffff"
    )
    assert server.last.json() == {
        "theme": "bauhaus",
        "config": {"title": "Acme"},
        "colors": {"bg_body": "#ffffff"},
    }
    assert result == {"domain": "example.com", "updated": ["theme", "config"]}


def test_select_checks_the_site_then_stores_it_for_later_commands(
    monkeypatch: pytest.MonkeyPatch, server: FakeServer
) -> None:
    monkeypatch.delenv("ENINESITES_SITE")
    api.select_site(domain=" Chosen.Example ")
    assert (server.last.method, server.last.path) == (
        "GET",
        "/api/v1/site/chosen.example/configure/",
    )
    api.randomize_subdomain_site()
    assert server.last.path == "/api/v1/site/chosen.example/random-subdomain/"


@pytest.mark.parametrize(
    ("status", "detail"),
    [(404, "Not found."), (403, "You don't have access to this site.")],
)
def test_select_refuses_a_site_the_server_rejects_and_saves_nothing(
    monkeypatch: pytest.MonkeyPatch, server: FakeServer, status: int, detail: str
) -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel
    from eninesites.lib.client import config  # pylint: disable=import-outside-toplevel

    monkeypatch.delenv("ENINESITES_SITE")
    server.add(
        "GET",
        "/api/v1/site/typo.example/configure/",
        {"detail": detail},
        status=status,
    )
    before = config.load()
    with pytest.raises(ApiError, match="typo.example was not saved"):
        api.select_site(domain="typo.example")
    assert config.load() == before


def test_copy_needs_a_destination() -> None:
    from eninesites.errors import ApiError  # pylint: disable=import-outside-toplevel

    with pytest.raises(ApiError, match="--to"):
        api.copy_site()


def test_site_verbs_without_an_endpoint_are_the_documented_ones() -> None:
    # Pinned independently of the api: the server's URL conf has no route for these.
    assert api.NOT_OVER_REST == frozenset(
        {"delete", "check", "review", "propose", "build"}
    )


def test_the_cli_sends_the_path_and_has_no_file_switch(
    server: FakeServer, run_cli: Callable[..., tuple[int, str, str]]
) -> None:
    code, _, err = run_cli(cli.main, ["load", "--path", "site.json", "--json"])
    assert (code, err) == (0, "")
    assert server.last.body is not None and b'filename="site.json"' in server.last.body
    code, out, err = run_cli(cli.main, ["load", "--file"])
    assert (code, out) == (2, "")
    assert "unrecognized arguments: --file" in err
