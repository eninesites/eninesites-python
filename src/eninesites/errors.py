"""The one exception a surface of eninesites catches: a request the api cannot run."""

from __future__ import annotations

from typing import Any, TypedDict

from eninesites.lib.jsonvalue import Json, JsonObject

#: The codes the client sets itself, when the server sent none. A server ``code`` (RFC 9457
#: problem details, the server's ``docs/API.md``) is passed through unchanged.
CLIENT_CODES = (
    "refused",  # the api refused its input; nothing was sent
    "unreachable",  # no connection to the server
    "timeout",  # the server did not answer in time
    "redirect_refused",  # the server redirected; the key is not sent onward
    "not_problem",  # an error reply without problem details (an HTML 404, say)
    "not_json",  # a success reply whose body is not JSON
    "not_available",  # the verb has no REST endpoint
    "usage",  # the command line itself was wrong
)


class ErrorResult(TypedDict):
    """A refusal as data: what ``--json`` writes on stderr when a verb cannot run.

    ``code`` is the server's own when it sent one, else one of ``CLIENT_CODES``. ``status``
    is the HTTP status, or null when no reply came back. ``errors`` carries the server's
    per-field errors on a validation or conflict failure.
    """

    status: int | None
    code: str
    detail: str
    errors: JsonObject | list[Json] | None
    method: str | None
    path: str | None


class ApiError(Exception):
    """The api refused: bad input, or a target that does not exist.

    Never a finding about the data asked for: an empty result is data, and the api
    returns it. A surface turns this into its own refusal; the cli prints the message on
    stderr and exits with ``exit_code``, or under ``--json`` prints ``record()`` instead.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        message: str,
        exit_code: int = 2,
        *,
        status: int | None = None,
        code: str = "refused",
        detail: str | None = None,
        errors: dict[str, Any] | list[Any] | None = None,
        method: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.status = status
        self.code = code
        self.detail = message if detail is None else detail
        self.errors = errors
        self.method = method
        self.path = path

    def reworded(self, message: str) -> ApiError:
        """The same refusal under a new message; every field is kept."""
        return ApiError(
            message,
            self.exit_code,
            status=self.status,
            code=self.code,
            detail=self.detail,
            errors=self.errors,
            method=self.method,
            path=self.path,
        )

    def record(self) -> ErrorResult:
        """The refusal as data: the shape ``--json`` prints on stderr."""
        return {
            "status": self.status,
            "code": self.code,
            "detail": self.detail,
            "errors": self.errors,
            "method": self.method,
            "path": self.path,
        }
