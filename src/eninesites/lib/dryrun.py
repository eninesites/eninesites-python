"""``--dry-run``: what a write verb would send, returned as its result instead of sent.

A write verb acts by default. Under ``--dry-run`` its api function runs as usual, GETs
included, because a write often resolves something first, and the client stops at the first
request that is not a GET: it raises ``Planned`` carrying that request, and ``writes``
returns it as a ``PlannedRequest``. Every write verb sends at most one such request (a test
holds that), so the one recorded is the whole of what the verb would change.

``writes`` is also the one place that says a verb writes: it marks the api function, and
each noun's parser gives ``--dry-run`` to exactly the verbs whose function is marked. The
``dry_run`` parameter itself is written into each function's own signature, because the
surface checks read the signature (``inspect.signature`` and the AST), and a parameter a
decorator added would be invisible to both.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, Literal, ParamSpec, Protocol, TypedDict, TypeVar, cast

from eninesites.lib.jsonvalue import Json, JsonObject

P = ParamSpec("P")
R = TypeVar("R")

FLAG_HELP = "Show what would be sent or written, and change nothing."


class PlannedRequest(TypedDict):
    """What a write verb would have done under ``--dry-run``.

    ``method`` and ``path`` are the HTTP request (``path`` under the base URL), or, for a
    verb that writes the local config file, ``WRITE`` or ``REMOVE`` and the file's path.
    ``body`` is the JSON body, ``files`` the files a multipart upload would carry, ``form``
    its other fields.
    """

    dry_run: Literal[True]
    method: str
    path: str
    query: JsonObject | None
    body: Json
    files: list[str] | None
    form: dict[str, str] | None


class Planned(Exception):
    """The request a dry run stopped at, before it was sent."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any = None,
        files: list[str] | None = None,
        form: dict[str, str] | None = None,
    ) -> None:
        super().__init__(f"would send {method} {path}")
        self.method = method
        self.path = path
        self.query = query
        self.body = body
        self.files = files
        self.form = form

    def record(self) -> PlannedRequest:
        """The planned request as a verb's result."""
        return {
            "dry_run": True,
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "body": self.body,
            "files": self.files,
            "form": self.form,
        }


def writes(fn: Callable[P, R]) -> Callable[P, R]:
    """Mark ``fn`` as a write verb, and return its planned request under ``dry_run``."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except Planned as planned:
            return cast(R, planned.record())

    setattr(wrapper, "writes", True)
    return wrapper


def is_write(fn: object) -> bool:
    """Whether ``fn`` is a write verb's api function."""
    return bool(getattr(fn, "writes", False))


def is_planned(result: object) -> bool:
    """Whether a verb's result is a planned request rather than what it did."""
    return isinstance(result, dict) and result.get("dry_run") is True


def done(result: R | PlannedRequest) -> R:
    """A write verb's own result, typed as such; ``TypeError`` if it is a planned request.

    A write verb returns ``<Result> | PlannedRequest``. A Python caller that did not ask for a
    dry run passes the result through this to index it as ``<Result>``.
    """
    if is_planned(result):
        raise TypeError(
            "this result is a dry run's planned request, not what the verb did"
        )
    return cast(R, result)


class ArgumentHolder(Protocol):  # pylint: disable=too-few-public-methods
    """A parser: whatever takes an argument."""

    def add_argument(self, *names: str, **options: Any) -> Any:
        """Declare one argument."""


def add_flag(holder: ArgumentHolder) -> None:
    """Give a write verb's parser the ``--dry-run`` switch."""
    holder.add_argument("--dry-run", action="store_true", help=FLAG_HELP)
