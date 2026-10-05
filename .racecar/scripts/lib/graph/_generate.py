"""The `generate` verb: project this repo's graphs into the README's `## Graphs` block.

**Counts are derived; the shape is authored.** Every count comes from the artifact that
already owns it, and which graph feeds which is authored in each graph node's `edges:` and
then checked: every edge names the file that implements it, and a missing file is a
finding. `scripts/graph.py` carries the full argument, beside the parser this verb is
reached through.

Part of `lib.graph`; `scripts/graph.py` parses the command line and calls `main`. `run`
grades the declarations and either reads the graphs (`--json`) or renders, compares and,
under `--apply`, writes the block; it returns what it found as a record and raises
`Refused` for every reason it declines. `renderer.text` is how the record reads.

Exit: 0 current or rewritten, 1 stale under `strict`, any author error in `docs/graphs/`
or a declared graph whose source is there and could not be read, 2 a usage error.

Complexity: O(n) in tracked markdown plus one CLI-tree audit; the audit dominates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lib import not_a_command
from lib.graph._declared import declarations, malformed, unresolvable
from lib.graph._edges import edge_findings, inter_edges
from lib.graph._readers import ReadError, build, read_all
from lib.graph._render import (
    GRAPHS_BEGIN,
    GRAPHS_END,
    graph_names,
    narrow,
    render_graphs_section,
)
from lib.graph.renderer import text
from lib.shared._readme_block import is_stale, splice
from lib.shared._root import find_repo_root


class Refused(Exception):
    """A reason `generate` declines: the lines it says on stderr, and the exit code."""

    def __init__(self, lines: list[str], code: int) -> None:
        super().__init__("\n".join(lines))
        self.lines = lines
        self.code = code


def _refuse(
    root: Path | None,
    readme: Path,
    *,
    docs: bool,
    path: Path | None,
    as_json: bool,
    output: Path | None,
) -> None:
    """Every reason this verb declines before it reads anything, raised as `Refused`.

    Separated from the work so `run` states the run and this states the refusals --
    the alternative was one function whose exits outnumbered its steps.
    """
    if not docs:
        raise Refused(
            [
                "graph generate: say what to generate -- --docs is the only artefact "
                "this verb knows"
            ],
            2,
        )
    if root is None:
        raise Refused(["graph: no repo root found"], 1)
    if path is not None and path.resolve() != readme.resolve():
        # Refused BY NAME rather than silently skipped: a caller who narrowed to the wrong
        # path has made a mistake, and a run that reports success having written nothing
        # is the same defect as writing the wrong thing.
        raise Refused(
            [
                f"graph generate: {path} declares no producer for this command; "
                f"today {readme.name} is the only artifact it writes"
            ],
            2,
        )
    if output is not None and not as_json:
        # A usage error rather than an ignored flag. The prose report is a verdict for a
        # person at a terminal; there is no non-JSON artifact a file could hold, so a run
        # that accepted `-o` and wrote nothing would report success having done nothing.
        raise Refused(
            [
                "graph generate: --output requires --json; there is no non-JSON report to "
                "write to a file"
            ],
            2,
        )


def _graphs(root: Path, only: str | None) -> list[dict[str, Any]]:
    """Every declared graph: its authored shape, its nodes, and its edges.

    Nodes and edges in full rather than their sizes, because the sizes are what the prose
    table already shows and a machine-readable rendering that carried only them would be
    the same reduction in another syntax. `edges: None` keeps its meaning -- the set cannot
    be derived -- and is distinct from `[]`.
    """
    reads = read_all(root)
    rows = []
    for data in declarations(root):
        name = str(data["name"])
        if only is not None and name != only:
            continue
        read = reads.get(name)
        rows.append(
            {
                "name": name,
                "node": data["node"],
                "edge": data["edge"],
                "source": data["source"] if read is not None else "absent",
                "reader": data["reader"],
                "nodes": list(read.nodes) if read is not None else [],
                "edges": (
                    None
                    if read is None or read.edges is None
                    else [list(e) for e in read.edges]
                ),
            }
        )
    return rows


def _grade(root: Path) -> list[str]:
    """Every author error in `docs/graphs/`, before anything reads a graph.

    Three questions, each about the DECLARATIONS rather than about the graphs they
    describe: `edge_findings` asks whether each declared inter-graph edge names a file
    that exists, `malformed` whether each declaration carries the fields its kind
    requires, and `unresolvable` whether each `reader:` names code that is there.
    """
    declared = declarations(root)
    return edge_findings(root) + malformed(declared) + unresolvable(declared)


def _write_block(
    root: Path, readme: Path, *, graph: str | None, apply: bool
) -> dict[str, bool]:
    """The prose path: render the `## Graphs` block, compare it, and write it under
    `apply`.

    Split from `run` so that function states the run -- refuse, grade, render -- while
    this one owns the block's own verdict: `stale` whether the block differed, `wrote`
    whether it was rewritten, and `applied` whether writing was asked for.
    """
    graphs = build(root)
    if graph is not None:
        if graph not in graph_names(graphs):
            raise Refused(
                [
                    f"graph generate: no graph named {graph!r}; this repo declares "
                    + ", ".join(repr(n) for n in graph_names(graphs))
                ],
                2,
            )
        existing = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        graphs = narrow(graphs, existing, graph)

    section = render_graphs_section(graphs, inter_edges(root))
    stale = is_stale(readme, GRAPHS_BEGIN, GRAPHS_END, section)
    wrote = apply and stale
    if wrote:
        existing = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        readme.write_text(
            splice(existing, GRAPHS_BEGIN, GRAPHS_END, section), encoding="utf-8"
        )
    return {"stale": stale, "wrote": wrote, "applied": apply}


def run(
    root: Path | None = None,
    *,
    docs: bool = False,
    apply: bool = False,
    path: Path | None = None,
    graph: str | None = None,
    as_json: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    """`generate --docs`: grade the declarations, then read the graphs or render the block.

    `root` absent is the repo holding the working directory. Under `as_json` the record is
    `{"graphs": [...]}`, one row per declared graph, and nothing is written -- a
    machine-readable dump of what is there is not a claim about whether it is right. Without
    it the record is the block's verdict, `{stale, wrote, applied}`, and `apply` rewrites a
    stale block. `output` is where `main` writes the JSON; it is read here only to refuse it
    without `as_json`. Raises `Refused` for every reason the verb declines.
    """
    root = root if root is not None else find_repo_root(Path.cwd())
    readme = (root or Path.cwd()) / "README.md"
    _refuse(root, readme, docs=docs, path=path, as_json=as_json, output=output)
    assert root is not None

    findings = _grade(root)
    if findings:
        raise Refused([f"graph: {finding}" for finding in findings], 1)

    try:
        if as_json:
            return {"graphs": _graphs(root, graph)}
        return _write_block(root, readme, graph=graph, apply=apply)
    except ReadError as exc:
        # Refused rather than rendered: a row built from a graph nobody could read would
        # print a count the tree does not have, and `absent` would say the source is
        # missing when it is there and broken. Nothing is written.
        raise Refused([f"graph: {exc}"], 1) from exc


def main(
    root: Path | None = None,
    *,
    docs: bool = False,
    apply: bool = False,
    strict: bool = False,
    path: Path | None = None,
    graph: str | None = None,
    as_json: bool = False,
    output: Path | None = None,
) -> int:
    """Run `generate --docs` and print its record: the graphs as JSON, or the verdict.

    `--apply` and `--strict` COMPOSE: the block is rewritten AND the run exits non-zero,
    because the tree was wrong when it started. That is the formatter convention pre-commit
    already relies on, and it is what stops a caller having to keep one run's output for
    the next.
    """
    try:
        record = run(
            root,
            docs=docs,
            apply=apply,
            path=path,
            graph=graph,
            as_json=as_json,
            output=output,
        )
    except Refused as refused:
        for line in refused.lines:
            print(line, file=sys.stderr)
        return refused.code

    if as_json:
        payload = json.dumps(record["graphs"], indent=2, sort_keys=False)
        if output is None:
            print(payload)
            return 0
        output.write_text(payload + "\n", encoding="utf-8")
        print(text.wrote(output))
        return 0

    if record["stale"] and not record["wrote"]:
        print(text.stale(), file=sys.stderr)
    else:
        print(text.generate(record))
    return 1 if (record["stale"] and strict) else 0


if __name__ == "__main__":
    not_a_command()
