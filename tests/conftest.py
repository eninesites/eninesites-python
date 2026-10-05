"""The helpers every CLI test shares.

``run_cli`` runs a node's ``main(argv)`` and reads what it wrote. ``server`` stands in for
the eninesites REST API: it is installed for EVERY test (autouse), replacing the client's
one network function, so no test can reach a real host. It records each request and
answers from routes a test registers, or with ``200 {}`` by default. Every test also gets a
private config directory and a known environment: an API key, a selected site, no base URL
or project override.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, get_type_hints
from urllib.parse import parse_qs, urlsplit

import pytest

import eninesites.schema
from eninesites.errors import ApiError
from eninesites.lib.client import http

Main = Callable[[list[str] | None], int]

API_KEY = "0123456789abcdef0123456789abcdef0123abcd"  # gitleaks:allow
SITE = "example.com"
#: Files every test finds in its working directory (a private tmp dir), for verbs that read one.
SAMPLE_FILES: dict[str, bytes] = {
    "site.json": b'{"content": []}',
    "site.zip": b"PK\x05\x06" + b"\x00" * 18,
    "logo.png": b"\x89PNG\r\n\x1a\n",
    "config.json": b'{"theme": "bauhaus"}',
    "design.json": b'{"card_template": "card"}',
    "aeo.json": b'{"what": "Consulting"}',
    "map.json": b'{"artifact_b": 7}',
    "order.json": b'{"order": 2}',
    "url.json": b'{"label": "Docs", "url": "https://docs.example"}',
    "label.json": b'{"label": "Manual"}',
    "urlmap.json": b'{"path": "legal/terms", "projection": "detail", "artifact": "terms"}',
    "canonical.json": b'{"is_canonical": true}',
    "seopage.json": b'{"canonical": "https://example.com/about/", "page_title": "About us"}',
    "seotitle.json": b'{"page_title": "About"}',
    "filename.json": b'{"filename": "hero"}',
    "navbar.json": b'{"navbar": true}',
    "theme.json": (
        b'{"domain": "example.com", "custom_theme": {"name": "mine", "parent": "bauhaus", '
        b'"templates": {"home.html": "<h1>hi</h1>"}}}'
    ),
}


@dataclass
class Call:
    """One request the client sent."""

    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes | None

    def json(self) -> Any:
        """The request body decoded as JSON."""
        assert self.body is not None
        return json.loads(self.body)


@dataclass
class FakeServer:
    """Answers the client's requests from registered routes; records every one."""

    routes: dict[tuple[str, str], list[http.Reply]] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

    def add(  # pylint: disable=too-many-arguments
        self,
        method: str,
        path: str,
        payload: Any = None,
        *,
        status: int = 200,
        content_type: str = "application/json",
        raw: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Queue one answer for ``method path``; the last one queued repeats."""
        body = (
            raw
            if raw is not None
            else (b"" if payload is None else json.dumps(payload).encode())
        )
        reply = http.Reply(status, content_type, body, headers or {})
        self.routes.setdefault((method, path), []).append(reply)

    def __call__(self, req: Any, timeout: float) -> http.Reply:
        url = urlsplit(req.full_url)
        assert url.scheme in ("https", "http")
        call = Call(
            req.get_method(),
            url.path,
            parse_qs(url.query),
            {k.lower(): v for k, v in req.header_items()},
            req.data,
        )
        self.calls.append(call)
        queue = self.routes.get((call.method, call.path))
        if not queue:
            return http.Reply(200, "application/json", b"{}", {})
        return queue.pop(0) if len(queue) > 1 else queue[0]

    @property
    def last(self) -> Call:
        """The most recent request."""
        assert self.calls, "no request was sent"
        return self.calls[-1]


@pytest.fixture(name="server", autouse=True)
def _server(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Iterator[FakeServer]:
    """A fake API for every test, a private config dir, and a known environment."""
    fake = FakeServer()
    monkeypatch.setattr(http, "transport", fake)

    def no_network(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a test tried to open a real network connection")

    opener = http._OPENER  # pylint: disable=protected-access
    monkeypatch.setattr(opener, "open", no_network)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("ENINESITES_API_KEY", API_KEY)
    monkeypatch.setenv("ENINESITES_SITE", SITE)
    monkeypatch.delenv("ENINESITES_BASE_URL", raising=False)
    monkeypatch.delenv("ENINESITES_PROJECT_NAME", raising=False)
    monkeypatch.chdir(tmp_path)
    for name, content in SAMPLE_FILES.items():
        (tmp_path / name).write_bytes(content)
    yield fake


@pytest.fixture(name="returns_declared")
def _returns_declared() -> Callable[[Callable[..., Any], dict[str, Any], bool], None]:
    """Assert a verb returns its declared type, or, for a verb with no endpoint, refuses."""

    def check(
        fn: Callable[..., Any], sample: dict[str, Any], unavailable: bool
    ) -> None:
        if unavailable:
            with pytest.raises(
                ApiError, match="not available over the eninesites REST API"
            ):
                fn(**sample)
            return
        result = fn(**sample)
        assert eninesites.schema.conforms(result, get_type_hints(fn)["return"]) == []

    return check


@pytest.fixture(name="run_cli")
def _run_cli(
    capsys: pytest.CaptureFixture[str],
) -> Callable[[Main, list[str]], tuple[int, str, str]]:
    """(exit code, stdout, stderr) of one invocation, whether it returned or exited."""

    def run(main: Main, argv: list[str]) -> tuple[int, str, str]:
        try:
            code = main(argv)
        except SystemExit as exc:
            code = int(exc.code or 0)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run
