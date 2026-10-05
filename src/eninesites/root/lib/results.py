"""The shapes the eninesites root api returns: one TypedDict per verb.

The one home of every root result shape. The api returns them, the renderers read
them, and ``output()`` publishes them as JSON Schema; nothing restates them. A result
holds JSON types only. No result ever holds an API key in full: ``api_key`` is the
redacted form, its last four characters.
"""

from __future__ import annotations

from typing import TypedDict


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
