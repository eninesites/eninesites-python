"""The REST client library: config file, credential precedence, transport, record shaping.

``lib/client`` is not a CLI node, so its contract is tested here directly. The fake
``server`` fixture (``conftest.py``) replaces the network for every test.
"""

from __future__ import annotations

import json
import os
import stat
from email.message import Message
from pathlib import Path
from urllib import request

import pytest
from conftest import API_KEY, SITE, FakeServer

from eninesites.errors import ApiError
from eninesites.lib.client import config, credentials, http, records


def _settings(**overrides: str | None) -> credentials.Settings:
    return credentials.resolve(**overrides)


# -- config file ------------------------------------------------------------------------


def test_config_path_follows_xdg(tmp_path: Path) -> None:
    assert config.config_path() == tmp_path / "xdg" / "eninesites" / "config.toml"


def test_config_path_falls_back_to_dot_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert (
        config.config_path()
        == tmp_path / "home" / ".config" / "eninesites" / "config.toml"
    )


def test_save_writes_0600_in_a_0700_directory() -> None:
    path = config.save({"default": {"api_key": API_KEY}})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not [p for p in path.parent.iterdir() if p.name.startswith(".config.")]


def test_save_refuses_to_write_through_a_symlink(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.toml"
    target.write_text("", encoding="utf-8")
    path = config.config_path()
    path.parent.mkdir(parents=True)
    path.symlink_to(target)
    with pytest.raises(ApiError, match="symlink"):
        config.save({"default": {"api_key": API_KEY}})
    assert target.read_text() == ""


def test_dumps_and_load_round_trip_awkward_values() -> None:
    profiles = {
        "default": {"api_key": 'a"b\\c\n\td'},
        "my project": {"site": "x.example"},
    }
    config.save(profiles)
    assert config.load() == profiles
    assert config.config_path().read_text().startswith("config_version = 2\n")


def test_load_reads_stripes_v1_layout() -> None:
    path = config.config_path()
    path.parent.mkdir(parents=True)
    path.write_text('[default]\napi_key = "k1"\n', encoding="utf-8")
    assert config.load() == {"default": {"api_key": "k1"}}


def test_load_refuses_a_file_that_is_not_toml() -> None:
    path = config.config_path()
    path.parent.mkdir(parents=True)
    path.write_text("[[[", encoding="utf-8")
    with pytest.raises(ApiError, match="not valid TOML"):
        config.load()


def test_update_profile_removes_an_emptied_profile() -> None:
    config.update_profile("dev", api_key="k")
    config.update_profile("dev", api_key=None)
    assert "dev" not in config.load()


# -- credentials ------------------------------------------------------------------------


def test_flag_beats_env_beats_config_beats_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config.save(
        {"default": {"api_key": "from-config", "base_url": "https://c.example"}}
    )
    monkeypatch.setenv("ENINESITES_BASE_URL", "https://env.example")
    s = _settings(api_key="from-flag")
    assert (s.api_key, s.api_key_source) == ("from-flag", "flag")
    assert (s.base_url, s.base_url_source) == (
        "https://env.example",
        "env ENINESITES_BASE_URL",
    )
    monkeypatch.delenv("ENINESITES_API_KEY")
    monkeypatch.delenv("ENINESITES_BASE_URL")
    s = _settings()
    assert (s.api_key, s.api_key_source) == ("from-config", "config")
    assert s.base_url == "https://c.example"
    config.save({})
    assert _settings().base_url == "https://eninesites.com"
    assert _settings().base_url_source == "default"


def test_project_name_selects_the_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENINESITES_API_KEY")
    monkeypatch.delenv("ENINESITES_SITE")
    config.save(
        {"default": {"api_key": "d"}, "dev": {"api_key": "v", "site": "dev.example"}}
    )
    assert _settings().api_key == "d"
    monkeypatch.setenv("ENINESITES_PROJECT_NAME", "dev")
    s = _settings()
    assert (s.project_name, s.api_key, s.site) == ("dev", "v", "dev.example")
    assert _settings(project_name="default").api_key == "d"


@pytest.mark.parametrize(
    "url",
    [
        "http://eninesites.com",
        "ftp://x.example",
        "eninesites.com",
        "https://x.example/?a=1",
    ],
)
def test_unsafe_or_malformed_base_urls_are_refused(url: str) -> None:
    with pytest.raises(ApiError):
        credentials.normalize_base_url(url)


@pytest.mark.parametrize(
    ("url", "normal"),
    [
        ("https://eninesites.com/", "https://eninesites.com"),
        ("http://localhost:8000", "http://localhost:8000"),
        ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
    ],
)
def test_https_and_loopback_http_are_accepted(url: str, normal: str) -> None:
    assert credentials.normalize_base_url(url) == normal


def test_no_key_says_how_to_provide_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENINESITES_API_KEY")
    with pytest.raises(ApiError, match="You have not configured an API key yet"):
        credentials.require_key(_settings())
    with pytest.raises(ApiError, match='project name "dev"'):
        credentials.require_key(_settings(project_name="dev"))


def test_no_site_names_the_three_ways(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENINESITES_SITE")
    with pytest.raises(ApiError, match="--domain .*ENINESITES_SITE.*site select"):
        credentials.require_site(_settings())


def test_redact_keeps_only_the_last_four() -> None:
    assert credentials.redact(API_KEY) == "*" * 36 + "abcd"
    assert credentials.redact("short") == "*****"
    assert credentials.redact(None) is None


# -- transport --------------------------------------------------------------------------


def test_requests_carry_the_token_and_client_headers(server: FakeServer) -> None:
    client = http.connect()
    client.get(client.site_path("tags"))
    sent = server.last
    assert sent.headers["authorization"] == f"Token {API_KEY}"
    assert sent.headers["user-agent"].startswith("eninesites-python/")
    assert (
        json.loads(sent.headers["x-eninesites-client-user-agent"])["name"]
        == "eninesites-python"
    )
    assert sent.path == f"/api/v1/site/{SITE}/tags/"


def test_path_segments_are_escaped(server: FakeServer) -> None:
    client = http.connect()
    client.get(client.site_path("artifacts", "a/b c"))
    assert server.last.path == f"/api/v1/site/{SITE}/artifacts/a%2Fb%20c/"


def test_problem_details_become_one_api_error(server: FakeServer) -> None:
    problem = {
        "type": "https://api.eninesites.com/errors/validation_error",
        "title": "Bad Request",
        "status": 400,
        "code": "validation_error",
        "detail": "Request body failed validation.",
        "errors": {
            "name": ["This field is required."],
            "colors": {"bg_body": ["Bad hex."]},
        },
    }
    server.add(
        "POST",
        f"/api/v1/site/{SITE}/tags/",
        problem,
        status=400,
        content_type="application/problem+json",
    )
    client = http.connect()
    with pytest.raises(ApiError) as caught:
        client.json("POST", client.site_path("tags"), body={})
    message = str(caught.value)
    assert "HTTP 400 validation_error: Request body failed validation." in message
    assert "name: This field is required." in message
    assert "colors.bg_body: Bad hex." in message
    assert API_KEY not in message


def test_401_says_to_check_the_key(server: FakeServer) -> None:
    server.add("GET", "/api/v1/site/", {"detail": "Invalid token."}, status=401)
    with pytest.raises(ApiError, match="Invalid token.*Check the API key"):
        http.connect().get("/api/v1/site/")


def test_401_message_has_one_full_stop_between_detail_and_advice(
    server: FakeServer,
) -> None:
    server.add("GET", "/api/v1/site/", {"detail": "Invalid token."}, status=401)
    with pytest.raises(ApiError) as caught:
        http.connect().get("/api/v1/site/")
    assert "Invalid token. Check the API key" in str(caught.value)
    assert ".." not in str(caught.value)


def test_an_html_error_page_is_named_not_dumped(server: FakeServer) -> None:
    server.add(
        "GET",
        "/api/v1/site/",
        raw=b"<html>404</html>",
        status=404,
        content_type="text/html",
    )
    with pytest.raises(ApiError, match="an HTML page"):
        http.connect().get("/api/v1/site/")


def test_a_success_that_is_not_json_is_refused(server: FakeServer) -> None:
    server.add("GET", "/api/v1/site/", raw=b"not json", content_type="text/plain")
    with pytest.raises(ApiError, match="not JSON"):
        http.connect().get("/api/v1/site/")


def test_redirects_are_refused_so_the_key_is_not_forwarded() -> None:
    handler = http._NoRedirect()  # pylint: disable=protected-access
    req = request.Request("https://eninesites.com/api/v1/site/")
    with pytest.raises(ApiError, match="not followed"):
        handler.redirect_request(
            req, None, 301, "Moved", Message(), "https://evil.example/"
        )


def test_list_all_follows_pages_until_next_is_null(server: FakeServer) -> None:
    path = f"/api/v1/site/{SITE}/tags/"
    server.add(
        "GET", path, {"count": 3, "next": "p2", "results": [{"id": 1}, {"id": 2}]}
    )
    server.add("GET", path, {"count": 3, "next": None, "results": [{"id": 3}]})
    client = http.connect()
    assert client.list_all(client.site_path("tags")) == [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]
    assert [c.query["page"] for c in server.calls] == [["1"], ["2"]]
    assert server.calls[0].query["page_size"] == ["200"]


def test_list_all_accepts_a_bare_array(server: FakeServer) -> None:
    server.add("GET", "/api/v1/site/", [{"domain": "a"}])
    assert http.connect().list_all("/api/v1/site/") == [{"domain": "a"}]


def test_uploads_are_multipart_with_one_file_part_each(server: FakeServer) -> None:
    client = http.connect()
    client.request("POST", client.site_path("media"), files=[Path("logo.png")])
    sent = server.last
    assert sent.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert sent.body is not None
    assert b'name="file"; filename="logo.png"' in sent.body
    assert b"Content-Type: image/png" in sent.body


def test_without_a_key_nothing_is_sent(
    monkeypatch: pytest.MonkeyPatch, server: FakeServer
) -> None:
    monkeypatch.delenv("ENINESITES_API_KEY")
    with pytest.raises(ApiError, match="API key"):
        http.connect()
    assert not server.calls


# -- records ----------------------------------------------------------------------------


def test_project_keeps_only_declared_keys_recursively() -> None:
    from eninesites.artifact.lib.results import (  # pylint: disable=import-outside-toplevel
        ArtifactRow,
    )

    raw = {
        "id": 1,
        "name": "a",
        "secret_new_field": 1,
        "children": [{"id": 2, "extra": 1}],
    }
    assert records.project(raw, ArtifactRow) == {
        "id": 1,
        "name": "a",
        "children": [{"id": 2}],
    }
    assert records.project("not a dict", ArtifactRow) == {}


def test_request_body_reads_a_json_file_or_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io  # pylint: disable=import-outside-toplevel

    Path("body.json").write_text('{"a": 1}', encoding="utf-8")
    assert records.request_body(Path("body.json")) == {"a": 1}
    assert records.request_body(None) == {}
    monkeypatch.setattr("sys.stdin", io.StringIO('{"b": 2}'))
    assert records.request_body(Path("-")) == {"b": 2}
    Path("bad.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(ApiError, match="not valid JSON"):
        records.request_body(Path("bad.json"))
    Path("list.json").write_text("[1]", encoding="utf-8")
    with pytest.raises(ApiError, match="JSON object"):
        records.request_body(Path("list.json"))
    with pytest.raises(ApiError, match="cannot read"):
        records.request_body(Path("missing.json"))


def test_merged_lays_flags_over_data() -> None:
    Path("body.json").write_text('{"a": 1, "b": 2}', encoding="utf-8")
    assert records.merged(Path("body.json"), b=3, c=None) == {"a": 1, "b": 3}


@pytest.mark.parametrize(
    ("text", "value"), [("true", True), ("No", False), ("1", True)]
)
def test_boolean_flags(text: str, value: bool) -> None:
    assert records.boolean(text, "--published") is value


def test_boolean_refuses_anything_else() -> None:
    with pytest.raises(ApiError, match="--published"):
        records.boolean("maybe", "--published")


def test_config_file_is_never_world_readable_even_with_a_loose_umask() -> None:
    old = os.umask(0)
    try:
        path = config.save({"default": {"api_key": API_KEY}})
    finally:
        os.umask(old)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
