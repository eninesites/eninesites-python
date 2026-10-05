#!/usr/bin/env python3
"""The arrows BETWEEN graphs, read from the declarations, and the check that closes them.

AUTHORED, because no predicate recovers "this checker compares these two structures" from
source. Closed against the tree by `edge_findings`, so a claim whose implementation was
deleted fails rather than lingering as a caption.

**Correspondence, not derivation.** A checker comparing two structures is not one structure
building the other, so these are their own `edges:` field rather than a borrowing of a
derivation edge. Conflating them would put a build order on a relationship that has none.

They point BACKWARD, like every other edge in a racecar graph: a node says what it is
checked AGAINST, never what checks it. The forward view is computed by walking, which is
the rule `pnode` already sets and the reason no node carries a list of its dependents.

Complexity: O(E) in declared edges -- one stat per claimed implementation.
"""

from __future__ import annotations

from pathlib import Path

# The flat delivered checkers are siblings in `scripts/`, which `lib/__init__.py`
# puts on the path before any module here is imported.
from lib.graph._declared import declarations

#: One declared correspondence: `(from, to, implementation, what it asserts)`.
Correspondence = tuple[str, str, str, str]


def inter_edges(root: Path) -> list[Correspondence]:
    """Every declared correspondence as `(from, to, implementation, what it asserts)`.

    Flipped on the way out: a node declares what it is checked against, and a reader of the
    picture wants the arrow the other way round. One direction is declared and the other is
    derived, which is the whole reason only one of them can go stale.
    """
    return [
        (
            str(edge["against"]),
            str(data["name"]),
            str(edge["via"]),
            str(edge["asserts"]),
        )
        for data in declarations(root)
        for edge in data.get("edges", []) or []
    ]


def edge_findings(root: Path) -> list[str]:
    """Every declared inter-graph edge whose implementing file is missing.

    This is what stops the authored half from being unfalsifiable. The claim "these two
    structures are connected, by this file" is exactly as checkable as the file existing,
    so that much is checked.
    """
    return [
        f"{src} -> {dst}: {impl} does not exist"
        for src, dst, impl, _why in inter_edges(root)
        if not (root / impl).exists()
    ]
