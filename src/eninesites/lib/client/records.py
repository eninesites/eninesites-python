"""Shaping server payloads into the records a verb declares, and reading verb input.

``project`` keeps exactly the keys a result's TypedDict declares, recursively, so what
``--json`` prints is always the shape ``output()`` publishes: a field the server adds later
is dropped rather than breaking the published schema, and a field it omits is simply absent
(server row types are ``total=False``).

``request_body`` reads the ``--data`` param: a JSON file holding the request fields (``-``
for stdin), the way the Stripe CLI's ``-d`` carries fields a command has no flag for.
"""

from __future__ import annotations

import json
import sys
import types
import typing
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints, is_typeddict

from eninesites.errors import ApiError

_UNIONS = (typing.Union, types.UnionType)


def project(value: Any, tp: Any) -> Any:
    """``value`` cut down to what ``tp`` declares: TypedDict keys, list items, union arms."""
    origin, args = get_origin(tp), get_args(tp)
    if origin in _UNIONS:
        arms = [arm for arm in args if is_typeddict(arm)]
        tp = arms[0] if arms and isinstance(value, dict) else None
        origin, args = None, ()
    if tp is not None and is_typeddict(tp):
        if not isinstance(value, dict):
            return {}
        hints = get_type_hints(tp)
        return {k: project(value[k], hints[k]) for k in hints if k in value}
    if origin is list and args:
        return (
            [project(item, args[0]) for item in value]
            if isinstance(value, list)
            else []
        )
    return value


def rows(payload: Any, tp: Any) -> list[Any]:
    """Each row of a list response (envelope or bare array) projected onto ``tp``."""
    if isinstance(payload, dict):
        payload = payload.get("results") or []
    return project(payload, list[tp]) if isinstance(payload, list) else []


def request_body(data: Path | str | None) -> dict[str, Any]:
    """The ``--data`` file's JSON object; ``-`` reads it from stdin; ``{}`` when unset.

    ``--data`` names a file, as racecar's vocabulary types it (``path``), so a body is never
    squeezed into a shell argument: ``--data body.json``, or ``... | <cmd> --data -``.
    """
    if data is None or str(data) == "":
        return {}
    if str(data) == "-":
        text = sys.stdin.read()
        where = "stdin"
    else:
        path = Path(data).expanduser()
        where = str(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ApiError(f"--data {path}: cannot read it: {exc.strerror}") from exc
    try:
        body = json.loads(text)
    except ValueError as exc:
        raise ApiError(f"--data {where}: not valid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise ApiError(
            f'--data {where}: must hold a JSON object, e.g. {{"title": "About"}}'
        )
    return body


def merged(data: Path | str | None, **fields: Any) -> dict[str, Any]:
    """``--data`` with each named flag laid over it; a flag left unset adds nothing."""
    body = request_body(data)
    body.update({k: v for k, v in fields.items() if v is not None})
    return body


def json_file(path: Path, what: str) -> Any:
    """A local JSON file's content, refused with the flag's name when it cannot be read."""
    try:
        return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except OSError as exc:
        raise ApiError(f"{what} {path}: cannot read it: {exc.strerror}") from exc
    except ValueError as exc:
        raise ApiError(f"{what} {path}: not valid JSON: {exc}") from exc


_TRUE = frozenset({"true", "yes", "1", "on"})
_FALSE = frozenset({"false", "no", "0", "off"})


def boolean(value: str | None, flag: str) -> bool | None:
    """A yes/no flag given as text (``true``/``false``, ``yes``/``no``, ``1``/``0``)."""
    if value is None:
        return None
    word = value.strip().lower()
    if word in _TRUE:
        return True
    if word in _FALSE:
        return False
    raise ApiError(f"{flag} {value!r}: expected true or false")


def integer(value: str | int | None, flag: str) -> int | None:
    """An id given as text, refused by name when it is not a whole number."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(f"{flag} {value!r}: expected a whole number") from exc


def refuse_unsupported(verb: str, why: str, **given: Any) -> None:
    """Refuse a flag the REST endpoint cannot honour, rather than drop it silently."""
    named = [f"--{k.rstrip('_').replace('_', '-')}" for k, v in given.items() if v]
    if named:
        raise ApiError(
            f"{verb}: {', '.join(named)} not accepted over the REST API: {why}"
        )


def not_over_rest(verb: str, where: str) -> ApiError:
    """The refusal for a verb the eninesites REST API has no endpoint for."""
    return ApiError(
        f"`{verb}` is not available over the eninesites REST API: {where}",
        code="not_available",
    )


def required(value: str | int | None, flag: str, what: str = "") -> str:
    """A flag the verb cannot run without, stripped; refused by name when absent."""
    if value is None or not str(value).strip():
        raise ApiError(f"{flag} is required{f' ({what})' if what else ''}")
    return str(value).strip()


def required_int(value: str | int | None, flag: str, what: str = "") -> int:
    """A whole-number flag the verb cannot run without (an id), refused by name otherwise."""
    text = required(value, flag, what)
    try:
        return int(text)
    except ValueError as exc:
        raise ApiError(f"{flag} {text!r}: expected a whole number") from exc
