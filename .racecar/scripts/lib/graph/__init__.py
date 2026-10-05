"""The graph projection: read this repo's graphs, and render them as one block.

`scripts/graph.py` is one command line over this and `racecar.graph.api.generate` is
another, so a caller imports what it needs instead of loading a script by path.

Delivered WHOLE into an adopter's `.racecar/scripts/lib/graph/`, the same way
`lib.lexicon` is: a package survives delivery exactly as a single file does.

One verb, one module, each with a `run` that returns the verb's record and a `main` that
`scripts/graph.py` dispatches to:

  `_generate`     project the declared graphs into the README's `## Graphs` block
  `_check`        gate the corpus: topology and ontology
  `_materialize`  render the tree, or one view of it
  `_perimeter`    derive the real declaration set from the delivered checkers
  `_build`        materialize a graph at a destination from source material

and `renderer.text`, every line those verbs print, rendered from their records. The
topology and the ontology a graph is gated against are `lib.topology` and `lib.ontology`.

The projection beneath `_generate`, bottom up -- each imports only from the ones above it
in this list:

  `_readers`  one reader per graph; every count read from the artifact that owns it
  `_edges`    the authored arrows between graphs, closed against the tree
  `_render`   the marker-delimited block: the picture, the table, the markers

Public names are re-exported here so `from lib.graph import build` works.

Complexity: O(1) -- re-exports only
"""

from __future__ import annotations

from lib.graph._edges import edge_findings, inter_edges
from lib.graph._readers import Graph, build
from lib.graph._render import (
    GRAPHS_BEGIN,
    GRAPHS_END,
    REGENERATE,
    render_graphs_section,
)

__all__ = [
    "GRAPHS_BEGIN",
    "GRAPHS_END",
    "Graph",
    "REGENERATE",
    "build",
    "edge_findings",
    "inter_edges",
    "render_graphs_section",
]
