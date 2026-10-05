"""One reader per graph: its nodes, its edges, and where both were read from.

A reader returns the GRAPH, not a measurement of it. Every count in the README is `len()`
of a collection this produced, so a number there cannot disagree with the thing it
describes -- it is the same object.

Returning the edge set rather than its size is also what lets one invariant run against
every graph. Acyclicity is P-01, racecar's root axiom, and a reader that yields
`(src, dst)` pairs gives every graph one input for it.

Complexity: O(n) in tracked markdown plus one CLI-tree audit; the audit dominates.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The flat delivered checkers are siblings in `scripts/`, which `lib/__init__.py`
# puts on the path before any module here is imported.
from check_doc_graph import graph_edges, in_scope
from lib.graph._declared import declarations, reader_problem, resolve
from lib.lexicon._audit import cli_tree
from lib.lexicon._nodes import LexiconError
from lib.shared._files import repo_files
from lib.shared._imports import closure, import_edges
from lib.shared._root import package_dir, package_root
from lib.topology import _walk

#: One edge: `(from, to)`, both node identifiers as that graph names them.
Edge = tuple[str, str]


class ReadError(Exception):
    """A reader reached its source and could not read it.

    Distinct from a reader returning None, which means the source is not there, so a
    broken tree never reads as a missing one.
    """


@dataclass(frozen=True)
class Read:
    """What a reader returns: one graph's nodes and edges, or None when its source is absent.

    `edges is None` means the edge set CANNOT BE DERIVED, which is not the same as empty.
    The skill graph is the case: 34 `SKILL.md` files cross-reference each other in prose
    links nothing declares, so the honest answer is a node set and a stated absence. An
    empty tuple is a real, derived zero -- the capability graph's `requires` column exists
    and no row has used it.

    The distinction is load-bearing: an edge-based invariant can RUN against `()` and
    must refuse `None`, so a reader that guessed zero would make an unrunnable check
    report a pass.
    """

    nodes: tuple[str, ...]
    edges: tuple[Edge, ...] | None


@dataclass(frozen=True)
class Graph:
    """One graph as the README renders it: the authored shape plus the derived sizes.

    Counts rather than collections, because this is the rendering type. `edges` is `None`
    for a graph whose edge set cannot be derived -- see `Read`.
    """

    name: str
    node: str
    edge: str
    nodes: int
    edges: int | None
    source: str


def _rel(path: Path, root: Path) -> str:
    """`path` as a repo-relative posix string, or absolute when it sits outside `root`."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _lines(path: Path) -> list[str]:
    """Non-empty lines of a jsonl file; `[]` when it is absent."""
    if not path.is_file():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _pnode_graph(nodes: list[Path], root: Path) -> Read:
    """A `pnode` containment graph over `nodes`: one edge per declared parent.

    ONE HOME for the containment walk, shared by the two graphs whose declared edge is
    `pnode` containment -- the doc graph over every in-scope `*.md`, and the nomenclature
    graph over `docs/lexicon/`.

    `graph_edges` is `check_doc_graph`'s OWN frontmatter parser, imported rather than
    reimplemented: it handles the flow form, the block form and a bare scalar, and a doc
    may name several parents or none.
    """
    edges: list[Edge] = []
    for doc in nodes:
        parents, _see_also = graph_edges(
            doc.read_text(encoding="utf-8", errors="ignore")
        )
        for parent in parents or []:
            edges.append((_rel(doc, root), _rel(Path(parent), root)))
    return Read(tuple(sorted(_rel(p, root) for p in nodes)), tuple(sorted(edges)))


def _source(data: dict[str, Any]) -> tuple[str, str]:
    """A declaration's `source:` split into a path and an optional `#fragment`.

    ONE convention, so a reader is named for its MECHANISM and never for a graph. The
    fragment says what WITHIN the named file to read, which is the only thing that
    otherwise forces a per-graph function:

        pyproject.toml#tool.importlinter.contracts    a dotted table path
        surface.jsonl#cli>requires                    a node key, then an edge key
        racecar-manifest.jsonl#dest                   a node key, no edges

    Explicit rather than inferred. A reader that guessed which key held the node id would
    guess wrongly just as silently, and the failure is a graph reporting zero.
    """
    path, _, fragment = str(data.get("source") or "").strip().partition("#")
    return path.rstrip("/"), fragment


def read_pnode(root: Path, data: dict[str, Any]) -> Read | None:
    """Any `pnode` containment graph, its corpus named by the declaration's `source:`.

    ONE reader for every graph whose edge is `pnode` containment, because they differ only
    in which files they collect: the doc graph, the nomenclature graph and the graph
    manifest.

    `source:` is what selects the corpus, which is what the delivered kind already says it
    is: "where the graph is read from: a path, or a glob". A directory means every `*.md`
    beneath it; anything else is a glob against the repo. So declaring a new containment
    graph is a node and no code.

    `in_scope` is applied either way -- it is `check_doc_graph`'s own predicate for "a doc
    this repo grades", and a corpus reader that counted files the repo does not grade would
    report a graph nothing checks.
    """
    source, _ = _source(data)
    if not source:
        return None
    if (root / source).is_dir():
        found = sorted((root / source).rglob("*.md"))
    else:
        found = [p for p in repo_files(root, "*.md") if p.match(source)]
    docs = [p for p in found if in_scope(p, root)]
    if not docs:
        return None
    return _pnode_graph(docs, root)


def read_files(root: Path, data: dict[str, Any]) -> Read | None:
    """Files matching the declaration's `source:`, with no derivable edge set.

    For a graph whose nodes are files and whose edges nothing declares. The skill graph is
    the case: `SKILL.md` bodies cross-reference each other in prose links, so `edges` is
    `None` -- cannot be derived, which is not zero.
    """
    source, _ = _source(data)
    if not source:
        return None
    pattern = source.rsplit("/", 1)[-1]
    found = [p for p in repo_files(root, pattern) if p.is_file() and p.match(source)]
    if not found:
        return None
    return Read(tuple(sorted(_rel(p, root) for p in found)), None)


def read_argparse(root: Path, data: dict[str, Any]) -> Read | None:
    """A command tree, introspected from the `__main__.py` modules under `source:`.

    Named for the mechanism: any repo whose CLI follows the `commands()`/`subcommands()`
    contract can declare this reader. The collector is a COMPUTATION rather than a format
    -- no glob produces a command tree, a program has to import the modules and read the
    live argparse objects -- which is why this one cannot collapse into `read_pnode`.

    An edge is a `subcommands()` entry: node to verb, not parent to child. The containment
    edges are a different relation and a graph declaring this reader does not get them.

    `source:` names the package root to walk (`src/racecar/**/__main__.py`); its glob tail
    is stripped, since the audit walks a directory rather than matching a pattern. It is
    resolved against `root` and nowhere else: a declared directory that is not there is
    `absent`, like every other reader's missing source, never a cue to audit whatever
    `src/` the working directory happens to hold.
    """
    source, _ = _source(data)
    top = source.split("*", 1)[0].rstrip("/") or "src"
    target = root / top
    if not target.is_dir():
        return None
    tree = _audit(root, target)

    # A `Node` is `dict[str, Any]` and its children live under `children`, not `commands`
    # -- `commands` is the declared (name, blurb) list. `getattr` on a dict returns None
    # for both, so a walk using it stops at one node without erroring. `render_tree` is
    # the authority on how a node descends.
    def walk(node: dict[str, Any]) -> list[dict[str, Any]]:
        return [node, *[d for k in node.get("children", []) or [] for d in walk(k)]]

    nodes = walk(tree)
    edges = tuple((_node_name(n), verb) for n in nodes for verb in _verb_names(n))
    return Read(tuple(sorted(_node_name(n) for n in nodes)), tuple(sorted(edges)))


def _audit(root: Path, target: Path) -> dict[str, Any]:
    """The CLI audit tree of the repo's package, through the lexicon's one route to it.

    `cli_tree` walks the repo's one package by name, drops what it imported afterwards,
    and refuses a tree it could not read in full, so a declared `source:` names that
    package or the package root (`src/`) itself. Any other directory, a repo with no single
    package, or an audit that did not complete, is a `ReadError` carrying the reason: a broken
    tree never reads as a missing one.
    """
    where = _rel(target, root)
    package = package_dir(root)
    if package is None:
        raise ReadError(f"the CLI audit of `{where}` finds no single package")
    if target not in (package, package_root(root)):
        raise ReadError(f"the CLI audit reads `{_rel(package, root)}`, not `{where}`")
    try:
        return cli_tree(root)
    except LexiconError as err:
        raise ReadError(f"the CLI audit of `{where}`: {err}") from err


def _node_name(node: dict[str, Any]) -> str:
    """A CLI node's identity: its package path, which is what the tree is keyed on.

    `pkg` and not `command`, because `command` carries the invocation prefix
    (`python -m racecar.graph`) and an edge label should be the node, not how to type it.
    """
    return str(node.get("pkg") or node.get("command") or "?")


def _verb_names(node: dict[str, Any]) -> list[str]:
    """The verb names a CLI node declares, however `subcommands()` shaped them.

    `audit_cli_tree` reports a subcommand as a `(name, blurb)` pair for most nodes and as
    a bare string for some, so a reader that assumed either shape would silently produce
    the wrong edge label for the other.
    """
    out = []
    for entry in node.get("subcommands", []) or []:
        if isinstance(entry, (list, tuple)) and entry:
            out.append(str(entry[0]))
        elif isinstance(entry, dict):
            out.append(str(entry.get("name") or entry.get("verb") or "?"))
        else:
            out.append(str(entry))
    return out


def read_jsonl(root: Path, data: dict[str, Any]) -> Read | None:
    """Rows of a jsonl file as nodes, and an optional array field as edges.

    `source:` carries both halves — `path#node_key>edge_key`, or `path#node_key` for a
    graph with no edge type. So the capability spec and the delivery manifest are one
    reader and two declarations.

    **`edges` is `None` when no edge key is declared, and `()` when one is declared and
    unused.** That distinction is the whole reason the edge key is in the declaration
    rather than inferred: the delivery manifest has no edge type at all, while the
    capability graph's `requires` column exists and no row has used it yet. Data alone
    cannot tell those apart — both produce no pairs — and guessing makes an unrunnable
    check report a pass.
    """
    source, fragment = _source(data)
    node_key, _, edge_key = fragment.partition(">")
    if not node_key:
        return None
    nodes: list[str] = []
    edges: list[Edge] = []
    for row in _lines(root / source):
        try:
            record = json.loads(row)
        except json.JSONDecodeError:
            continue
        rid = str(record.get(node_key, "?"))
        nodes.append(rid)
        for target in (record.get(edge_key) or []) if edge_key else []:
            edges.append((rid, str(target)))
    if not nodes:
        return None
    return Read(tuple(sorted(nodes)), tuple(sorted(edges)) if edge_key else None)


def read_toml(root: Path, data: dict[str, Any]) -> Read | None:
    """A list of tables in a TOML file as nodes, addressed by `source:`'s fragment.

    `source: "pyproject.toml#tool.importlinter.contracts"` — the fragment is the dotted
    path to the list, and each entry's `name` is the node. Generic over any TOML-declared
    set: an adopter's own contracts, a tool's plugin table, a dependency group.

    Edges are `None`. What a table list carries is membership, not relation — an
    import-linter `layers` contract states a tier ORDER over module sets rather than a
    list of pairs, and enumerating the pairs it implies would be this reader inventing an
    edge set the tool never wrote down.
    """
    source, fragment = _source(data)
    target = root / source
    if not target.is_file() or not fragment:
        return None
    with target.open("rb") as handle:
        loaded = tomllib.load(handle)
    for key in fragment.split("."):
        loaded = loaded.get(key, {}) if isinstance(loaded, dict) else {}
    if not isinstance(loaded, list):
        return None
    names = tuple(
        str(entry.get("name", f"entry {i}")) if isinstance(entry, dict) else str(entry)
        for i, entry in enumerate(loaded)
    )
    return Read(tuple(sorted(names)), None)


def read_topology(root: Path, data: dict[str, Any]) -> Read | None:
    """A corpus graded against its own DECLARED topology: nodes on disk, plus peer edges.

    Generic over any corpus carrying `ontology/` and `topology/` beside its data --
    racecar's `architecture/` tree today, and `docs/lexicon/` equally, which is what makes
    this a mechanism rather than one graph's function. `source:` names the corpus root.

    **It does not collapse into `read_pnode`, and the reason is the edge set.**
    `structural_findings` returns containment AND peer edges together, applying the
    corpus's declared tier shape; a `pnode` frontmatter key carries containment only.
    Reading this corpus with `read_pnode` would silently drop every peer edge, and
    reimplementing the tier walk here would be a second opinion about a graph
    `racecar.graph check` already owns.

    **`lib.topology` is imported directly here, the way `lib.ontology` imports it.**
    Reaching it through `racecar.graph.topology.lib._verbs` -- a WRAPPER over this very
    package -- would invert the direction the delivered scripts are built on: library
    wraps delivered, never the reverse.
    """
    source, _ = _source(data)
    meta = root / source
    if not meta.is_dir():
        return None
    _errors, on_disk, edges = _walk.structural_findings(meta, meta / "topology")
    pairs = tuple((src, dst) for src, targets in edges.items() for dst in targets)
    return Read(tuple(sorted(on_disk)), tuple(sorted(pairs)))


def read_imports(root: Path, data: dict[str, Any]) -> Read | None:
    """The transitive `@path` import closure from the entry file `source:` names.

    Generic over any instruction-file chain: racecar's baseline starts at `CLAUDE.md`, an
    adopter's may start at `AGENTS.md`, and a repo with neither declares none.

    **A closure, not a collection, which is why it is its own reader.** You cannot glob for
    "files reachable by following `@`" -- reaching one file tells you which to read next,
    so the collector is a traversal. The walk itself lives in `lib.shared._imports`, shared
    with `racecar.root.lib.selfcheck._baseline`, so the row in the README and the check
    that gates it can never read different sets.
    """
    source, _ = _source(data)
    entry = root / source
    if not entry.is_file():
        return None
    reached, _broken = closure(entry, root)
    return Read(
        tuple(sorted(_rel(p, root) for p in reached)), import_edges(reached, root)
    )


def _read(root: Path, data: dict[str, Any]) -> Read | None:
    """One declaration's `Read`, with a `ReadError` renamed for the node that asked.

    The reader knows what it could not read and not which declaration sent it there, so
    the node's file name is prefixed here -- the same `<node>.md: ...` shape `malformed`
    and `unresolvable` give their findings.
    """
    try:
        found: Read | None = resolve(data["reader"])(root, data)
    except ReadError as exc:
        raise ReadError(f"{data['_node'].name}: {exc}") from exc
    return found


def build(root: Path) -> list[Graph]:
    """One `Graph` per DECLARED graph: the authored shape, plus sizes from its reader.

    The two halves are authored independently, which is what makes the row mean something:
    the declaration says what a node is and where the graph is read from, the reader
    produces the nodes and edges themselves. Deriving either from the other would make the
    row a report that cannot disagree with itself.

    Every size here is `len()` of a collection the reader returned, never a second walk.

    A reader returning None means the source is not on disk. That is a reported state and
    not an error -- an adopter has no `architecture/` and their axiom row reads `absent`,
    the same way a repo with no lexicon gets an empty lexicon. A reader that found its
    source and could not read it raises `ReadError` instead, and no row is built from it.
    """
    graphs: list[Graph] = []
    for data in declarations(root):
        # A reader that will not resolve is the CALLER's finding to report, via
        # `unresolvable`. Skipping the row here rather than raising keeps one bad
        # declaration from taking every other graph's row down with it.
        if reader_problem(str(data.get("reader") or "")) is not None:
            continue
        read = _read(root, data)
        graphs.append(
            Graph(
                data["name"],
                data["node"],
                data["edge"],
                len(read.nodes) if read is not None else 0,
                None if read is None or read.edges is None else len(read.edges),
                data["source"] if read is not None else "absent",
            )
        )
    return graphs


def read_all(root: Path) -> dict[str, Read]:
    """Every declared graph's `Read`, keyed by declared name; absent sources omitted.

    What an invariant loops over. `build` is the rendering path and returns sizes; this is
    the data path and returns the graphs, so a check never re-walks what a row measured.
    """
    out: dict[str, Read] = {}
    for data in declarations(root):
        if reader_problem(str(data.get("reader") or "")) is not None:
            continue
        read = _read(root, data)
        if read is not None:
            out[str(data["name"])] = read
    return out
