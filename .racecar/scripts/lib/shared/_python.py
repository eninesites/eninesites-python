"""Which Python runs a repo's own code: its virtualenv's, where it has one.

A probe that imports a repo's code (a checker reading its CLI tree, a transcript running its
commands) must import against the repo's own dependencies, not racecar's, or a package the
repo installed reads as missing. One home for that choice, so every probe makes it the same
way.
"""

from __future__ import annotations

import sys
from pathlib import Path


def repo_python(root: Path) -> str:
    """The repo's own interpreter, where it has a virtualenv; else the one running this.

    Looked for in the order `racecar.mk` finds the venv: `.venv`, `venv`, then `../venv`.
    """
    for venv in (".venv", "venv", "../venv"):
        candidate = root / venv / "bin" / "python"
        if candidate.is_file():
            return str(candidate)
    return sys.executable
