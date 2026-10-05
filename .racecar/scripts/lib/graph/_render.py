"""The marker-delimited `## Graphs` block: the arrows, the table, and the markers.

The arrows are the declared `edges:`, one per line, each with the file that implements
it beneath. This module is delivered, so the block describes whichever repo it runs in:
the arrows come from that repo's `docs/graphs/declared/`, and a repo that declares no
edge gets a sentence saying so rather than another repo's picture.

Complexity: O(G + E) in graphs rendered and declared edges -- one line each.
"""

from __future__ import annotations

from lib.graph._edges import Correspondence
from lib.graph._readers import Graph

GRAPHS_BEGIN = "<!-- BEGIN graphs (generated) -->"
GRAPHS_END = "<!-- END graphs -->"

REGENERATE = "python3 .racecar/scripts/graph.py generate --docs --apply"
"""The one command that refreshes this section. Named in every staleness error."""

ARROW = "──>"
"""The glyph between the two ends of a declared edge."""


def _map_block(graphs: list[Graph], edges: list[Correspondence]) -> list[str]:
    """One line per declared edge, the file that implements it beneath, then the rest.

    Structure only -- no counts, which live in the table. A list needs no authoring, so
    it can be generated for any repo. The ends are padded to one column so the arrows
    line up, and the edges are sorted so a rendering is stable. A graph no edge names is
    listed after them, so leaving it out of the arrows is stated rather than implied by
    absence.
    """
    if not edges:
        return ["No edge between graphs is declared."]
    ordered = sorted(edges)
    width = max(len(src) for src, _dst, _via, _why in ordered)
    lines = ["```text"]
    for src, dst, via, why in ordered:
        lines.append(f"{src.ljust(width)} {ARROW} {dst}")
        lines.append(f"{' ' * (width + len(ARROW) + 2)}{via}: {why}")
    named = {end for src, dst, _via, _why in ordered for end in (src, dst)}
    alone = [g.name for g in graphs if g.name not in named]
    if alone:
        lines += ["", "no edge declared: " + ", ".join(alone)]
    lines.append("```")
    return lines


def _absent_note(graphs: list[Graph]) -> list[str]:
    """What `not declared` means, naming the rows that carry it; else nothing."""
    undeclared = [g.name for g in graphs if g.edges is None]
    if not undeclared:
        return []
    return [
        "`not declared` is not zero: no file declares an edge set for "
        + ", ".join(undeclared)
        + ", so there is none to count.",
        "",
    ]


def render_graphs_section(graphs: list[Graph], edges: list[Correspondence]) -> str:
    """The marker-delimited ``## Graphs`` block.

    `edges` is `inter_edges(root)` for the same repo `graphs` was built from. It is
    passed in rather than read here, so this module renders data and no caller can
    render the table without deciding what the arrows are.
    """
    rows = [
        "| Graph | Nodes | Edge | Edges | Derived from |",
        "|---|---|---|---|---|",
    ]
    for g in graphs:
        count = "not declared" if g.edges is None else str(g.edges)
        rows.append(
            f"| {g.name} | {g.nodes} {g.node} | {g.edge} | {count} | `{g.source}` |"
        )
    return "\n".join(
        [
            GRAPHS_BEGIN,
            "## Graphs",
            "",
            f"<!-- GENERATED — DO NOT EDIT between the markers. Regenerate:  {REGENERATE} -->",
            "",
            "This repo declares its graphs in `docs/graphs/declared/`. Counts below",
            "are read from the artifact that owns each one, so they cannot drift from",
            "it; each arrow is an `edges:` entry in a declaration and names the file",
            "that implements it.",
            "",
            *_map_block(graphs, edges),
            "",
            *rows,
            "",
            *_absent_note(graphs),
            GRAPHS_END,
        ]
    )


def narrow(fresh: list[Graph], existing: str, name: str) -> list[Graph]:
    """`fresh` with every graph EXCEPT `name` replaced by what `existing` already claims.

    What `--graph <name>` means when it writes. Each row is read from its own source --
    the import graph from `pyproject.toml`, the skill graph from every `SKILL.md` -- and
    no row is derived from another, so refreshing one and leaving the rest is honest
    rather than half-done. The others stay exactly as stale as they already were, and the
    run did not make them so.

    A row the block does not yet carry has nothing to preserve, so it is taken fresh. That
    is not a special case: "what the README already claims" is empty for it.
    """
    claimed = {
        line.split("|")[1].strip(): line
        for line in existing.splitlines()
        if line.startswith("| ") and line.count("|") >= 6
    }
    kept: list[Graph] = []
    for graph in fresh:
        if graph.name == name or graph.name not in claimed:
            kept.append(graph)
            continue
        cells = [c.strip() for c in claimed[graph.name].split("|")[1:-1]]
        nodes, _, node_word = cells[1].partition(" ")
        kept.append(
            Graph(
                graph.name,
                node_word,
                cells[2],
                int(nodes) if nodes.isdigit() else graph.nodes,
                None if cells[3] == "not declared" else int(cells[3]),
                cells[4].strip("`"),
            )
        )
    return kept


def graph_names(graphs: list[Graph]) -> list[str]:
    """Every declared graph's name, for `--graph`'s error message and its choices."""
    return [g.name for g in graphs]
