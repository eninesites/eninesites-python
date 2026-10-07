"""Walk the `@path` import chain an instruction file declares.

Claude Code expands a line beginning `@` in an instruction file by inlining the file it
names, recursively. That is how racecar's baseline reaches a session: `CLAUDE.md` names
`AGENTS.md`, which names the `shared/` files, the generated axiom list and the change SOP.
The set that arrives is therefore not a list anybody wrote down -- it is the transitive
closure of those lines, and this computes it.

**Why it is here and not beside the checker that needs it.** Two callers want the same
answer and they sit on opposite sides of the delivery boundary:
`lib/graph/_readers.py`'s `read_imports` produces the `baseline` row of the README's
`## Graphs` block, and `racecar.root.lib.selfcheck._baseline` compares it against the load
token. A delivered script may not import the library, so the shared answer belongs on the
delivered side, and `lib/shared/` is where a leaf that more than one noun imports lives.

Stdlib only, which is `lib/shared/`'s own admission rule; the markdown reader is too.

Complexity: O(n) in files reached, each read once.
"""

from __future__ import annotations

from pathlib import Path

from lib.shared import _markdown


def imports(path: Path, root: Path) -> list[Path]:
    """The files `path`'s own `@path` lines name, resolved against `root`, in file order.

    Read through the markdown reader, so a `@` line in the frontmatter or inside a code
    block is not an import: the instruction loader does not expand one there either.
    """
    return [
        (root / line.text[1:].strip()).resolve()
        for line in _markdown.read(path).text()
        if line.text.startswith("@")
    ]


def closure(entry: Path, root: Path) -> tuple[set[Path], list[Path]]:
    """Every file reachable from `entry` by `@path` imports, and the ones that do not exist.

    A chain, not one file's list: reading only `AGENTS.md`'s own `@` lines reports
    `AGENTS.md` itself as undelivered, because a file cannot import itself. Walking from
    the entry point models what the instruction loader actually does.

    The entry file itself counts as reached: it is loaded by being the entry. Paths are
    resolved, so two spellings of one file are one member. A cycle terminates on `seen`
    rather than recursing, which the loader also survives.
    """
    seen: set[Path] = set()
    broken: list[Path] = []
    stack = [entry.resolve()]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        if not current.is_file():
            broken.append(current)
            continue
        stack += [target for target in imports(current, root) if target not in seen]
    return seen, broken


def import_edges(reached: set[Path], root: Path) -> tuple[tuple[str, str], ...]:
    """Every `@path` import as a `(importer, imported)` pair, relative to `root`.

    The graph's edges, not a count of them. An edge whose target is MISSING is still a
    declared edge and is included: a reader that dropped it would report a smaller shape
    than the author wrote, which is the opposite of what a broken link means.

    Sorted, so a rendering is stable across filesystems.
    """

    def rel(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    out: list[tuple[str, str]] = []
    for path in reached:
        if not path.is_file():
            continue
        out += [(rel(path), rel(target)) for target in imports(path, root)]
    return tuple(sorted(out))
