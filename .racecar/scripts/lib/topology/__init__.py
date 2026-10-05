"""The topology: declare a corpus's tier shape, walk the corpus by it, and grade the walk.

`scripts/topology.py` is one command line over this and `racecar.graph.topology` is another,
so a caller imports what it needs instead of loading a script by path to reach a function.

Delivered WHOLE into an adopter's `.racecar/scripts/lib/topology/`, the same way `lib.lexicon`
is: a package survives delivery exactly as a single file does.

One verb, one module, with a `main` that `scripts/topology.py` dispatches to:

  `_check`  gate a corpus's tier shape against the topology it declares

and beneath it `_walk`, the one chain the verb needs: the declaration, the walk that needs
the declaration, and the grade that needs the walk (`check`, the graph and its errors,
printing nothing). `lib.ontology` and `lib.graph` import the walk from there.

Public names are re-exported here so `from lib.topology import load` works.

Complexity: O(1) -- re-exports only
"""

from __future__ import annotations

from lib.topology._walk import (
    META_ROOT,
    ROOT,
    TOPOLOGY_DIRNAME,
    TOPOLOGY_FILENAME,
    Tier,
    Topology,
    check,
    load,
    load_topology_spec,
    project,
    resolve,
    structural_findings,
)

__all__ = [
    "META_ROOT",
    "ROOT",
    "TOPOLOGY_DIRNAME",
    "TOPOLOGY_FILENAME",
    "Tier",
    "Topology",
    "check",
    "load",
    "load_topology_spec",
    "project",
    "resolve",
    "structural_findings",
]
