#!/usr/bin/env python3
"""check_surface_auth.py — enforce the auth rail (AUTH.md) on a generated surface.

A racecar surface is closed by default: it must carry the auth gate, and every exposed command must
declare a scope. This check fails when either is missing. It bites before the rail is implemented (a
surface with no auth fails it), which is the canon-first point: "closed by default" is a mechanical
fact, not a hope. Run from the project root; a project with no server is a no-op.

Complexity: O(n)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path("docs") / "api" / "manifest.json"


class ConfigError(Exception):
    """A `server/` surface exists that this check cannot read, so it cannot grade it.

    Raised rather than exited, because `findings` runs inside other programs and a
    script that ends its caller's process cannot be imported by one. It is a separate
    answer from an empty finding list: "ungraded" must never borrow the word the
    clean case uses.
    """


def _server_root(repo: Path) -> Path | None:
    """The server dir if this project has a generated surface, else None.

    Absence of `server/` is the only inapplicable case. A `server/` WITHOUT its manifest is
    a different answer, and folding it into this one would be an R-10 breach in the
    checker R-10 names to enforce itself: the surface exists, is reachable, and this
    check cannot see it -- which is not the same fact as "there is nothing to check",
    and must not print the same word. `main` separates them.
    """
    cand = repo / "server"
    return cand if (cand / MANIFEST).exists() else None


def findings(repo: Path) -> list[str]:
    """Return one message per auth-rail violation in the project's server surface.

    Both checks below apply Saltzer & Schroeder's fail-safe-defaults principle (1975):
    access is denied unless explicitly granted, so a missing gate or an unscoped command
    is a violation, never a silent pass.
    """
    server = _server_root(repo)
    if server is None:
        if (repo / "server").is_dir():
            raise ConfigError(
                f"cannot run -- server/ exists but {MANIFEST} does not; the surface "
                "is ungraded, not clean. Regenerate it, or remove server/"
            )
        return []  # no surface to check
    out: list[str] = []
    # 1. Closed by default: the auth gate module must exist (the surface is not anonymous).
    if not (server / "project" / "auth.py").exists():
        out.append(
            "server ships without the auth gate (project/auth.py missing): the surface is "
            "anonymous, not closed by default (AUTH.md)"
        )
    # 2. Default-deny: every exposed command must declare a non-empty scope.
    manifest = json.loads(
        (server / "docs" / "api" / "manifest.json").read_text(encoding="utf-8")
    )
    verticals = manifest.get("verticals")
    if verticals is None:
        out.append(
            'manifest.json has no "verticals" key: a malformed manifest is not '
            "distinguishable from an empty, clean one otherwise (AUTH.md)"
        )
    else:
        for vertical in verticals:
            commands = vertical.get("commands")
            if commands is None:
                out.append(
                    f'vertical {vertical.get("vertical", "?")} has no "commands" key: '
                    f"malformed, not merely empty (AUTH.md)"
                )
                continue
            for command in commands:
                if not command.get("scope"):
                    out.append(
                        f"command {vertical['vertical']}.{command['subcommand']} has "
                        f"no scope: default-deny requires every command to declare "
                        f"one (AUTH.md)"
                    )
    return out


def render(problems: list[str]) -> str:
    """The report `main` prints, built from `findings`. One home for the format.

    Empty when there is nothing to report, so a caller can tell a clean run from a
    dirty one without reading the text.
    """
    return "\n".join(f"check_surface_auth: {problem}" for problem in problems)


def main() -> int:
    """CLI: 0 closed-by-default and every command scoped, 1 on a violation, 2 unable to run.

    Three outcomes, not two. The third -- a real `server/` whose manifest was never
    generated -- must not borrow the word `OK` from the first, or it reports a surface
    as checked-and-clean that has not been read at all.

    0/1/2 is the standard Unix predicate-command exit-status convention (POSIX Utility
    Conventions, IEEE Std 1003.1): success, no-match/failure, usage-or-execution error --
    the same three-way split `grep`/`diff`/`cmp` use.
    """
    repo = Path.cwd()
    try:
        problems = findings(repo)
    except ConfigError as exc:
        print(f"check_surface_auth: {exc}", file=sys.stderr)
        return 2
    if problems:
        print(render(problems), file=sys.stderr)
        return 1
    print(
        "check_surface_auth: OK"
        if _server_root(repo)
        else "check_surface_auth: nothing to check (no server/ surface)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
