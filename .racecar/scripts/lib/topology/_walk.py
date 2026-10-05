"""Declare, walk by, and GRADE a corpus's topology — the tier shape a graph's containment
follows, orthogonal to its ontology (the type system). See `TOPOLOGY.md`.

**THIS IS THE IMPLEMENTATION, AND IT IS DELIVERED**, as `lib/topology/` beside
`scripts/topology.py`, the command line over it. It lands in an adopter's
`.racecar/scripts/` and runs there with no racecar installed, so it imports only what is
delivered with it -- `lib.lexicon._nodes.corpora` for the corpus join and
`lib.shared._root` for the repo root. `racecar.graph.topology.lib._verbs` is a
wrapper that delegates here; the dependency runs library-wraps-delivered, never the reverse.

It is delivered because racecar DELIVERS a topology
(`docs/rc_lexicon/topology/`, landing at `.racecar/docs/lexicon/topology/`) whose two tier
nodes are read as data: an adopter who receives the tiers receives what acts on them.

**This module and `lib.ontology._kinds` carry the same verbs.** `load_ontology`/
`load_topology_spec` read the declaration; `check(data, meta, domains)` grades a corpus
against it;
`relation_findings`/`structural_findings` return the findings a caller composes;
`_partition_of` and `project` cut one projection out of a partitioned corpus. The two
declarations are orthogonal in what they SAY and do genuinely different work inside those
names, and that is exactly why the names match: a reader who has learnt one engine should
not have to learn where the other one keeps the same verb.

Where `ontology.yaml` says what KIND a node is and what it must carry, `topology.yaml`
says WHERE a node subtree is rooted and how deep it may nest:

    name: architecture
    root_pattern: '^(?P<id>[PR]\\d\\d)-[a-z]+$'
    tiers: [rule, group, setting]

`root_pattern` answers root DISCOVERY — which top-level directories are node-subtree
roots at all. `tiers` is the depth bound: a tree this shape may nest at most
`len(tiers)` levels deep. Neither says anything about what KIND a node at a given tier
is. A node's tier position and its declared `kind:` are read independently;
nothing here infers one from the other.

**A topology is a graph or a document, never both**, the same split `ontology/_verbs`
makes one axis over. One home either way, `<meta>/topology/`; what is inside decides
which. An index alone — its own `tiers:` list, the shape above — is the document. That
index with `<tier>.md` nodes beside it, each declaring its own `name:` and `carrier:`,
is the graph, and each tier then has somewhere to argue its own shape.

The order is the part a directory cannot say for itself, so **a tier's `pnode` is its
place in the chain**: the first tier takes its `pnode` from the index and each later one
from the tier above it. A tier contains the next one, so containment and order are one
fact rather than two free to disagree. `load_topology_spec` assembles the same `tiers:`
list the document spells by hand — a bare name for an ordinary `carrier: dir` tier, a
`{name, carrier}` row otherwise — so `resolve` never learns which shape it read.

Absent is a legitimate state, same policy as `load_ontology` for a corpus with no
declared ontology: a `meta` with no declared topology walks permissively (every
directory holding a `README.md` is a candidate node, no root-pattern restriction, no
depth bound) rather than refusing to walk at all.

**Why `load` — walking the tree — lives here, not in a graph-level peer file, and why
grading it lives here too.**
Walking a tree of nodes is not a topology-neutral operation: it needs a root pattern
and a tier depth to know where to start and how deep to go, and those two facts are
exactly what a topology declares. The declaration, the walk that needs it, and the
grade that needs the walk are one chain with nothing outside this file in it.

`lib.ontology._kinds` holds loading and checking in one module for the same reason this one holds
declaring, walking and grading: `ontology.sample` PREFERS this module's own `load` — the
real, declared node graph — when `data` has a declared topology, and falls back to its
own `.md` glob only when it does not (a raw, undeclared pile is ontology's own real case,
not this module's — the walk is directory-shaped here, one node one `<dir>/README.md`, and
cannot represent a loose file with no containment position at all). The grade needs the
walk and the walk needs the declaration, so all three sit on one chain with no outside
link in it.

Complexity: O(N), N = nodes walked (one frontmatter parse each) x C corpora joined
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from lib.lexicon._nodes import corpora
from lib.shared import _frontmatter
from lib.shared._root import find_repo_root

# The repo this runs in, and its architecture tree. `find_repo_root` and not racecar's own
# root: this file is DELIVERED into `.racecar/scripts/` and runs from there with no racecar
# installed, so "the repo" is whichever one it was copied into. In racecar's own checkout the
# two coincide.
ROOT = find_repo_root()
META_ROOT = ROOT / "architecture"

TOPOLOGY_FILENAME = "topology.yaml"


class Tier(NamedTuple):
    """One tier of a declared topology: its name, and what carries a node at it.

    `carrier` is `"dir"` (the default -- a node is a directory holding a
    `README.md`) or `"file"` -- a tier whose members are
    inherently childless, so the node IS a `.md` file rather than a directory
    that holds one. Only the LAST tier may be `"file"`: a file
    cannot contain a further tier nested inside it.
    """

    name: str
    carrier: str = "dir"


def _parse_tier(spec: Any) -> Tier:
    """One `tiers:` list entry -- a bare name (a directory tier) or a
    `{name, carrier}` mapping -- resolved to a `Tier`."""
    if isinstance(spec, dict):
        carrier = str(spec.get("carrier") or "dir")
        if carrier not in ("dir", "file"):
            raise ValueError(
                f"tier {spec.get('name')!r}: carrier must be 'dir' or 'file', got "
                f"{carrier!r}"
            )
        return Tier(name=str(spec["name"]), carrier=carrier)
    return Tier(name=str(spec))


class Topology(NamedTuple):
    """A declared topology, resolved to what `load` actually needs."""

    name: str
    root_pattern: re.Pattern[str]
    tiers: tuple[Tier, ...]


def _topology_path(meta: Path) -> Path:
    """The declared topology's real source at `meta`.

    A proper kgraph node IS the declaration -- `meta`'s own `README.md` is
    checked FIRST, same as `ontology._verbs._ontology_path`. A generated
    `*.yaml` is the fallback for a declaration too large for one file's
    frontmatter. A bare file path (`meta` not a directory) is used exactly as
    given, whichever shape it is.
    """
    if not meta.is_dir():
        return meta
    readme = meta / "README.md"
    if readme.is_file():
        return readme
    candidates = sorted(meta.glob("*.yaml"))
    return candidates[0] if candidates else meta / TOPOLOGY_FILENAME


# A topology's one home, whichever shape it is in: `<meta>/topology/`. An index
# alone is a document -- every tier a row in its own `tiers:` list -- and an index
# with tier nodes beside it is a graph. The same split `ontology._verbs` makes, made
# the same way, because the two declarations are orthogonal in what they SAY and
# identical in how they are written down.
TOPOLOGY_DIRNAME = "topology"


def _is_tier_node(path: Path) -> bool:
    """Whether `path` declares a tier: `name:` (which tier) and `carrier:` (what
    carries a node at it).

    Both, because `name:` alone is carried by every node in every corpus --
    `topology` is also a CLI noun, so racecar's own `docs/lexicon/graph/topology/`
    is a directory of that name holding a README and a verb node, and it is a node
    IN a corpus rather than any corpus's meta.

    `carrier` earns the job of marker honestly: every tier has one, implicit at
    `dir` for a tier that is a row in a list, and a tier node spells it out.
    """
    if path.name == "README.md":
        return False
    frontmatter = _frontmatter.load(path)
    return bool(frontmatter.get("name")) and bool(frontmatter.get("carrier"))


def _is_graph(meta: Path, declaration: Path) -> bool:
    """Whether `meta` is the GRAPH shape: a `topology` directory of tier nodes."""
    return (
        meta.is_dir()
        and meta.name == TOPOLOGY_DIRNAME
        and declaration.name == "README.md"
        and any(
            _is_tier_node(p)
            for source in _topology_sources(meta)
            for p in source.glob("*.md")
        )
    )


def _topology_sources(meta: Path) -> list[Path]:
    """**Step two for the topology.** One `topology/` directory per joined corpus, in that
    order, skipping a corpus that holds none.

    The mirror of `lib.ontology._kinds._ontology_sources`, and for the same reason: the tiers a
    corpus obeys are assembled from every corpus that joins to make it, not from whichever
    one the caller happened to name. racecar's own two tiers are DELIVERED -- `noun` and
    `verb` live in `docs/rc_lexicon/topology/` and land at `.racecar/docs/lexicon/topology/`
    -- so without this the repo's own `docs/lexicon/topology/` holds an index and no tiers,
    `load_topology_spec` finds no `tiers:`, `resolve` returns None, and the walk silently
    falls back to permissive. That failure is invisible: every gate still reports OK, and
    the containment rule stops being checked.

    Anything that is not a directory named `topology` is one source and nothing else --
    `resolve` is also called with a bare `.yaml` path and with a directory that is not a
    corpus member (`architecture/topology`, whose parent is not a corpus root), and neither
    is a corpus whose peers this should go looking for.

    **A corpus that declares a topology OF ITS OWN is not joined to.** Its own declaration
    wins, whichever shape it is in -- a `tiers:` list on its index, or tier nodes beside it --
    and the delivered tiers are not read at all. Same ladder as everywhere else: the more
    specific statement wins, and canon is the fallback for a corpus that states nothing.

    Without that clause the join breaks a corpus's own declaration. An adopter who wrote
    a document-shaped topology, `tiers: [group, leaf]` on their own index, receives racecar's
    tier nodes on the next sync and `load_topology_spec` then raises "declares a `tiers:` list
    AND has tier nodes beside it" -- a hard `ValueError` out of `resolve`, which every graph
    command walks through, over a conflict the adopter did not create and a message naming
    nodes "beside it" that are in a different corpus. Two graphs collide the same way: two
    chains yield two roots and `_tiers_from_nodes` refuses both.
    """
    if not meta.is_dir() or meta.name != TOPOLOGY_DIRNAME:
        return [meta]
    declares_its_own = bool(
        (_frontmatter.load(_topology_path(meta)) or {}).get("tiers")
    ) or any(_is_tier_node(p) for p in meta.glob("*.md"))
    if declares_its_own:
        return [meta]
    found = [
        candidate
        for candidate in (corpus / TOPOLOGY_DIRNAME for corpus in corpora(meta.parent))
        if candidate.is_dir()
    ]
    return found or [meta]


def _tiers_from_nodes(meta: Path) -> list[Any]:
    """The `tiers:` list a directory of tier nodes declares, in order.

    **The order is the `pnode` chain**, which is the one thing a directory cannot
    say for itself: a list is ordered and a set of files is not. The first tier
    takes its `pnode` from the index, each later tier from the tier above it, and
    reading the chain from the index down gives the same list a `tiers:` row would
    have spelled. That is not a coding trick — a tier genuinely CONTAINS the next
    one, so containment and order are the same fact, and storing the order twice
    would be the second home the repo's own axiom forbids.

    Rendered back into the row shape `_parse_tier` already reads: a bare name for
    the ordinary `carrier: dir` tier, a `{name, carrier}` mapping otherwise. So a
    topology reads identically whichever shape it was written in, and `resolve`
    below never learns which it got.
    """
    nodes = {
        p.resolve(): _frontmatter.load(p)
        for source in _topology_sources(meta)
        for p in source.glob("*.md")
    }
    nodes = {p: fm for p, fm in nodes.items() if _is_tier_node(p)}
    parent_of: dict[Path, Path | None] = {}
    for path, frontmatter in nodes.items():
        refs = [
            (path.parent / str(ref)).resolve()
            for ref in (frontmatter.get("pnode") or [])
        ]
        tiers_above = [ref for ref in refs if ref in nodes and ref != path]
        if len(tiers_above) > 1:
            raise ValueError(
                f"{path}: names {len(tiers_above)} tiers in its `pnode` — tiers are "
                "an ordered chain, so a tier has at most one tier above it"
            )
        parent_of[path] = tiers_above[0] if tiers_above else None

    roots = [path for path, parent in parent_of.items() if parent is None]
    if len(roots) != 1:
        named = ", ".join(sorted(p.name for p in roots)) or "none"
        raise ValueError(
            f"{meta}: a topology is one ordered chain, so exactly one tier takes its "
            f"`pnode` from the index and every other from the tier above it; found "
            f"{len(roots)} without a tier above ({named})"
        )
    children: dict[Path, list[Path]] = {}
    for path, parent in parent_of.items():
        if parent is not None:
            children.setdefault(parent, []).append(path)
    for parent, kids in children.items():
        if len(kids) > 1:
            named = ", ".join(sorted(p.name for p in kids))
            raise ValueError(
                f"{parent}: {len(kids)} tiers name it as the tier above them "
                f"({named}) — a topology is a chain, not a branching tree"
            )

    order: list[Path] = []
    cursor: Path | None = roots[0]
    while cursor is not None:
        if cursor in order:
            raise ValueError(f"{cursor}: the tier chain loops back on itself")
        order.append(cursor)
        kids = children.get(cursor) or []
        cursor = kids[0] if kids else None
    if len(order) != len(nodes):
        stranded = ", ".join(sorted(p.name for p in nodes if p not in order))
        raise ValueError(
            f"{meta}: {stranded} is not reachable from the first tier — every tier "
            "belongs to the one chain"
        )
    return [
        (
            str(nodes[path]["name"])
            if str(nodes[path]["carrier"]) == "dir"
            else {
                "name": str(nodes[path]["name"]),
                "carrier": str(nodes[path]["carrier"]),
            }
        )
        for path in order
    ]


def load_topology_spec(meta: Path) -> dict[str, Any] | None:
    """The raw declared topology, or `None` when `meta` declares none.

    One dict whichever shape it is written in. A `topology/` directory holding tier
    nodes is a graph — the index keeps `root_pattern` and the corpus-level keys, and
    each tier is a node of its own that can carry the argument for its own shape —
    and its assembled `tiers:` is exactly the list the document shape spells by hand.
    """
    path = _topology_path(meta)
    if not path.is_file():
        return None
    if path.suffix == ".md":
        spec = _frontmatter.load(path)
    else:
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not _is_graph(meta, path):
        return spec
    if spec.get("tiers"):
        raise ValueError(
            f"{path}: declares a `tiers:` list AND has tier nodes beside it — a "
            "topology is a document or a graph, never both"
        )
    return {**spec, "tiers": _tiers_from_nodes(meta)}


def resolve(meta: Path | None) -> Topology | None:
    """A declared topology resolved to a compiled pattern + tier tuple, or `None`.

    `None` means "no declared topology" — the caller's job is to walk permissively,
    not to invent a default. Raises `ValueError` on a declared-but-malformed
    `root_pattern` rather than silently matching nothing, the same fail-loud policy
    `acyclic_kinds` applies to a cyclic ontology.
    """
    if meta is None:
        return None
    spec = load_topology_spec(meta)
    if not spec or not spec.get("root_pattern") or not spec.get("tiers"):
        return None
    try:
        pattern = re.compile(str(spec["root_pattern"]))
    except re.error as exc:
        raise ValueError(
            f"{_topology_path(meta)}: `root_pattern` does not compile: {exc}"
        ) from exc
    tiers = tuple(_parse_tier(t) for t in spec["tiers"])
    file_tiers = [i for i, t in enumerate(tiers) if t.carrier == "file"]
    if file_tiers and file_tiers != [len(tiers) - 1]:
        raise ValueError(
            f"{_topology_path(meta)}: only the last tier may be `carrier: file` "
            f"(a file cannot contain a further tier); got it at "
            f"{[tiers[i].name for i in file_tiers]}"
        )
    return Topology(
        name=str(spec.get("name") or "unnamed"), root_pattern=pattern, tiers=tiers
    )


# The permissive fallback for a corpus with NO declared topology -- matches every
# policy `ONTOLOGY.md` states for a corpus with no declared ontology, and what
# `TOPOLOGY.md` itself says this fallback does: "every directory holding a README.md
# is a candidate node, no root-pattern restriction, no depth bound". It is not racecar's
# OWN `[PR]-NN`/three-tier shape: an undeclared FOREIGN corpus (the only case that
# reaches this fallback; racecar's own tree always has a real declared topology) would
# silently yield zero nodes rather than walking permissively, because nothing outside
# racecar's own tree is shaped `[PR]-NN`. `None` tiers means unbounded depth -- there is
# no finite tuple that means "no bound" the way an empty root_pattern restriction is
# `.*`, so the depth check below special-cases it explicitly rather than reaching for a
# large sentinel tuple.
_FALLBACK_ROOT_PATTERN = re.compile(r".*")
_FALLBACK_TIERS: tuple[Tier, ...] | None = None


def load(
    data: Path | None = None, meta: Path | None = None
) -> dict[str, dict[str, Any]]:
    """Every node, read fresh from the tree at `data` (racecar's own `architecture/`
    absent one). Kind is DECLARED, in each node's own frontmatter (`kind:`), not
    read from depth. A node with no declared `kind` loads with
    `kind: None` rather than raising; the composite gate is where that becomes a finding,
    because this function's only job is reading the tree as it actually is (P-02).

    Keyed by PATH relative to `data`, not by the directory's bare basename
    — a basename recurs across containers by design (the same concept slug
    under two different parents, or a leaf tier whose short names are drawn from a
    small shared vocabulary), and a dict keyed on it silently drops every node but
    the last one loaded with that name. The basename survives as `name`, for a
    caller that wants the short form to render; `id` and the dict key are always
    the same path string. A `carrier: file` leaf's id strips the `.md` suffix, so a
    file-tier and a directory-tier node have the same shape of id either way.

    Root discovery and the depth bound come from `meta`'s declared topology (`meta`
    absent defaults to `data` — racecar's own `architecture/` tree carries both its
    data and its topology in one place, and always declares one, so this fallback is
    never actually consulted for racecar's own tree). A `meta` with no declared
    topology walks permissively instead — every directory holding a README.md is a
    candidate node, no root-pattern restriction, no depth bound — the same "absent is
    legitimate, not an error" policy this module applies to a corpus with no declared
    ontology, rather than silently yielding zero nodes for a foreign layout that was
    never going to match racecar's own shape.
    """
    tax = (data if data is not None else META_ROOT).resolve()
    resolved = resolve(meta if meta is not None else tax / "topology")
    root_pattern = resolved.root_pattern if resolved else _FALLBACK_ROOT_PATTERN
    tiers = resolved.tiers if resolved else _FALLBACK_TIERS

    nodes: dict[str, dict[str, Any]] = {}
    # A node subtree is rooted at a topology root, so the walk is anchored on the
    # declared (or permissively-fallback) root pattern -- for a corpus WITH a declared
    # topology this still excludes siblings like architecture/'s own `scripts/`,
    # `canon/`, PRINCIPLES.md; the permissive fallback only ever runs for a corpus
    # with no declared topology at all, where nothing distinguishes a "real" sibling
    # from a node candidate anyway.
    for d in sorted(p for p in tax.rglob("*") if p.is_dir()):
        rel = d.relative_to(tax).parts
        if not root_pattern.match(rel[0]):
            continue
        readme = d / "README.md"
        if (tiers is not None and len(rel) > len(tiers)) or not readme.is_file():
            continue
        fm = _frontmatter.load(readme)
        node_id = d.relative_to(tax).as_posix()
        nodes[node_id] = {
            **fm,
            "id": node_id,
            "name": d.name,
            "kind": fm.get("kind"),
            "serves": d.parent.relative_to(tax).as_posix() if len(rel) > 1 else None,
            "path": d,
        }

    # A `carrier: file` last tier: that tier's members are inherently
    # childless, so the node IS a `.md` file rather than a directory holding one.
    # Only the last tier may be `carrier: file` (`resolve` refuses otherwise), and
    # its members sit one level under a directory at the SECOND-TO-LAST tier --
    # a depth the directory loop above already walked, so this reuses its root
    # discovery rather than re-deriving it.
    if tiers and tiers[-1].carrier == "file":
        parent_depth = len(tiers) - 1
        for d in sorted(p for p in tax.rglob("*") if p.is_dir()):
            rel = d.relative_to(tax).parts
            if not root_pattern.match(rel[0]) or len(rel) != parent_depth:
                continue
            for leaf in sorted(d.glob("*.md")):
                if leaf.name == "README.md":
                    continue
                fm = _frontmatter.load(leaf)
                leaf_id = (d.relative_to(tax) / leaf.stem).as_posix()
                nodes[leaf_id] = {
                    **fm,
                    "id": leaf_id,
                    "name": leaf.stem,
                    "kind": fm.get("kind"),
                    "serves": d.relative_to(tax).as_posix(),
                    "path": leaf,
                }
    return nodes


def structural_findings(  # pylint: disable=too-many-statements
    data: Path, meta: Path | None = None
) -> tuple[list[str], dict[str, Path], dict[str, list[str]]]:
    """Containment + peer-DAG findings for `data`, graded against `meta`'s declared
    topology (or the permissive fallback — see `load`/`resolve` above).

    One pass over one tree, each block a named invariant; splitting it would scatter
    the invariants across functions that all need the same dicts.

    Returns `(errors, on_disk, peer_edges)` — the latter two are what `check` below, the
    graph-level composite's own summary and `graph.py`'s node and edge counts all
    need, computed once here rather than walked three times.
    """

    def frontmatter_of(node_path: Path) -> Path:
        """The file carrying `node_path`'s own frontmatter — itself, for a
        `carrier: file` leaf; `README.md` inside it otherwise."""
        return node_path if node_path.is_file() else node_path / "README.md"

    def node_of(carrier: Path) -> Path:
        """The inverse of `frontmatter_of`: the node a frontmatter FILE belongs to
        — its own directory for a `README.md`, or the file itself for a leaf."""
        return carrier.parent if carrier.name == "README.md" else carrier

    def node_id(node_path: Path) -> str:
        """The id `load` gave this node -- its path relative to `data`,
        minus the `.md` suffix for a `carrier: file` leaf."""
        if node_path.is_dir():
            return node_path.relative_to(data).as_posix()
        return (node_path.parent.relative_to(data) / node_path.stem).as_posix()

    declared = load(data, meta)
    on_disk = {nid: n["path"] for nid, n in declared.items()}

    errors: list[str] = []

    for nid, d in on_disk.items():
        readme = frontmatter_of(d)
        if not readme.is_file():
            errors.append(f"{nid}: node directory has no README.md")
            continue
        # ONE parent, any number of SIBLINGS, nothing deeper.
        #
        # A pnode target must sit at depth <= this node's depth. Exactly one sits
        # one level up — that is containment, and one parent is what makes it a
        # tree. The rest sit at the SAME depth and are precedence edges: R-08
        # naming R-07 is a peer saying "this takes that as given".
        #
        # That is why there is no second edge vocabulary. Containment and
        # precedence are one relation read by depth, and a target DEEPER than the
        # declaring node is the only shape that is meaningless in either reading.
        refs = declared[nid].get("pnode") or []
        here = len(d.relative_to(data).parts)
        parents: list[str] = []
        for ref in refs:
            target = (readme.parent / ref).resolve()
            if not target.is_file():
                errors.append(f"{nid}: pnode {ref!r} resolves to nothing")
                continue
            try:
                there = len(node_of(target).relative_to(data).parts)
            except ValueError:
                errors.append(f"{nid}: pnode {ref!r} points outside the corpus")
                continue
            own_parent = (d.parent / "README.md").resolve()
            if there == here - 1:
                # THE parent, not merely something one level up. Depth alone admits an
                # uncle -- a d-1 node in another branch -- which would declare a second
                # containment tree over the same directories. Containment is the
                # filesystem's fact (P-02), so it is compared against the filesystem
                # rather than against a frontmatter field that can disagree with it.
                if target != own_parent:
                    errors.append(
                        f"{nid}: pnode {ref!r} is one level up but is not this node's "
                        f"parent. A parent edge names the containing directory and "
                        f"nothing else; any other d-1 node is an uncle."
                    )
                else:
                    parents.append(ref)
            elif there == here:
                # SAME CONTAINER. A peer edge joins nodes under one parent; a cousin
                # -- level, but in another container -- is a claim about two containers,
                # which is containment's job, not precedence's.
                if node_of(target).parent != d.parent:
                    errors.append(
                        f"{nid}: peer {ref!r} sits under "
                        f"{node_of(target).parent.name!r}, not {d.parent.name!r} — a "
                        f"peer edge stays inside one container. Crossing one means the "
                        f"two share a parent they have not declared, which is a "
                        f"compound to decompose."
                    )
            else:
                errors.append(
                    f"{nid}: pnode {ref!r} is at depth {there}; this node is at {here}. "
                    f"A parent sits one above, a peer sits level; nothing may sit below."
                )
        if len(parents) != 1:
            errors.append(
                f"{nid}: has {len(parents)} parent pnode(s) at depth {here - 1}; "
                f"exactly one is what makes containment a tree"
            )

    # PEER EDGES, held acyclic.
    edges: dict[str, list[str]] = {}
    for nid, d in on_disk.items():
        here = len(d.relative_to(data).parts)
        peers = []
        for ref in declared[nid].get("pnode") or []:
            target = (frontmatter_of(d).parent / ref).resolve()
            if not target.is_file():
                continue
            peer = node_of(target)
            # A pnode outside the corpus is reported by the first loop; it has no depth here.
            if peer == data or not peer.is_relative_to(data):
                continue
            if len(peer.relative_to(data).parts) == here:
                peers.append(node_id(peer))
        edges[nid] = peers

    seen: dict[str, int] = {}

    def walk(nid: str, stack: list[str]) -> None:
        if seen.get(nid) == 2:
            return
        if seen.get(nid) == 1:
            errors.append("peer cycle: " + " -> ".join(stack + [nid]))
            return
        seen[nid] = 1
        for t in edges.get(nid, []):
            if t in declared:
                walk(t, stack + [nid])
        seen[nid] = 2

    for nid in sorted(declared):
        walk(nid, [])

    return errors, on_disk, edges


def _partition_of(declared: dict[str, Any] | None) -> str | None:
    """The frontmatter field this corpus splits into projections along, or None.

    `ontology._partition_of`'s counterpart, reading the topology's own declaration instead
    of the ontology's — the two engines read different files and must not read each other's,
    so the rule is stated once per engine rather than shared. Declared, never fixed: the
    engine should not know the word `domain`. A corpus that declares no `partition:` has no
    projections at all, so asking for one is a category error rather than an empty result.
    """
    value = declared.get("partition") if declared else None
    return str(value) if value else None


def project(
    nodes: dict[str, dict[str, Any]], field: str | None, domains: list[str]
) -> dict[str, dict[str, Any]]:
    """The sub-corpus whose `field` names any of `domains`. Not a filter — a subgraph.

    `ontology.project`'s counterpart over a WALKED tree rather than a flat source list, so
    it keys by node id and reads each node's own frontmatter as `load` already parsed it.
    A node claiming several domains appears in each of their projections: a shared word is
    one vertex where two graphs meet.
    """
    if not field or not domains:
        return nodes
    wanted = set(domains)
    out: dict[str, dict[str, Any]] = {}
    for nid, node in nodes.items():
        raw = node.get(field)
        claimed = {str(raw)} if isinstance(raw, str) else {str(x) for x in (raw or [])}
        if claimed & wanted:
            out[nid] = node
    return out


def check(
    data: Path | None = None,
    meta: Path | None = None,
    domains: list[str] | None = None,
) -> dict[str, Any]:
    """The topology at `data` as a graph, and every way it breaks the declared shape.

    `data` absent is racecar's own `architecture/`; `meta` absent is `<data>/topology`.
    `nodes` maps each node id to the node `load` reads, `contains` maps it to its parent's
    id (None for a root), and `peers` to the ids it declares as peers. `errors` is empty
    when the tier shape holds. Prints nothing: `lib.topology._check` is the verb over it.

    `ontology.check`'s counterpart, and deliberately the same name and argument order for a
    different result: an ontology's fit is a MEASUREMENT (`Fit`, a percentage that can be
    poor without being wrong), where a tier shape either holds or does not.

    `domains` grades ONE projection. There is no union pass, because the union is not a
    graph -- it is a superposition of overlapping edges that nobody authored as a tree. The
    invariant that makes each projection rooted is that a node's domains are a subset of its
    parent's; violate it and the parent vanishes from this projection while the union stays
    perfectly green.
    """
    tax = (data if data is not None else META_ROOT).resolve()
    if not tax.is_dir():
        return {
            "nodes": {},
            "contains": {},
            "peers": {},
            "errors": [f"{tax} is not a directory"],
        }
    meta_path = meta if meta is not None else tax / "topology"

    errors, on_disk, edges = structural_findings(tax, meta_path)
    declared = load(tax, meta_path)

    def _parent_id(d: Path) -> str | None:
        if d.parent == tax:
            return None
        pid = d.parent.relative_to(tax).as_posix()
        return pid if pid in declared else None

    contains = {nid: _parent_id(d) for nid, d in on_disk.items()}

    if domains:
        field = _partition_of(load_topology_spec(meta_path))
        if field is None:
            errors.append(
                f"{_topology_path(meta_path)}: this corpus declares no `partition:`, so it "
                f"has no projections — cannot check --domain {', '.join(domains)}"
            )
            return {"nodes": {}, "contains": {}, "peers": {}, "errors": errors}
        keep = set(project(declared, field, domains))
        for nid in sorted(keep):
            parent = contains.get(nid)
            if parent is not None and parent not in keep:
                errors.append(
                    f"{nid}: present in domain(s) {', '.join(sorted(domains))} but its parent "
                    f"{parent} is not — that leaves this projection rootless at {nid}."
                )
        declared = {k: v for k, v in declared.items() if k in keep}
        contains = {k: v for k, v in contains.items() if k in keep}
        edges = {k: v for k, v in edges.items() if k in keep}

    return {"nodes": declared, "contains": contains, "peers": edges, "errors": errors}
