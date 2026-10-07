"""Check, or derive, the ontology a body of source material conforms to.

**THIS IS THE IMPLEMENTATION, AND IT IS DELIVERED**, as `lib/ontology/` beside
`scripts/ontology.py`, the command line over it. It lands in an adopter's
`.racecar/scripts/` and runs there with no racecar installed, so it imports only what is
delivered with it -- `lib.topology` for the tier walk, `lib.lexicon._nodes` for the corpus
join and the kind reader. `racecar.graph.ontology.lib._verbs` is a wrapper that delegates
here; the dependency runs library-wraps-delivered and never the reverse.

It is delivered because racecar DELIVERS an ontology
(`docs/rc_lexicon/ontology/`, landing at `.racecar/docs/lexicon/ontology/`) whose kind nodes
are read as data. A reader has to travel with the thing it reads.

An ontology says what kinds of thing exist in a domain and what each must carry
(`ONTOLOGY.md`); a corpus of instances filed against those forms is a graph, not a
taxonomy — `GRAPH.md` names *taxonomy* itself as a word "tried and wrong" for that
tree, because a taxonomy is a classification scheme, which is the ontology's job.
This module answers the ontology question: given a pile of source files, what KINDS
of thing are in it, and what must each carry?

SCOPE NOTE — this module's `check`/`derive` score a corpus
against exactly ONE ontology — declared at `--meta` — rather than a registry of
every ontology reachable, which is out of scope.

`ontology.yaml` (or its containing directory), named at `--meta`, sibling to the
sources it describes:

    name: deal
    discriminator: kind   # optional; default "kind" — the frontmatter field
                          # naming a source's kind. A sibling corpus in the
                          # same real toolchain uses `type` for this instead,
                          # which is why the field name is declared, not fixed.
    base:
      required: [asof]
    kinds:
      entity:
        required: [role]
      instrument:
        required: [counterparty]
        depends_on: [entity]

`kinds` maps a kind name to the fields a node of that kind must carry
(`required`) and, optionally, which other kinds it depends on (`depends_on`) —
the ontology's own DAG, checked acyclic before any source is scored against it
(`acyclic_kinds`, public because `racecar.graph` is a second real caller). The top-level
`base.required` is optional and orthogonal to `kinds`: fields every node carries
whatever its kind, checked in addition to its kind's own `required` list.

**An ontology is a graph or a document, never both.** It has one home either way,
`<meta>/ontology/`, and what decides the shape is what is inside it. An index alone
— `ontology/README.md` whose own `kinds:` block holds every kind, the shape above,
or an `ontology.yaml` — is the document: one file, a kind per row. That index with
`<kind>.md` nodes beside it, each declaring its own `name:` and `required:`, is the
graph. Not told apart by a distinguishing FILENAME: `ONTOLOGY.md` already names this
repo's doctrine ABOUT ontologies, and one name doing two jobs is the drift a
declaration of all things should not be caught in.

The difference is not filing. A row in a block has no parent and nothing can point
at it, so a kind has nowhere to say why it requires what it requires and no way to
narrow another kind. **A kind node's `pnode` is inheritance** — a kind filed under
another kind carries everything that one requires plus its own, which is what a
corpus of financial instruments needs and what a block cannot express. Resolved at
load, so `load_ontology` returns one flat `kinds` mapping either way and nothing
downstream knows which shape it read.

racecar's own ontologies are graphs. The document is read for compatibility rather
than as a second blessed shape: racecar delivers its checkers and not its lexicon,
so an adopter's unmoved ontology meeting a new `load_ontology` is the ordinary case.

**Two verbs, one operation, deliberate.** `identify` and `derive` both infer a
candidate ontology from field presence in `--data` — the same underlying pass —
and differ only in whether the result is written to `--meta`: `identify` reports,
read-only; `derive` writes. Kept as two named verbs rather than one verb plus a
mode flag, for discoverability — a caller scanning `--help` sees the read/write
split in the verb name, not buried in a flag. `check` is the DIFFERENT operation —
scoring `--data` against an ALREADY-declared ontology at `--meta` — and does not
infer anything.

**The unmapped fraction is first-class**: sampling degrades
silently, and an ontology "identified" from a handful of sources looks exactly
like one identified from all of it unless the fraction is reported alongside
the verdict rather than buried in a caveat.

Complexity: O(S), S = sources read (one frontmatter parse each) x C corpora joined
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml
from lib.lexicon._corpora import home_directories
from lib.lexicon._nodes import ONTOLOGY_DIRNAME, graph_kinds
from lib.shared import _frontmatter
from lib.topology import _walk

# Keys `lib.topology._walk.load` adds to every node that are not part of its own
# frontmatter -- stripped when reshaping a walked node back into the shape
# `sample()`'s own glob would have produced, so `derive()`'s field-presence count
# is not corrupted by every node spuriously "requiring" `id`/`name`/`serves`/`path`.
_TOPOLOGY_DERIVED_KEYS = frozenset({"id", "name", "serves", "path"})
DEFAULT_SAMPLE_LIMIT = 500
# Past this fraction unmapped, the declared ontology does not fit — `check` reports
# no match rather than naming a schema most of the corpus disagrees with.
UNMAPPED_THRESHOLD = 0.2
ONTOLOGY_FILENAME = "ontology.yaml"
# An ontology's one home, whichever shape it is in: `<meta>/ontology/`. What decides
# the shape is what is INSIDE it -- an index alone is a document, an index with kind
# nodes beside it is a graph. Deliberately not a distinguishing FILENAME: `ONTOLOGY.md`
# already names this repo's doctrine about ontologies (`docs/graphs/ONTOLOGY.md`), and
# a second meaning for it would be two homes for one name. `ONTOLOGY_DIRNAME` itself is
# imported from `lib.lexicon._nodes`, which reads the same shape.

# The frontmatter field naming a source's kind, absent a declared override. A sibling
# ontology may name the same concept `type` instead, which is why an ontology may
# override it rather than the field name being fixed.
DEFAULT_DISCRIMINATOR = "kind"


@dataclasses.dataclass(frozen=True)
class Fit:
    """How well a sampled corpus matches the ONE ontology declared at `--meta`.

    `best` is the ontology's own `name` when the fit clears
    `UNMAPPED_THRESHOLD`, `None` otherwise — either because `--meta` declares no
    ontology at all, or because it declares one the sources mostly don't match.
    Both cases mean the same next step: call `derive()`.
    """

    best: str | None
    unmapped_fraction: float
    total: int
    by_kind: dict[str, int]


@dataclasses.dataclass(frozen=True)
class Proposal:
    """A candidate ontology inferred from `--data`, not yet declared anywhere.

    Stops at the proposal — the same terminus `racecar-issue create` stops at
    with a rendered issue body: adopting a schema is the corpus owner's
    keystroke, never this function's.
    """

    kinds: dict[str, list[str]]  # kind -> required fields, inferred from presence
    dag: dict[str, list[str]]  # kind -> kinds it depends on, best-effort
    total: int


def _from_topology(data: Path, limit: int) -> list[dict[str, Any]] | None:
    """The declared topology's real node graph, reshaped to what `sample()` returns
    -- or `None` when `data` declares no topology, so the caller falls back to its
    own glob rather than reading "declares nothing" as "declares zero nodes".

    Both `lib.topology._walk.load` and this module's own glob walk a tree and return a
    collection of nodes to traverse; the difference is what a NODE is. Topology's
    walk is directory-shaped -- one node is one `<dir>/README.md` -- and requires
    a declared (or racecar's own fallback) root pattern and tier depth to mean
    anything. `sample()`'s glob is file-shaped -- one node is one `.md` file,
    anywhere, README.md or not -- because inferring an ontology from a raw,
    undeclared pile is exactly the
    case a topology has not been authored for yet. So this is preferred WHEN a
    topology is declared for `data` (an already-structured corpus's real
    containment positions are a more accurate "what are the units here" than a
    blind glob, and `check`/`identify`/`derive` then score against the same
    nodes `racecar.graph.topology check` itself grades) and skipped otherwise.
    """
    if _walk.resolve(data / "topology") is None:
        return None
    out: list[dict[str, Any]] = []
    for node in list(_walk.load(data).values())[:limit]:
        source = {k: v for k, v in node.items() if k not in _TOPOLOGY_DERIVED_KEYS}
        if source.get("kind") is None:
            source.pop("kind", None)
        path = node["path"]
        source["_path"] = path if path.is_file() else path / "README.md"
        out.append(source)
    return out


def sample(data: Path, limit: int = DEFAULT_SAMPLE_LIMIT) -> list[dict[str, Any]]:
    """The corpus's real, declared nodes when `data` has a declared topology
    (`_from_topology`); every `.md` file under `data` carrying YAML frontmatter,
    up to `limit`, otherwise.

    "Enough to characterise, not enough to be slow." A corpus larger than
    `limit` is sampled, not read whole; the walk is sorted first so the same
    corpus samples the same way twice rather than depending on filesystem order.
    """
    from_topology = _from_topology(data, limit)
    if from_topology is not None:
        return from_topology
    out: list[dict[str, Any]] = []
    for path in sorted(data.rglob("*.md"))[:limit]:
        frontmatter = _frontmatter.load(path)
        if frontmatter:
            out.append({**frontmatter, "_path": path})
    return out


def _ontology_path(meta: Path) -> Path:
    """The declared ontology's real source at `meta`.

    A proper kgraph node IS the declaration -- `meta`'s own `README.md` is
    checked FIRST, its frontmatter read the same way any other node in this
    graph is, not as a lesser or different format. A generated `*.yaml`
    (a flat projection of a node tree too large for one file's
    frontmatter, `<name>.yaml` beside the source it projects) is the
    fallback, for when a declaration has outgrown one node.
    A bare file path (`meta` not a directory) is used exactly as given,
    whichever of the shapes it is.

    `README.md` is the declaration either way: the whole ontology when it is a
    document, the INDEX — corpus-level keys only — when the kinds are nodes beside
    it. `_nodes.is_graph` is what tells those apart, and it reads the directory rather
    than the filename.
    """
    if not meta.is_dir():
        return meta
    readme = meta / "README.md"
    if readme.is_file():
        return readme
    candidates = sorted(meta.glob("*.yaml"))
    return candidates[0] if candidates else meta / ONTOLOGY_FILENAME


def _ontology_sources(meta: Path) -> list[Path]:
    """**Step two for the ontology.** One ontology directory per joined corpus, in that
    order, skipping a corpus that holds none.

    `meta` is an ontology directory, and `home_directories` names the same directory in every
    home of the lexicon union. Anything that is not a directory named `ontology` is one source and
    nothing else: `load_ontology` is also called with a plain corpus root
    (`racecar.graph`'s build, when no `--meta` is named) and with a bare `.yaml` path,
    and neither is a corpus whose peers this should go looking for.
    """
    if not meta.is_dir() or meta.name != ONTOLOGY_DIRNAME:
        return [meta]
    return home_directories(meta)


# How a kind node is read, how a graph-shaped ontology is told from a document, and how
# `pnode` inheritance resolves live ONCE, in `lib.lexicon._nodes` (`graph_kinds`), because
# `lexicon check` reads the same declarations.


def _load_one_ontology(meta: Path) -> dict[str, Any] | None:
    """The ontology declared at the ONE directory `meta`, or `None` when it declares none.

    **An ontology is a graph or a document, never both.** One home either way,
    `<meta>/ontology/`; what is inside it decides which. With kind nodes beside the
    index it is a graph: `README.md` carries the corpus-level keys (`discriminator`,
    `partition`, `base`, ...) and each `<kind>.md` carries what that kind requires,
    the argument for it, and a `pnode` it may inherit through. With none, it is a
    document — the index's own `kinds:` block, or an `ontology.yaml` — in which a
    kind is a row, with no parent and nothing able to point at it.

    Both are read, and the same dict comes back either way, so nothing downstream
    knows which it got. The document is compatibility rather than a second blessed
    shape: racecar delivers its checkers and not its lexicon, so an adopter's
    unmoved ontology meeting a new `load_ontology` is the ordinary case.

    An ontology directory holding kind nodes AND a `kinds:` block on its index is
    refused. That is the one state the rule above forbids, and resolving it by
    picking a winner would mean the file said one thing and the checker did another.
    """
    path = _ontology_path(meta)
    if not path.is_file():
        return None
    if path.suffix == ".md":
        declared = _frontmatter.load(path)
    else:
        declared = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # None when there are no kind nodes: the declaration is then the document the index
    # already is.
    kinds = graph_kinds(meta, path, declared)
    return declared if kinds is None else {**declared, "kinds": kinds}


def load_ontology(meta: Path) -> dict[str, Any] | None:
    """The ontology in force at `meta`: the OUTER JOIN of the joined corpora's ontologies
    (`_ontology_sources`), or `None` when none of them declares one.

    One tree is the ordinary case — `_load_one_ontology` is the whole of it, including
    its refusal of a directory that is both a document and a graph, which is raised per
    source and neither widened nor narrowed here.

    Several trees union their kinds, and **a kind declared in more than one of them resolves
    to the first** — `lexicon_corpora` puts them in resolution order, custom before the repo's own
    before the delivered corpus, so the most specific declaration wins and canon is the
    fallback. A repo can therefore narrow a delivered kind, which `shadowed_kinds` reports
    rather than applying in silence. The corpus-level keys resolve the same way, first tree
    first, because `discriminator`, `partition` and `base` are statements about a corpus and
    a delivered tree is not one.

    `ontology_shadowed` reports which copies lost, so the resolution is visible rather than
    silent -- two files claiming one kind is exactly the state where a quiet winner is
    indistinguishable from a reader that found the other file.
    """
    sources = _ontology_sources(meta)
    if len(sources) == 1:
        return _load_one_ontology(sources[0])
    joined: dict[str, Any] | None = None
    kinds: dict[str, Any] = {}
    for source in sources:
        one = _load_one_ontology(source)
        if one is None:
            continue
        for name, spec in (one.get("kinds") or {}).items():
            kinds.setdefault(name, spec)
        corpus_keys = {k: v for k, v in one.items() if k != "kinds"}
        joined = corpus_keys if joined is None else {**corpus_keys, **joined}
    if joined is None:
        return None
    return {**joined, "kinds": kinds} if kinds else joined


def ontology_shadowed(meta: Path) -> dict[str, Path]:
    """Every kind declared in more than one of the joined corpora, mapped to the source
    whose copy LOST.

    Empty in the ordinary case, and never a finding: a repo is allowed to restate a
    delivered kind, and restating is how it narrows one. It is also never silent, which
    is what this function is for — `racecar.graph check` prints it.
    """
    seen: dict[str, Path] = {}
    out: dict[str, Path] = {}
    for source in _ontology_sources(meta):
        one = _load_one_ontology(source)
        for name in (one or {}).get("kinds") or {}:
            if name in seen:
                out[name] = source
            else:
                seen[name] = source
    return out


def acyclic_kinds(kinds: dict[str, dict[str, Any]]) -> bool:
    """The declared ontology's own `depends_on` graph, held acyclic — the same
    invariant `lib.topology._walk.structural_findings` holds the peer-edge DAG to.
    Public (not `_acyclic`) because that module is a second real caller of this
    exact yes/no, not a detail private to this module's own two functions."""
    state: dict[str, int] = {}

    def walk(kind: str) -> bool:
        if state.get(kind) == 2:
            return True
        if state.get(kind) == 1:
            return False
        state[kind] = 1
        for dep in (kinds.get(kind) or {}).get("depends_on") or []:
            if dep in kinds and not walk(dep):
                return False
        state[kind] = 2
        return True

    return all(walk(kind) for kind in kinds)


def _partition_of(declared: dict[str, Any] | None) -> str | None:
    """The frontmatter field this corpus splits into projections along, or None.

    Declared, never fixed, for the same reason `discriminator` is: the engine should not
    know the word `domain`. A corpus that declares no `partition:` has no projections at
    all — `architecture/` is abstract, and an idea has no one who fixes its name, so asking
    for a projection of it is a category error rather than an empty answer.
    """
    value = declared.get("partition") if declared else None
    return str(value) if value else None


def project(
    sources: list[dict[str, Any]], field: str | None, domains: list[str]
) -> list[dict[str, Any]]:
    """The sub-corpus whose `field` names any of `domains`. Not a filter over rows — a subgraph.

    A node claiming several domains appears in each of their projections, which is the whole
    point: a shared word is ONE vertex where two graphs meet, and scoring the union instead
    would blend two vocabularies into a single meaningless percentage.
    """
    if not field or not domains:
        return sources
    wanted = set(domains)
    out = []
    for source in sources:
        raw = source.get(field)
        claimed = {str(raw)} if isinstance(raw, str) else {str(x) for x in (raw or [])}
        if claimed & wanted:
            out.append(source)
    return out


def _discriminator_of(declared: dict[str, Any] | None) -> str:
    """The frontmatter field naming a source's kind: the declared override, or
    `DEFAULT_DISCRIMINATOR` absent one."""
    if declared and declared.get("discriminator"):
        return str(declared["discriminator"])
    return DEFAULT_DISCRIMINATOR


def check(data: Path, meta: Path, domains: list[str] | None = None) -> Fit:
    """Score `data` against the ontology declared at `meta`, optionally one projection of it.

    Single-ontology by scope (see module docstring): `meta` names its own schema
    rather than this function searching a registry of every ontology racecar
    could reach.

    `domains` scores ONE projection. A corpus that declares `partition:` holds several graphs
    in one, and their fit percentages are different numbers: `fact` is an Ansible kind that
    racecar has none of, so scoring the union averages two vocabularies into one figure
    that describes neither.
    """
    sources = sample(data)
    declared = load_ontology(meta)
    partition = _partition_of(declared)
    if domains:
        if partition is None:
            raise ValueError(
                f"{_ontology_path(meta)}: this corpus declares no `partition:`, so it has no "
                f"projections — cannot score --domain {', '.join(domains)}"
            )
        sources = project(sources, partition, domains)
    if not declared or not declared.get("kinds"):
        return Fit(best=None, unmapped_fraction=1.0, total=len(sources), by_kind={})

    name = str(declared.get("name") or "unnamed")
    kinds = declared["kinds"]
    if not acyclic_kinds(kinds):
        raise ValueError(
            f"{_ontology_path(meta)}: `kinds` has a cycle in `depends_on` — an "
            "ontology's own dependency graph must be acyclic"
        )
    base_required = (declared.get("base") or {}).get("required") or []
    discriminator = _discriminator_of(declared)

    matched = 0
    by_kind: dict[str, int] = {}
    for source in sources:
        raw_kind = source.get(discriminator)
        if not raw_kind:
            continue
        kind = str(raw_kind)
        spec = kinds.get(kind)
        if spec is None:
            continue
        required = [*base_required, *(spec.get("required") or [])]
        if all(field in source for field in required):
            matched += 1
            by_kind[kind] = by_kind.get(kind, 0) + 1

    total = len(sources)
    unmapped_fraction = 1.0 if total == 0 else 1 - (matched / total)
    best = name if unmapped_fraction < UNMAPPED_THRESHOLD else None
    return Fit(
        best=best, unmapped_fraction=unmapped_fraction, total=total, by_kind=by_kind
    )


_CARDINALITY_CHOICES = frozenset(
    {"one-to-one", "one-to-many", "many-to-one", "many-to-many"}
)


def relation_findings(  # pylint: disable=too-many-locals
    data: Path, meta: Path, topology_meta: Path | None = None
) -> list[str]:
    """Gate every content node's own USE of a declared relation — not just its kind
    and required fields (`check`'s job), but what it may point AT beyond
    containment. `pnode` already gets exactly this treatment in
    `lib.topology._walk.structural_findings`; this applies the same discipline to
    every OTHER relation an ontology declares under `relations:`, sibling to
    `kinds:` on the index (`ONTOLOGY.md` §"Relations are declared, not just
    containment") — bundled, not a node per relation. `kinds:` may be nodes
    (`_nodes.kind_nodes`) and relations deliberately are not:
    a kind is the thing a content node declares itself to BE and has prose of its
    own to carry, while a relation is an edge rule two kinds share and belongs
    where the pair is visible at once.

    Absent is a legitimate state: an ontology declaring no `relations:` returns no
    findings, the same policy `check` applies to a `data` with no declared
    ontology at all.

    A node USES a relation by carrying a frontmatter field named for it, valued
    as a list of references — exactly `pnode`'s own convention, resolved the same
    way (relative to the declaring node's own directory). `from`/`to` name the
    kinds the relation may connect (`"any"` or absent means unconstrained);
    `cardinality`, one of `one-to-one`/`one-to-many`/`many-to-one`/`many-to-many`,
    is checked by counting in/out-degree per node, absent means unconstrained —
    the same "filter out, not filter in" default the meta-ontology itself follows.
    """
    declared = load_ontology(meta)
    if not declared or not declared.get("relations"):
        return []
    relations = declared["relations"]
    nodes = _walk.load(data, topology_meta)

    errors: list[str] = []
    for name, spec in sorted(relations.items()):
        from_kind = spec.get("from")
        to_kind = spec.get("to")
        out_count: dict[str, int] = {}
        in_count: dict[str, int] = {}
        for nid, node in sorted(nodes.items()):
            refs = node.get(name)
            if not refs:
                continue
            if from_kind and from_kind != "any" and node.get("kind") != from_kind:
                errors.append(
                    f"{nid}: declares {name!r} but is kind {node.get('kind')!r}, "
                    f"not the declared `from: {from_kind}`"
                )
                continue
            for ref in refs:
                own_path = node["path"]
                base = own_path.parent if own_path.is_file() else own_path
                target_path = (base / ref).resolve()
                if not target_path.is_file():
                    errors.append(f"{nid}: {name} {ref!r} resolves to nothing")
                    continue
                try:
                    if target_path.name == "README.md":
                        target_id = target_path.parent.relative_to(data).as_posix()
                    else:
                        target_id = (
                            target_path.parent.relative_to(data) / target_path.stem
                        ).as_posix()
                except ValueError:
                    # Outside `data` entirely -- never a declared node either way.
                    target_id = (
                        target_path.parent.name
                        if target_path.name == "README.md"
                        else target_path.stem
                    )
                target = nodes.get(target_id)
                if target is None:
                    errors.append(
                        f"{nid}: {name} {ref!r} points outside the declared node set"
                    )
                    continue
                if to_kind and to_kind != "any" and target.get("kind") != to_kind:
                    errors.append(
                        f"{nid}: {name} -> {target_id} (kind "
                        f"{target.get('kind')!r}), not the declared `to: {to_kind}`"
                    )
                    continue
                out_count[nid] = out_count.get(nid, 0) + 1
                in_count[target_id] = in_count.get(target_id, 0) + 1

        cardinality = spec.get("cardinality")
        if cardinality in _CARDINALITY_CHOICES:
            from_one, to_one = cardinality.split("-to-")
            if from_one == "one":
                for target_id, count in sorted(in_count.items()):
                    if count > 1:
                        errors.append(
                            f"{name}: {target_id} has {count} incoming edges; "
                            f"declared `cardinality: {cardinality}` allows at most one"
                        )
            if to_one == "one":
                for nid, count in sorted(out_count.items()):
                    if count > 1:
                        errors.append(
                            f"{name}: {nid} has {count} outgoing edges; declared "
                            f"`cardinality: {cardinality}` allows at most one"
                        )
    return errors


def derive(data: Path, meta: Path | None = None, min_presence: float = 0.5) -> Proposal:
    """Propose kinds, required fields, and a best-effort DAG from `data` alone.

    Stops at the proposal. `min_presence` is the fraction of a kind's sampled
    nodes a field must appear on to be proposed as required — a field on one
    outlier is not a requirement. Reads `meta`'s declared `discriminator` when
    `meta` is given and declares one — a poor fit still knows which field names
    a source's kind, even though it does not know what each kind requires.
    """
    sources = sample(data)
    discriminator = _discriminator_of(load_ontology(meta) if meta else None)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        kind = source.get(discriminator)
        if kind:
            by_kind.setdefault(kind, []).append(source)

    kinds: dict[str, list[str]] = {}
    values_by_kind: dict[str, set[str]] = {}
    for kind, nodes in by_kind.items():
        counts: dict[str, int] = {}
        for node in nodes:
            for field in node:
                if field in (discriminator, "_path"):
                    continue
                counts[field] = counts.get(field, 0) + 1
        kinds[kind] = sorted(
            field
            for field, count in counts.items()
            if count / len(nodes) >= min_presence
        )
        values_by_kind[kind] = {
            str(value)
            for node in nodes
            for field, value in node.items()
            if field not in (discriminator, "_path")
        }

    # A best-effort DAG: kind A depends on kind B when a field VALUE on an A
    # node is literally a value declared somewhere on a B node — a referential
    # signal, not a semantic one. Anything subtler than that is exactly why the
    # result is a PROPOSAL rather than a schema: pattern matching starts the
    # judgement, the corpus owner finishes it.
    dag: dict[str, list[str]] = {}
    for kind, nodes in by_kind.items():
        deps: set[str] = set()
        for node in nodes:
            for field, value in node.items():
                if field in (discriminator, "_path"):
                    continue
                for other_kind, values in values_by_kind.items():
                    if other_kind != kind and str(value) in values:
                        deps.add(other_kind)
        if deps:
            dag[kind] = sorted(deps)

    if not acyclic_kinds({kind: {"depends_on": deps} for kind, deps in dag.items()}):
        # A cyclic guess is worse than none: refuse to propose it rather than
        # hand back a "DAG" that fails the one invariant an ontology owes.
        dag = {}

    return Proposal(kinds=kinds, dag=dag, total=len(sources))


def render_ontology_yaml(name: str, proposal: Proposal) -> str:
    """A `derive()` proposal, rendered as the `ontology.yaml` shape this module
    itself reads — what `derive --meta` writes."""
    doc: dict[str, Any] = {
        "name": name,
        "kinds": {
            kind: {
                "required": fields,
                **({"depends_on": proposal.dag[kind]} if kind in proposal.dag else {}),
            }
            for kind, fields in sorted(proposal.kinds.items())
        },
    }
    return yaml.safe_dump(doc, sort_keys=False)
