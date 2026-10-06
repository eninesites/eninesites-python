"""The shapes the eninesites root api returns: one TypedDict per verb.

The one home of every root result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. A result
holds JSON types only. No result ever holds an API key in full: ``api_key`` is the
redacted form, its last four characters.
"""

from __future__ import annotations

from typing import TypedDict

from eninesites.lib.jsonvalue import Json


class LoginRoot(TypedDict):
    """What ``login`` returns: the project the key was stored under, and the check it passed."""

    project_name: str
    config_path: str
    base_url: str
    api_key: str | None
    sites: int


class LogoutRoot(TypedDict):
    """What ``logout`` returns: the projects whose key was removed (empty: none was stored)."""

    project_name: str
    all: bool
    cleared: list[str]
    config_path: str
    env_key_set: bool


class ConfigRoot(TypedDict):
    """What ``config`` returns: each setting a command would use, and the tier it came from."""

    project_name: str
    project_source: str
    config_path: str
    config_exists: bool
    base_url: str
    base_url_source: str
    api_key: str | None
    api_key_source: str | None
    site: str | None
    site_source: str | None


class Arg(TypedDict):
    """One flag a verb takes, named as racecar's CLI audit names it (its ``Arg``)."""

    dest: str
    flags: list[str]
    help: str | None
    required: bool
    choices: list[str] | None
    default: Json
    type: str | None
    action: str | None


class Command(TypedDict):
    """One runnable command: what to type, whether it writes, its flags and its result.

    ``output`` is the JSON Schema of what ``--json`` prints, as JSON text: a schema nests
    deeper than a result may (``lib.jsonvalue``), so it is carried as a string to parse.
    """

    command: str
    noun: str
    verb: str
    description: str
    writes: bool
    args: list[Arg]
    output: str


class DescribeRoot(TypedDict):
    """What ``describe`` returns: every command, and the shapes every command shares.

    ``error`` is the JSON Schema of the refusal ``--json`` writes on stderr, ``planned`` that
    of a write verb's ``--dry-run`` result, both as JSON text like ``Command.output``.
    """

    commands: list[Command]
    error: str
    planned: str
    exit_codes: dict[str, str]
