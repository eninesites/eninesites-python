"""Project shape detection (PACKAGING.md "Scope")."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from ._findings import Finding
from ._root import flat_package

#: The two shapes where a library sits beside a `server/` Django project. A check about the
#: server tree, its pyproject or its lockfile asks this, never one name of the two.
LIBRARY_WITH_SERVER = ("src+server", "flat+server")


@dataclasses.dataclass(frozen=True)
class Shape:
    """The project shape as PYTHON_LIBRARY x DJANGO_PROJECT.

    `has_library` (a library package with its pyproject at repo root) and `has_django`
    are the two axes. The library axis is split by WHERE the package root is:

      - `src/<pkg>` — the src layout. `flat_package` is None.
      - `<pkg>` at the repo root, named by `[project].name` — the flat layout, Python's
        other packaging layout. `flat_package` is that folder. Identical to the src
        layout in every way except where the package root is.

    The Django axis is split by WHERE `manage.py` lives:

      - `server/manage.py` — racecar's server shell, a Django surface wrapping the
        library (or standalone). Marked here by `django_root == False`.
      - a ROOT `manage.py` — the `django-admin startproject` canon: a standalone
        Django site with no library to wrap. Marked by `django_root == True`.

    Recognizing both is deliberate: each is its framework's own default, so racecar must
    classify it, not reject it. racecar may *prefer* `src/` and `server/` for what it
    scaffolds, but preference is not the same as recognition (SG2).

    `name` is the derived label over this product, not the primitive — compare the
    booleans when the axis is what matters.
    """

    has_library: bool
    has_django: bool
    library_pyproject: Path | None  # the root pyproject (None only when absent)
    server_pyproject: Path | None  # the server pyproject (only Shape src+server)
    manage_py: Path | None = (
        None  # located Django manage.py (server/ or root), else None
    )
    django_root: bool = (
        False  # Django marked by a ROOT manage.py (startproject site), not server/
    )
    flat_package: Path | None = None  # the library at the repo root (the flat layout)

    @property
    def source_root(self) -> str | None:
        """Where this shape's Python source lives, relative to the repo root.

        The same value `racecar.mk` computes as `SRC`, so the audit and the build cannot
        disagree about where a project's source lives. `src` for the two src-layout
        shapes, the package itself for the two flat ones (in `src` the source root holds
        only the package, and at the root the package is its equivalent), `server` for the
        standalone Django project, `.` for the startproject site, and None when there is
        no shape to speak of.
        """
        if self.flat_package is not None:
            return self.flat_package.name
        return {
            "src": "src",
            "src+server": "src",
            "server": "server",
            "django": ".",
        }.get(self.name)

    @property
    def name(self) -> str:
        """The derived label for this shape.

        Not a pure function of the two booleans: the library splits by package root into
        `src` and `flat`, and the (no-library, Django) cell splits by manage.py location
        into `server` (server/manage.py) and `django` (a startproject site).
        """
        layout = "flat" if self.flat_package is not None else "src"
        if not self.has_django:
            return layout if self.has_library else "unknown"
        if self.django_root:
            return "django"  # startproject site (root manage.py), no library
        return f"{layout}+server" if self.has_library else "server"


def detect_shape(root: Path) -> tuple[Shape, list[Finding]]:
    """Resolve the project shape from what is on disk (PACKAGING.md "Scope").

    Pure filesystem inference, the same decision `racecar.mk` makes in Make so the build
    is self-contained; a coherence test asserts the two classify every fixture identically.
    Shape is governed by what is, not by any declared value: there is no shape entry to read.

    Shape is PYTHON_LIBRARY x DJANGO_PROJECT. The library is `src/<pkg>`, or the package
    `[project].name` names at the repo root when there is no `src/` (`flat_package`, the
    one home for that rule). The Django axis is marked by a `manage.py` and split by its
    location -> a derived label:

      - (src library, no Django)   -> `src`         — library only.
      - (flat library, no Django)  -> `flat`        — library only, package at the root.
      - (library, server/manage)   -> `src+server` / `flat+server` — a server wrapping it.
      - (no library, server/manage)-> `server`      — racecar's server-shell Django project.
      - (no library, root manage)  -> `django`      — the django-admin startproject canon:
                                                      a standalone Django site.
      - (no library, no Django)    -> `unknown`     — a bare pyproject (neither axis); a
                                                      finding, not silently treated as `src`.

    The root `pyproject.toml` is the shared shell, the precondition for any shape; without
    it the repo is unclassifiable. Django is marked by a `manage.py`, never a bare `server/`.
    A root `manage.py` beside a library is NOT the `django` shape — a library's Django
    belongs under `server/` (the +server convention), so that case degrades to the
    library reading rather than minting a new cell. A startproject site has no
    `[project].name` naming a root package, so it stays `django`. TODO: library-axis
    polymorphism — the `{packages,pypkg}/<pkg>/src/<pkg>` workspace form — is a downstream
    addition.
    """
    root_py = root / "pyproject.toml"
    src_dir = root / "src"
    server_py = root / "server" / "pyproject.toml"
    server_manage = root / "server" / "manage.py"
    root_manage = root / "manage.py"

    if not root_py.exists():
        return (
            Shape(False, False, None, None),
            [
                Finding(
                    "Blocker",
                    "pyproject.toml",
                    "missing-file",
                    "no pyproject.toml found at repo root; cannot determine project shape",
                )
            ],
        )

    flat = flat_package(root)  # the library at the root, when there is no src/
    has_library = src_dir.is_dir() or flat is not None  # PYTHON_LIBRARY axis
    has_django_server = server_manage.exists()  # DJANGO_PROJECT axis, server-shell form
    # Startproject Django (the django-admin canon): a root manage.py, no library and no
    # server/manage.py. A library repo's Django belongs under server/, so a root manage.py
    # beside a library is not this shape.
    has_django_root = (
        root_manage.is_file() and not has_library and not has_django_server
    )
    has_django = has_django_server or has_django_root

    findings: list[Finding] = []
    if not (has_library or has_django):
        findings.append(
            Finding(
                "Blocker",
                "pyproject.toml",
                "no-shape",
                "root pyproject.toml present but none of a src/ library, a root "
                "package named by [project].name, a server/ Django project, or a root "
                "manage.py Django site; not a recognized shape",
            )
        )
    return (
        Shape(
            has_library=has_library,
            has_django=has_django,
            library_pyproject=root_py,
            server_pyproject=(
                server_py
                if (has_library and has_django_server and server_py.exists())
                else None
            ),
            manage_py=(
                server_manage
                if has_django_server
                else (root_manage if has_django_root else None)
            ),
            django_root=has_django_root,
            flat_package=flat,
        ),
        findings,
    )
