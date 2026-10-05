#!/usr/bin/env python3
"""Enforce arch-python/DJANGO.md §2: no cross-module string references in ORM relations.

Reads `[tool.importlinter].root_packages` (or the singular `root_package`, through
the one reader in `check_upward_imports.py`) from the root pyproject, which is the
library pyproject in every shape, and walks each named package. The package
directories are located by globbing the project tree, so a root under `src`,
under `server/`, or at the repo root is found wherever it lives, never assumed from
the shape. It flags any `ForeignKey`, `OneToOneField`, or `ManyToManyField` call
whose target is a cross-module string literal. Three
forms are exempted because they cross no module boundary and so cannot hide
a cycle:

  - `settings.AUTH_USER_MODEL` (an attribute access, not a string).
  - `"self"` — required for self-references inside a class body.
  - An unqualified string whose name matches a class defined at module
    top-level in the same file (a forward reference; reorder the classes
    if you want the symbol form, but it is architecturally inert).

Files under any `migrations/` directory are skipped: Django generates them
mechanically and `app_label.model` strings are how migrations serialize
relationships — they are not hand-written architectural choices.

Finding a violation is a purely static AST concern; classifying it needs
Django's `INSTALLED_APPS`. The static walk runs first, and Django is booted
only when there is a violation to classify, so a clean tree never boots:

  - LIVE: the file's containing app is in `INSTALLED_APPS`. Annotated with
    the file's DAG layer (from `[tool.importlinter].contracts` of type
    `layers`) and, where resolvable, the target app's layer plus an UPWARD
    flag if the target sits above the file in the DAG.
  - NOOP: the file's containing app is NOT in `INSTALLED_APPS`. Django will
    not load these models; the violation is dead code, but listed so the
    reader can decide between deletion and registration.
  - UNCLASSIFIED: a violation was found but `INSTALLED_APPS` could not be
    resolved (no `manage.py`, or `manage.py shell` did not boot). The static
    finding stands and is reported; LIVE/NOOP is simply unavailable.

`INSTALLED_APPS` is obtained via `python manage.py shell` (boots Django so
dynamic settings resolve correctly). A boot that does not complete degrades to
the UNCLASSIFIED report rather than failing the gate: the static graph concern
does not hang on the app booting. For tests or constrained environments, set
`STRING_RELATIONS_INSTALLED_APPS` to a comma-separated override list.

String references defeat the import graph: two models can reference each
other without either import appearing, papering over a cycle that the
arch-python acyclicity axiom makes a Blocker. The DAG annotation makes
the worst variant — upward layer crossings — explicit.

Usage:
    python scripts/check_dj_model_ref_as_string.py

Exits 0 if clean, 1 if any violation is found, 2 on configuration error.

Complexity: O(files × avg file size)
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from check_packaging import detect_shape

# `ConfigError` is the one class both checkers raise when the repo is not set up for them,
# and `root_packages` is the one reader of `[tool.importlinter]`'s root package(s): both
# spellings, the plural winning.
from check_upward_imports import ConfigError, root_packages

RELATION_FIELDS = frozenset({"ForeignKey", "OneToOneField", "ManyToManyField"})

_INSTALLED_APPS_SCRIPT = (
    "import json,sys;"
    "from django.conf import settings;"
    "sys.stdout.write('__INSTALLED_APPS__='+json.dumps(list(settings.INSTALLED_APPS)))"
)


def _load_pyproject(pyproject: Path | None) -> dict[str, Any]:
    # The importlinter config (root_packages, layers) lives in the LIBRARY pyproject,
    # which is the root one in every shape. The server pyproject is deps-only and never
    # carries [tool.importlinter] (PACKAGING.md §"Pyproject rules").
    if pyproject is None or not pyproject.is_file():
        raise ConfigError("pyproject.toml not found")
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))


def _dag_layers(data: dict[str, Any]) -> list[str]:
    """Return layers from the first `[tool.importlinter.contracts]` of type `layers`."""
    contracts = data.get("tool", {}).get("importlinter", {}).get("contracts", [])
    for contract in contracts:
        if contract.get("type") == "layers":
            layers = contract.get("layers", [])
            if isinstance(layers, list) and all(isinstance(x, str) for x in layers):
                return layers
    return []


def _installed_apps(manage_py: Path | None) -> list[str] | None:
    """Resolve INSTALLED_APPS, or None when it cannot be determined. The override
    short-circuits the boot (test / CI). Otherwise Django is booted via `manage.py
    shell` so dynamic settings resolve. A missing `manage.py` or a boot that does not
    complete returns None: the caller degrades to an unclassified report rather than
    failing the gate, since the static graph concern does not depend on the app booting.
    """
    # `if override:`, not `is not None`: an empty-but-set value (a CI export that leaves
    # the variable blank) must fall back to booting Django, not silently produce an
    # empty `installed` list -- every real violation would then misclassify against
    # that empty list as NOOP dead code, with no diagnostic.
    override = os.environ.get("STRING_RELATIONS_INSTALLED_APPS")
    if override:
        return [s.strip() for s in override.split(",") if s.strip()]
    if manage_py is None:
        return None
    try:
        result = subprocess.run(
            [sys.executable, manage_py.name, "shell", "-c", _INSTALLED_APPS_SCRIPT],
            cwd=manage_py.parent,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print(
            "check_dj_model_ref_as_string: manage.py shell did not respond within "
            "60s; reporting violations unclassified",
            file=sys.stderr,
        )
        return None
    if result.returncode:
        print(
            f"check_dj_model_ref_as_string: manage.py shell did not boot "
            f"(exit {result.returncode}); reporting violations unclassified:\n{result.stderr}",
            file=sys.stderr,
        )
        return None
    for line in result.stdout.splitlines():
        if line.startswith("__INSTALLED_APPS__="):
            # str() per element rather than returning json.loads' `Any` straight through:
            # INSTALLED_APPS entries are dotted app labels, and the annotation says so.
            return [str(app) for app in json.loads(line[len("__INSTALLED_APPS__=") :])]
    print(
        "check_dj_model_ref_as_string: could not parse INSTALLED_APPS from manage.py "
        "output; reporting violations unclassified",
        file=sys.stderr,
    )
    return None


def _longest_prefix(dotted: str, candidates: list[str]) -> str | None:
    """Longest prefix match: walk `dotted`'s components from most to least specific
    and return the first one present in `candidates`. Same idiom as CIDR longest-prefix-
    match routing or a trie lookup, applied to dotted module paths (DAG layers,
    INSTALLED_APPS entries) instead of address blocks or trie nodes."""
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in candidates:
            return candidate
    return None


def _resolve_target_app(target: str, installed: list[str]) -> str | None:
    """Match `'app_label.Model'` against INSTALLED_APPS by last-component label."""
    if "." not in target:
        return None
    app_label = target.split(".", 1)[0]
    for entry in installed:
        if entry.split(".")[-1] == app_label:
            return entry
    return None


def _file_to_dotted(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def _target_node(call: ast.Call) -> ast.expr | None:
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg == "to":
            return kw.value
    return None


def _violations(path: Path) -> list[tuple[int, str, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    same_file_classes = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in RELATION_FIELDS:
            continue
        target = _target_node(node)
        if not (isinstance(target, ast.Constant) and isinstance(target.value, str)):
            continue
        value = target.value
        if value == "self":
            continue
        if "." not in value and value in same_file_classes:
            continue
        found.append((node.lineno, func.attr, value))
    return found


def _annotate(
    file_dotted: str,
    target: str,
    installed: list[str],
    layers: list[str],
) -> list[str]:
    notes: list[str] = []
    file_layer = _longest_prefix(file_dotted, layers)
    if file_layer:
        notes.append(f"file layer: {file_layer}")
    target_app = _resolve_target_app(target, installed)
    if target_app is None:
        if "." in target:
            notes.append(
                f"target app label '{target.split('.', 1)[0]}' not in INSTALLED_APPS"
            )
    else:
        target_layer = _longest_prefix(target_app, layers)
        if target_layer and file_layer:
            if layers.index(target_layer) < layers.index(file_layer):
                notes.append(f"target layer: {target_layer} (UPWARD DAG cross)")
            else:
                notes.append(f"target layer: {target_layer}")
        elif target_layer:
            notes.append(f"target layer: {target_layer}")
    return notes


_SKIP_DIRS = frozenset(
    {
        "venv",
        "node_modules",
        "__pycache__",
        "migrations",
        "build",
        "dist",
        "site-packages",
    }
)


def _package_index(project_root: Path) -> dict[str, list[Path]]:
    """Map every directory name in the project to where it occurs on disk, one pruned
    walk. Virtualenvs, caches, build output, migrations, and dotted dirs are skipped.

    Package locations are GLOBBED rather than derived from the shape: `root_packages`
    can sit under any source root (`src` for a library package, `server/` for a
    Django app, the repo root for a standalone server), so the directories are found
    wherever they are instead of assuming a fixed per-shape layout.
    """
    index: dict[str, list[Path]] = {}
    for dirpath, dirnames, _filenames in os.walk(project_root):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        here = Path(dirpath)
        # The repo root is never a root-package directory: root packages live under a
        # source root (src, server/, or a subdir of a standalone server). Skipping
        # it stops a repo named after its package (e.g. `acme/` containing
        # `src/acme/`) from shadowing the real package -- otherwise the shallowest
        # match is the repo root, whose rglob then walks `.venv` and crashes on the
        # first non-UTF-8 dependency file.
        if here == project_root:
            continue
        index.setdefault(here.name, []).append(here)
    return index


def _find_package_dir(
    name: str, index: dict[str, list[Path]], project_root: Path
) -> Path | None:
    """Return the on-disk directory for top-level package `name`, or None. When the
    name occurs more than once, the shallowest path wins: the source-root-level
    package, not a same-named nested subpackage."""
    matches = index.get(name, [])
    if not matches:
        return None
    return min(matches, key=lambda p: len(p.relative_to(project_root).parts))


def _collect_violations(
    roots: list[str], index: dict[str, list[Path]], cwd: Path
) -> list[tuple[str, str, str]]:
    """Static pass: AST-walk each root package and return every forbidden string
    reference as (display head, file dotted name, target), with no Django boot."""
    found: list[tuple[str, str, str]] = []
    for root in roots:
        root_dir = _find_package_dir(root, index, cwd)
        if root_dir is None:
            print(
                f"check_dj_model_ref_as_string: root package '{root}' not on disk; skipping",
                file=sys.stderr,
            )
            continue
        src_root = root_dir.parent
        for path in sorted(root_dir.rglob("*.py")):
            if "migrations" in path.parts:
                continue
            file_dotted = _file_to_dotted(path.relative_to(src_root))
            display = path.relative_to(cwd)
            for lineno, field_name, target in _violations(path):
                head = f"{display}:{lineno}: {field_name} string reference forbidden: '{target}'"
                found.append((head, file_dotted, target))
    return found


def findings(root: Path) -> list[dict[str, str]]:
    """One record per forbidden string reference found under `root`. Prints nothing.

    Keys are `where` — the `file:line: message` head, with any notes appended — and
    `status`, one of `live` (the file's app is in INSTALLED_APPS), `noop` (it is not,
    so Django never loads the model) or `unclassified` (Django did not boot, so the
    two cannot be told apart). An empty list means a clean tree.

    The static walk runs first and Django is booted only to classify what the walk
    found, so a tree with no violations never pays for a boot and a boot that does not
    complete degrades to an unclassified report instead of failing.
    """
    # detect_shape supplies the two genuinely shape-determined things: where the
    # importlinter contract lives (the library pyproject) and where Django boots
    # (manage.py). The package directories named in root_packages are globbed from the
    # tree (`_package_index`), so a root under src, server/, or the repo root is
    # found wherever it actually is.
    shape = detect_shape(root)[0]
    data = _load_pyproject(shape.library_pyproject)
    roots = root_packages(data)
    layers = _dag_layers(data)

    found = _collect_violations(roots, _package_index(root), root)
    if not found:
        return []

    # INSTALLED_APPS resolves dynamic settings, so it needs a Django boot.
    installed = _installed_apps(shape.manage_py)
    if installed is None:
        return [{"where": head, "status": "unclassified"} for head, _d, _t in found]

    records: list[dict[str, str]] = []
    for head, file_dotted, target in found:
        if _longest_prefix(file_dotted, installed) is None:
            records.append({"where": head, "status": "noop"})
            continue
        notes = _annotate(file_dotted, target, installed, layers)
        suffix = " [" + " \u00b7 ".join(notes) + "]" if notes else ""
        records.append({"where": head + suffix, "status": "live"})
    return records


def render(records: list[dict[str, str]]) -> str:
    """The report `main` prints, built from `findings`. One home for the format."""
    headings = {
        "unclassified": (
            "UNCLASSIFIED violations (Django did not boot; LIVE/NOOP unavailable):"
        ),
        "live": "LIVE violations (file's app is in INSTALLED_APPS):",
        "noop": (
            "NOOP modules (file's app is NOT in INSTALLED_APPS \u2014 "
            "Django will not load these models):"
        ),
    }
    blocks: list[str] = []
    for status, heading in headings.items():
        rows = [r["where"] for r in records if r["status"] == status]
        if rows:
            blocks.append(heading + "\n" + "\n".join(f"  {row}" for row in rows))
    return "\n\n".join(blocks)


def main() -> int:
    """Report every forbidden string reference.

    0 when clean, 1 when there are violations, 2 when the repo is not set up for
    the check.
    """
    try:
        records = findings(Path.cwd())
    except ConfigError as exc:
        print(f"check_dj_model_ref_as_string: {exc}", file=sys.stderr)
        return 2
    if not records:
        return 0
    print(render(records))
    return 1


if __name__ == "__main__":
    sys.exit(main())
