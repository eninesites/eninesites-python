"""The transport: one authenticated JSON request to the eninesites REST API, and its errors.

Wire conventions are the server's ``docs/API.md``: everything under ``/api/v1/``, served
only on the platform host; ``Authorization: Token <key>`` for a headless caller; success is
the resource itself (or 204 with no body); errors are RFC 9457 problem details
(``application/problem+json`` with ``code``, ``detail`` and, on validation, ``errors``);
list endpoints are paginated ``{count, next, previous, results}`` or, on several endpoints,
a bare array.

Every failure becomes the package's one refusal, ``ApiError``, whose message names the HTTP
status, the server's ``code`` and its ``detail``. The key never appears in a message.

``transport`` is the only function that touches the network; tests replace it.
"""

from __future__ import annotations

import json
import mimetypes
import platform
import re
import uuid
from dataclasses import dataclass, field
from email.message import Message
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import quote, urlencode

from eninesites.errors import ApiError

from . import credentials
from .credentials import Settings

TIMEOUT_SECONDS = 60.0
#: The server's page-size cap (``services/manager/api/v1/pagination.py``).
PAGE_SIZE = 200
#: A runaway guard for pagination: 200 pages of 200 is 40,000 rows.
MAX_PAGES = 200


@dataclass(frozen=True)
class Reply:
    """What came back: the status, the headers that matter, and the raw body."""

    status: int
    content_type: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


class _NoRedirect(request.HTTPRedirectHandler):
    """Refuse every redirect.

    urllib would follow it and send the ``Authorization`` header to wherever it points. The
    API is served from one host, so a redirect means the base URL is wrong, and saying so is
    safer than following it (the Stripe CLI's login refuses redirects for the same reason).
    """

    # urllib's own signature, overridden as it is declared.
    # pylint: disable-next=too-many-positional-arguments
    def redirect_request(
        self,
        req: request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        raise ApiError(
            f"the server redirected {req.get_method()} {req.full_url} to {newurl} "
            f"({code}); not followed, so the API key is not sent there. If that is the "
            "API's real address, pass it as --base-url."
        )


_OPENER = request.build_opener(_NoRedirect)


def transport(req: request.Request, timeout: float) -> Reply:
    """Send one request and return the reply, an HTTP error status included."""
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return Reply(
                resp.status,
                resp.headers.get_content_type(),
                resp.read(),
                {k.lower(): v for k, v in resp.headers.items()},
            )
    except error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        content_type = exc.headers.get_content_type() if exc.headers else ""
        return Reply(exc.code, content_type, body, {})
    except error.URLError as exc:
        raise ApiError(f"cannot reach {req.full_url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ApiError(f"{req.full_url} did not answer within {timeout:.0f}s") from exc


def _version() -> str:
    try:
        return metadata.version("eninesites")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def user_agent_headers() -> dict[str, str]:
    """The client identification headers, in the Stripe CLI's pair of shapes."""
    version = _version()
    return {
        "User-Agent": f"eninesites-python/{version} python/{platform.python_version()}",
        "X-Eninesites-Client-User-Agent": json.dumps(
            {
                "name": "eninesites-python",
                "version": version,
                "lang": "python",
                "lang_version": platform.python_version(),
                "os": platform.system().lower(),
            },
            sort_keys=True,
        ),
    }


def segment(value: str | int) -> str:
    """One URL path segment: a domain, slug or name, with ``/`` and the rest escaped."""
    return quote(str(value).strip(), safe="")


class Client:
    """An authenticated client bound to one base URL and one key."""

    def __init__(self, settings: Settings) -> None:
        """Bind to resolved settings; refuses now when there is no key to send."""
        self.settings = settings
        self._key = credentials.require_key(settings)

    def site_path(self, *parts: str | int) -> str:
        """``/api/v1/site/<site>/<parts...>/`` for the resolved site."""
        site = credentials.require_site(self.settings)
        return "/api/v1/site/" + "/".join(segment(p) for p in (site, *parts)) + "/"

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str | int] | None = None,
        body: Any = None,
        files: list[Path] | None = None,
        form: dict[str, str] | None = None,
    ) -> Reply:
        """Send one request; return the reply when it succeeded, else raise ``ApiError``."""
        url = self.settings.base_url + path
        if query:
            url += "?" + urlencode(query)
        headers = {
            **user_agent_headers(),
            "Accept": "application/json",
            "Authorization": f"Token {self._key}",
        }
        data: bytes | None = None
        if files is not None:
            data, headers["Content-Type"] = multipart(files, form or {})
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=data, headers=headers, method=method)
        reply = transport(req, TIMEOUT_SECONDS)
        if reply.status >= 400:
            raise ApiError(describe_error(method, path, reply))
        return reply

    def json(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send one request and decode its JSON body; ``None`` for an empty (204) body."""
        reply = self.request(method, path, **kwargs)
        if not reply.body.strip():
            return None
        try:
            return json.loads(reply.body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(
                f"{method} {path}: the server answered {reply.status} with a body that is "
                f"not JSON ({reply.content_type or 'no content type'})"
            ) from exc

    def get(self, path: str, query: dict[str, str | int] | None = None) -> Any:
        """GET one resource as decoded JSON."""
        return self.json("GET", path, query=query)

    def list_all(self, path: str) -> list[Any]:
        """Every row of a list endpoint, following pages until ``next`` is null.

        Tolerates both shapes ``docs/API.md`` documents: the paginated envelope and the
        bare array several endpoints return.
        """
        rows: list[Any] = []
        for page in range(1, MAX_PAGES + 1):
            payload = self.get(path, {"page": page, "page_size": PAGE_SIZE})
            if isinstance(payload, list):
                return rows + payload
            if not isinstance(payload, dict):
                return rows
            rows += payload.get("results") or []
            if not payload.get("next"):
                return rows
        raise ApiError(f"GET {path}: more than {MAX_PAGES} pages; refusing to continue")


def describe_error(method: str, path: str, reply: Reply) -> str:
    """One line naming what went wrong, from the problem details when the server sent them."""
    head = f"{method} {path}: HTTP {reply.status}"
    try:
        payload = json.loads(reply.body) if reply.body.strip() else None
    except (ValueError, UnicodeDecodeError):
        payload = None
    if isinstance(payload, dict):
        code = payload.get("code") or payload.get("error")
        detail = payload.get("detail") or payload.get("message")
        if code and code != detail:
            head += f" {code}"
        if detail:
            head += f": {detail}"
        if payload.get("errors"):
            head += f" -- {flatten_errors(payload['errors'])}"
    elif reply.body.strip():
        text = re.sub(r"\s+", " ", reply.body.decode("utf-8", "replace")).strip()
        if reply.content_type in ("text/html", "application/xhtml+xml"):
            text = "an HTML page (is --base-url the eninesites platform host?)"
        head += f": {text[:200]}"
    if reply.status == 401:
        head = head.rstrip(".") + (
            ". Check the API key: `python -m eninesites config` shows which one is used."
        )
    return head


def flatten_errors(errors: Any, prefix: str = "") -> str:
    """DRF field errors (``{"field": ["msg"]}``, nested, or a flat list) as one line."""
    if isinstance(errors, dict):
        return "; ".join(
            flatten_errors(v, f"{prefix}.{k}" if prefix else str(k))
            for k, v in errors.items()
        )
    if isinstance(errors, list):
        if any(isinstance(e, (dict, list)) for e in errors):
            return "; ".join(flatten_errors(e, prefix) for e in errors)
        text = " ".join(str(e) for e in errors)
        return f"{prefix}: {text}" if prefix else text
    return f"{prefix}: {errors}" if prefix else str(errors)


def multipart(files: list[Path], form: dict[str, str]) -> tuple[bytes, str]:
    """A ``multipart/form-data`` body: each file under the field name ``file``."""
    boundary = f"eninesites-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in form.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            + value.encode("utf-8")
            + b"\r\n"
        )
    for path in files:
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ApiError(f"cannot read {path}: {exc.strerror}") from exc
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        filename = path.name.replace('"', "_")
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{filename}"\r\nContent-Type: {kind}\r\n\r\n'
            ).encode()
            + content
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def connect(
    api_key: str | None = None,
    base_url: str | None = None,
    project_name: str | None = None,
    domain: str | None = None,
) -> Client:
    """Resolve the settings for one command and return a client bound to them."""
    return Client(credentials.resolve(api_key, base_url, project_name, domain))


def filename_from(reply: Reply) -> str | None:
    """The ``filename`` a ``Content-Disposition: attachment`` header names, if any."""
    disposition = reply.headers.get("content-disposition", "")
    match = re.search(r'filename="?([^";]+)"?', disposition)
    return Path(match.group(1)).name if match else None
