"""The CLI's config file: where it lives, how it is read, and how it is written safely.

Modelled on the Stripe CLI (``pkg/config``): ``$XDG_CONFIG_HOME/eninesites/config.toml``,
else ``~/.config/eninesites/config.toml``, in Stripe's v2 layout -- a ``config_version = 2``
line and one ``[profiles.<name>]`` table per project::

    config_version = 2

    [profiles.default]
    api_key = "..."
    base_url = "https://eninesites.com"
    site = "example.com"

The file holds a secret, so it is written stricter than Stripe writes its own: the directory
0700, the file 0600 from the moment it exists (a temporary file chmodded before the rename),
and never through a symlink. Reading uses ``tomllib``; writing uses the small serializer
below, because the standard library has no TOML writer and every value here is a string.
"""

from __future__ import annotations

import os
import stat
import tempfile
import tomllib
from pathlib import Path

from eninesites.errors import ApiError

CONFIG_VERSION = 2
APP_DIR = "eninesites"
FILE_NAME = "config.toml"
DEFAULT_PROFILE = "default"
#: The keys a profile may hold. Anything else in the file is kept but never written by us.
PROFILE_KEYS = ("api_key", "base_url", "site")

Profiles = dict[str, dict[str, str]]


def config_path() -> Path:
    """The config file: under ``$XDG_CONFIG_HOME`` when set, else ``~/.config``."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR / FILE_NAME


def load(path: Path | None = None) -> Profiles:
    """Every profile in the file, as ``{name: {key: value}}``; empty when there is no file.

    A v1 file (one top-level table per profile, Stripe's older layout) is read too, so a
    hand-written ``[default]`` table works. A file that does not parse is refused rather
    than treated as empty, because the next write would overwrite it.
    """
    path = path or config_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ApiError(f"cannot read the config file {path}: {exc.strerror}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ApiError(f"the config file {path} is not valid TOML: {exc}") from exc
    tables = data.get("profiles") if "profiles" in data else data
    if not isinstance(tables, dict):
        return {}
    return {
        str(name): {str(k): v for k, v in table.items() if isinstance(v, str)}
        for name, table in tables.items()
        if isinstance(table, dict)
    }


def save(profiles: Profiles, path: Path | None = None) -> Path:
    """Write every profile, atomically, 0600 in a 0700 directory. Returns the path."""
    path = path or config_path()
    if path.is_symlink():
        raise ApiError(f"refusing to write the config file through a symlink: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    text = dumps(profiles)
    fd, tmp = tempfile.mkstemp(prefix=".config.", suffix=".toml", dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def update_profile(name: str, path: Path | None = None, **changes: str | None) -> Path:
    """Set (a value) or remove (``None``) keys of one profile and write the file."""
    path = path or config_path()
    profiles = load(path)
    table = profiles.setdefault(name, {})
    for key, value in changes.items():
        if value is None:
            table.pop(key, None)
        else:
            table[key] = value
    if not table:
        del profiles[name]
    return save(profiles, path)


def dumps(profiles: Profiles) -> str:
    """The profiles as TOML text in the v2 layout, profiles and keys in a stable order."""
    lines = [f"config_version = {CONFIG_VERSION}"]
    for name in sorted(profiles):
        table = profiles[name]
        if not table:
            continue
        lines += ["", f"[profiles.{_key(name)}]"]
        lines += [f"{_key(k)} = {_string(table[k])}" for k in sorted(table)]
    return "\n".join(lines) + "\n"


def _key(name: str) -> str:
    """A TOML key: bare when it can be, quoted otherwise."""
    bare = name and all(c.isalnum() or c in "-_" for c in name) and name.isascii()
    return name if bare else _string(name)


def _string(value: str) -> str:
    """A TOML basic string, every character that needs it escaped."""
    out = ['"']
    for char in value:
        if char in ('"', "\\"):
            out.append("\\" + char)
        elif char == "\n":
            out.append("\\n")
        elif char == "\t":
            out.append("\\t")
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)
