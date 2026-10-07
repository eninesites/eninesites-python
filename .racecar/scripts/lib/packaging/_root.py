"""The `.git` walk-up every delivered script uses to find the repo it is grading, and the
one place that says where that repo keeps its package.

ONE HOME. The library reaches this file through a symlink, `src/racecar/lib/_root.py`, so
`racecar.lib._root` IS this file -- the arrangement `_shape.py`, `_findings.py`, `_files.py`,
`_cli.py` and `_as_json.py` already have. `lib/packaging/_root.py` is a second symlink, so
`_shape.py` reads the package root as a sibling in both trees it runs from. What only racecar
needs (where the racecar checkout is, the `--root` check) is in
`lib/racecar_only/_root_racecar_only.py`, which no adopter receives. It used to be the
other way round: the library held the authored copy and this file was a verbatim copy that a
test held identical. A delivered checker has to run from an adopter's flat `scripts/` with no
racecar installed, so it cannot import `racecar.lib`; that forces this file to stand alone,
and it does. It never forced a second copy.

It lives in `lib/shared/` because twenty-one scripts import it. Every script sits in one
flat `scripts/`, in racecar and in every adopter alike, so `lib` is a sibling under every
invocation and the import needs no help. Nothing outside this file re-implements the walk-up
or the package root.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor of `start` (default CWD) holding `.racecar/` or `.git`.

    `.racecar/` first in meaning: it is where racecar was delivered, so its parent is the
    repo racecar governs, and `package create` writes it before any `git init`. `.git`
    answers for a repo racecar has not been delivered into yet, which is where the first
    sync runs. Whichever marker is nearer wins, so a checkout nested in another resolves to
    itself.

    ONE HOME: this file. The library imports it as `racecar.lib._root`, a symlink, so a
    delivered checker and the library run the same bytes.

    Resolved, so the root compares equal to the `--root` paths callers already
    resolve. Returns `start` when neither is found rather than raising: a checker
    run outside a repo should report on what is there, not fail to start.
    """
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ".racecar").is_dir() or (candidate / ".git").exists():
            return candidate
    return start


def git_common_dir(path: Path) -> Path | None:
    """Return the repository `path` belongs to, or None when it is not in one.

    The COMMON dir, not the git dir: a worktree's git dir is private to it
    (`.git/worktrees/<name>`) while its common dir is the repository every worktree
    shares. That distinction is the whole value of the call -- it is what makes two
    checkouts of one repo answer the same thing.

    None on every negative: not a repo, no git on the machine, a path that does not
    exist. A caller comparing two of these must therefore treat None as "cannot say",
    never as a match, which :func:`same_repository` does.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # git is not installed
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    common = Path(proc.stdout.strip())
    return common.resolve() if common.is_absolute() else (path / common).resolve()


def same_repository(one: Path, other: Path) -> bool:
    """Whether two paths are checkouts of ONE repository -- a git worktree included.

    A path comparison cannot answer this. Two worktrees of one repo share no path prefix
    with each other, a clone sits wherever it was put, and `.claude/worktrees/<branch>/`
    is BOTH nested inside the main checkout and a separate checkout of the same
    repository. A checker that derives an identity from the directory gets the wrong
    answer there: it takes canon from the other checkout, so an edit made on the branch
    reads as the branch contradicting canon.

    One path is trivially itself: the identity case short-circuits, so a directory that
    is not a git repository at all -- a fixture, a vendored tree, an unpacked archive --
    still reads as the same checkout as itself. Only the two-checkouts question needs git.

    False when either side cannot be resolved. An unanswerable question is not a match.
    """
    if one.resolve() == other.resolve():
        return True
    here = git_common_dir(one)
    return here is not None and here == git_common_dir(other)


def project_name(root: Path) -> str | None:
    """Return `[project].name`, or None when the repo declares none.

    Tolerant of an unparseable or absent pyproject: callers resolve a filename or a
    package with it, and a malformed manifest is a finding for the packaging checker, not
    a reason for a reader to die before it reports anything.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None
    name = data.get("project", {}).get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def package_root(root: Path) -> Path:
    """Where `root` keeps its package: `src/` when it exists, else the repo root when the
    package `[project].name` names sits there (the `flat` shape, `flat_package`), else `src/`.

    The one statement of the package root, and the only thing that differs between the
    `src` and `flat` shapes. Everything that asks where the package lives asks here. A repo
    with neither is read as `src/`, where racecar scaffolds a new package.
    """
    src = root / "src"
    if src.is_dir():
        return src
    return root if flat_package(root) is not None else src


def flat_package(root: Path) -> Path | None:
    """The package at the repo root that `[project].name` names, when there is no `src/`.

    A root holds more than packages (`tests/`, tooling), so at the root only the name the
    repo declares can say which folder it ships; with no name, there is no `flat` package.
    """
    if (root / "src").is_dir():
        return None
    name = project_name(root)
    if name is None:
        return None
    package = root / module_name(name)
    return package if (package / "__init__.py").is_file() else None


def has_library(root: Path) -> bool:
    """Whether `root` carries a library: a `src/`, or the package `[project].name` names at
    the root (the `flat` shape). The PYTHON_LIBRARY axis of the shape, stated once.
    """
    return (root / "src").is_dir() or flat_package(root) is not None


def server_root(root: Path) -> Path | None:
    """Where `root` keeps its Django project, or None when it has none.

    `server/` when `server/manage.py` exists (racecar's server shell, beside a library or
    alone); else the repo root, when a root `manage.py` exists and there is no library (a
    startproject site, the `django` shape); else None. A root `manage.py` beside a library
    does not count: a library's Django belongs under `server/`.

    The one Python statement of the DJANGO_PROJECT axis's location, as `package_root` is of
    the library's. The two axes are independent: a repo has either, both or neither.
    `racecar.mk` decides the same thing again in Make (`_SERVER_MNG`, `_ROOT_MNG`), on purpose,
    so the build needs nothing but `make`; a coherence test holds the two in step. Where the
    generator WRITES a server (`server/`, always) is a different question, answered by the
    generator.
    """
    if (root / "server" / "manage.py").exists():
        return root / "server"
    if (root / "manage.py").is_file() and not has_library(root):
        return root
    return None


def packages(root: Path) -> list[Path]:
    """Every directory under the package root that holds an `__init__.py`, sorted by name.

    Under a `flat` root, only the named package: the rest of a root is not the package.
    """
    flat = flat_package(root)
    if flat is not None:
        return [flat]
    home = package_root(root)
    if not home.is_dir():
        return []
    return [p for p in sorted(home.iterdir()) if (p / "__init__.py").is_file()]


def module_name(name: str) -> str:
    """A distribution name as the import name it builds: `-` and `.` become `_`."""
    return re.sub(r"[-.]+", "_", name)


def package_dir(root: Path) -> Path | None:
    """The repo's package: the one entry of `packages(root)`.

    With several, the one `[project].name` names (as its import name, `module_name`). The
    repo states which of them it ships, so racecar reads that rather than picking one.
    None when there is none, or several and the name settles nothing; a command then has
    no package to act on.
    """
    found = packages(root)
    if len(found) == 1:
        return found[0]
    name = project_name(root)
    if name is None:
        return None
    named = [p for p in found if p.name == module_name(name)]
    return named[0] if named else None


def not_present(root: Path) -> str:
    """Why a check does not apply to `root`, in the owner's three cases, worded once.

    A package and no Django project: a Django check says "No django server to check". A
    Django project and no package: a package check says "No package to check". Neither:
    "Nothing to check". Every checker that skips for want of its subject says one of these,
    so the same repo is described the same way everywhere.
    """
    package, server = package_dir(root) is not None, server_root(root) is not None
    if package and not server:
        return "No django server to check"
    if server and not package:
        return "No package to check"
    return "Nothing to check"
