"""A refusal under ``--json`` is data: one JSON document on stderr, never a sentence.

The server sends RFC 9457 problem details (``code``, ``detail``, ``errors``); the client
keeps them as fields of ``ApiError`` and, under ``--json``, prints ``ApiError.record()``.
Without ``--json`` the text is what it always was.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib import error, request

import pytest
from conftest import FakeServer

import eninesites.artifact.__main__ as artifact
import eninesites.site.__main__ as site
from eninesites.errors import ApiError
from eninesites.lib.client import http

Run = Callable[..., tuple[int, str, str]]
PATH = "/api/v1/site/example.com/artifacts/about/"
GET = ["get", "--slug", "about"]
#: The real transport, taken before the autouse ``server`` fixture replaces it.
real_transport = http.transport


def problem(status: int, code: str, detail: str, **extra: Any) -> dict[str, Any]:
    """A problem-details body as the server's exception handler writes it."""
    return {
        "type": f"https://api.eninesites.com/errors/{code}",
        "title": "x",
        "status": status,
        "code": code,
        "detail": detail,
        "instance": PATH,
        **extra,
    }


#: The keys of ``errors.ErrorResult``, named here so this file imports nothing the change
#: adds and A3 (``check_red.py``) can run it against the tree before the change.
KEYS = {"status", "code", "detail", "errors", "method", "path"}


def refusal_of(err: str) -> dict[str, Any]:
    """stderr as exactly one JSON document of the refusal shape."""
    record: dict[str, Any] = json.loads(err)
    assert set(record) == KEYS
    return record


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "not_authenticated"),
        (403, "permission_denied"),
        (404, "not_found"),
        (409, "conflict"),
        (500, "server_error"),
    ],
)
def test_a_problem_reply_keeps_its_status_and_code(
    status: int, code: str, server: FakeServer, run_cli: Run
) -> None:
    server.add(
        "GET",
        PATH,
        problem(status, code, "said the server"),
        status=status,
        content_type="application/problem+json",
    )
    exit_code, out, err = run_cli(artifact.main, [*GET, "--json"])
    assert (exit_code, out) == (2, "")
    record = refusal_of(err)
    assert (record["status"], record["code"]) == (status, code)
    assert (record["method"], record["path"]) == ("GET", PATH)
    assert record["detail"] == "said the server"


def test_validation_errors_reach_the_agent_as_fields(
    server: FakeServer, run_cli: Run
) -> None:
    server.add(
        "POST",
        "/api/v1/site/example.com/artifacts/",
        problem(
            400,
            "validation_error",
            "Request body failed validation.",
            errors={"name": ["Ensure this value has at most 32 characters."]},
        ),
        status=400,
        content_type="application/problem+json",
    )
    exit_code, _, err = run_cli(artifact.main, ["create", "--name", "x" * 40, "--json"])
    record = refusal_of(err)
    assert exit_code == 2
    assert record["code"] == "validation_error"
    assert record["errors"] == {
        "name": ["Ensure this value has at most 32 characters."]
    }


def test_an_html_error_page_is_not_problem_details(
    server: FakeServer, run_cli: Run
) -> None:
    server.add(
        "GET",
        PATH,
        raw=b"<!DOCTYPE html><title>404</title>",
        status=404,
        content_type="text/html",
    )
    _, _, err = run_cli(artifact.main, [*GET, "--json"])
    record = refusal_of(err)
    assert (record["status"], record["code"]) == (404, "not_problem")
    assert "HTML page" in record["detail"]


def test_a_success_body_that_is_not_json(server: FakeServer, run_cli: Run) -> None:
    server.add("GET", PATH, raw=b"hello", status=200, content_type="text/plain")
    _, _, err = run_cli(artifact.main, [*GET, "--json"])
    assert refusal_of(err)["code"] == "not_json"


def test_an_input_refusal_is_code_refused(server: FakeServer, run_cli: Run) -> None:
    exit_code, _, err = run_cli(artifact.main, ["create", "--title", "x", "--json"])
    record = refusal_of(err)
    assert (exit_code, record["code"], record["status"]) == (2, "refused", None)
    assert not server.calls


def test_a_verb_with_no_endpoint_is_code_not_available(run_cli: Run) -> None:
    exit_code, _, err = run_cli(
        site.main, ["delete", "--domain", "example.com", "--json"]
    )
    record = refusal_of(err)
    assert (exit_code, record["code"]) == (2, "not_available")
    assert "manage.py site --delete" in record["detail"]


def test_text_mode_still_prints_the_sentence(server: FakeServer, run_cli: Run) -> None:
    server.add(
        "GET",
        PATH,
        problem(404, "not_found", "No artifact."),
        status=404,
        content_type="application/problem+json",
    )
    exit_code, out, err = run_cli(artifact.main, GET)
    assert (exit_code, out) == (2, "")
    assert err == f"GET {PATH}: HTTP 404 not_found: No artifact.\n"


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (
            error.URLError(ConnectionRefusedError(111, "Connection refused")),
            "unreachable",
        ),
        (error.URLError(TimeoutError("timed out")), "timeout"),
        (TimeoutError("timed out"), "timeout"),
    ],
)
def test_no_reply_is_unreachable_or_timeout(
    raised: Exception, code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise raised

    monkeypatch.setattr(http._OPENER, "open", fail)  # pylint: disable=protected-access
    req = request.Request("https://eninesites.com" + PATH, method="GET")
    with pytest.raises(ApiError) as caught:
        real_transport(req, 1.0)
    record = caught.value.record()
    assert (record["status"], record["code"], record["path"]) == (None, code, PATH)


def test_a_rewrapped_refusal_keeps_its_fields(server: FakeServer, run_cli: Run) -> None:
    server.add(
        "GET",
        "/api/v1/site/nope.com/configure/",
        problem(404, "not_found", "No."),
        status=404,
        content_type="application/problem+json",
    )
    _, _, err = run_cli(site.main, ["select", "--domain", "nope.com", "--json"])
    record = refusal_of(err)
    assert (record["status"], record["code"]) == (404, "not_found")


@pytest.mark.parametrize(
    "argv",
    [["get", "--json", "--bogus"], ["get", "--json"], ["chek", "--json"]],
    ids=["unknown-argument", "missing-argument", "unknown-verb"],
)
def test_a_usage_error_under_json_is_only_json(argv: list[str], run_cli: Run) -> None:
    exit_code, out, err = run_cli(artifact.main, argv)
    record = refusal_of(err)
    assert (exit_code, out, record["code"]) == (2, "", "usage")
    assert "usage:" not in err


def test_a_usage_error_without_json_keeps_the_help(run_cli: Run) -> None:
    exit_code, _, err = run_cli(artifact.main, ["get", "--bogus"])
    assert exit_code == 2
    assert "usage:" in err
    assert err.rstrip().endswith("unrecognized arguments: --bogus")
