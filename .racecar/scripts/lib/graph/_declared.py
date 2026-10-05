#!/usr/bin/env python3
"""The graphs a repo DECLARES, read from `docs/graphs/`.

A generator that ships its author's list of graphs projects the wrong repo's structure
into every tree it reaches. The readers are code -- counting import-linter contracts is
not something a declaration can express -- but WHICH graphs exist, and how they connect,
is a fact about the repo being read.

A repo that declares none gets an empty answer, which is the same scoping rule every other
delivered kind follows.

Complexity: O(G) in declared graphs -- one frontmatter parse and one import each.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable

# The flat delivered checkers are siblings in `scripts/`, which `lib/__init__.py`
# puts on the path before any module here is imported.
from lib.shared import _frontmatter

#: Where a repo declares its graphs: the DATA tier of `docs/graphs/`, beside the ontology and
#: topology that say what an instance must carry. Not under `docs/lexicon/`, which holds the
#: WORDS racecar fixes -- a graph is not a word, and filing one there would put it in
#: the noun namespace where `graph` is `python -m racecar.graph`.
DECLARED_REL = "docs/graphs/declared"

#: What `kind: graph` requires, mirrored from the delivered kind node so a malformed
#: declaration is reported rather than raising a KeyError three frames away.
REQUIRED = ("node", "edge", "source", "reader")


def declarations(root: Path) -> list[dict[str, Any]]:
    """Every `kind: graph` node under `root`, in declaration order by name.

    Absent is a reported state, not an error: a repo with no `docs/graphs/` has no
    graphs to project and gets an empty list, exactly as one with no lexicon gets an empty
    lexicon. Sorted by name so a rendering is stable across filesystems.
    """
    directory = root / DECLARED_REL
    if not directory.is_dir():
        return []
    found = []
    for node in sorted(directory.glob("*.md")):
        if node.name == "README.md":
            continue
        data = _frontmatter.load(node)
        if data.get("kind") != "graph":
            continue
        data["_node"] = node
        found.append(data)
    return found


def malformed(declared: list[dict[str, Any]]) -> list[str]:
    """Every declaration missing a field its kind requires, as findings.

    Checked here rather than left to the ontology gate because this reader runs in repos
    that may never run that gate, and a missing `reader:` would otherwise surface as an
    import error naming nothing the author wrote.
    """
    return [
        f"{data['_node'].name}: `kind: graph` requires `{field}:` and it is absent"
        for data in declared
        for field in REQUIRED
        if not data.get(field)
    ]


def reader_problem(reader: str) -> str | None:
    """Why `resolve` would fail on this value, or None when it would not.

    ONE home for the question, asked in two places: `unresolvable` turns it into a finding
    for the caller that grades declarations, and `build` skips the row rather than letting
    the import machinery raise from inside a loop.

    The same reasoning as `REQUIRED` above, one step further in. That constant exists "so a
    malformed declaration is reported rather than raising a KeyError three frames away",
    and it covers a field that is ABSENT. A field whose value names code that is not there
    is the same class of author error: unchecked, it surfaces as an `AttributeError`
    from inside `importlib`, naming the symbol but not the node that declared it, and
    killing the whole projection rather than the one row.
    """
    module, _, function = reader.partition(":")
    if not function:
        return f"`reader: {reader}` is not `module:function`"
    try:
        found = importlib.import_module(module)
    except ImportError as exc:
        return (
            f"`reader: {reader}` names module `{module}`, which does not import ({exc})"
        )
    if not hasattr(found, function):
        return (
            f"`reader: {reader}` names `{function}`, which `{module}` does not define"
        )
    return None


def unresolvable(declared: list[dict[str, Any]]) -> list[str]:
    """Every declaration whose `reader:` names code that is not there, as findings.

    Only declarations that HAVE a reader are asked, because `malformed` already reports a
    missing one and two findings for one absence reads as two defects.
    """
    out = []
    for data in declared:
        reader = str(data.get("reader") or "")
        if not reader:
            continue
        problem = reader_problem(reader)
        if problem is not None:
            out.append(f"{data['_node'].name}: {problem}")
    return out


def resolve(reader: str) -> Callable[[Path, dict[str, Any]], Any]:
    """`module:function` to the callable it names, as `reader(root, declaration)`.

    The declaration is the second argument, which is what keeps a reader named for its
    MECHANISM rather than for one graph: `source:` and its `#fragment` come from the node,
    so `read_pnode` serves every containment graph and `read_jsonl` every row-per-node one.
    See [`READERS.md`](../../../docs/graphs/READERS.md).

    Explicit rather than found by convention from `name:`. A convention that resolves
    silently resolves WRONGLY just as silently, and the failure mode there is a graph
    quietly reporting zero rather than an error naming the declaration that is wrong.
    """
    module, _, function = reader.partition(":")
    if not function:
        raise ValueError(f"reader must be `module:function`, got {reader!r}")
    found: Callable[[Path, dict[str, Any]], Any] = getattr(
        importlib.import_module(module), function
    )
    return found
