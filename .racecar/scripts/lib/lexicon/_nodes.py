"""Reading the graph: what a node declares, and where the declarations live.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A
caller imports what it needs: the tests, the `lexicon` noun's api and the delivered CLI
all reach the same functions instead of loading a script.

Complexity: O(N), N = nodes read (one frontmatter parse each, memoized per path)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from lib.lexicon._corpora import (
    DELIVERED,
    OWN,
    Corpus,
    Entry,
    Lexicon,
    LexiconError,
    lexicon_corpora,
)
from lib.shared import _frontmatter, _markdown
from lib.shared._root import find_repo_root

# The three exit codes, beside the error they sit next to. They live with the CHECKS rather
# than with the command line because a check is what decides which one a run earns; a surface
# only reports it.
OK, FINDINGS, UNMET = 0, 1, 2


# Three names for one error: all three mean the same thing.
NounspaceError = VocabularyError = NomenclatureError = LexiconError

#: The repo's own entries only: what a reader of the repo's commands, nouns and domains keeps.
OWN_ONLY = frozenset({OWN})

ONTOLOGY_REL = Path("ontology") / "README.md"


def _own_ontology(home: Corpus) -> Path:
    """ONE home's own ontology declaration: the first `ontology:` entry of its root node that
    exists, or the conventional location when it declares none."""
    declared = _frontmatter.load(home.path / "README.md").get("ontology") or []
    for entry in declared if isinstance(declared, list) else [declared]:
        # Normalized, not resolved: an entry may reach out of the home, and `home /
        # that` keeps the `..` in the middle of every path this hands to a FINDING.
        # Collapsing it is cosmetic for the filesystem and load-bearing for the reader;
        # `resolve()` would also make it absolute, which is not this function's to decide.
        candidate = Path(os.path.normpath(home.path / str(entry).rstrip("/")))
        if candidate.is_dir():
            return candidate / "README.md"
        if candidate.is_file():
            return candidate
    return home.path / ONTOLOGY_REL


def ontology_paths(lexicon: Lexicon) -> list[Path]:
    """**Step two for the ontology.** One declaration per home of the union, in precedence
    order, skipping a home that has none -- or the repo's own conventional location when
    no home has one, so a caller always has a path to name in a finding.
    """
    found = [_own_ontology(home) for home in lexicon.homes]
    return [path for path in found if path.is_file()] or [lexicon.own / ONTOLOGY_REL]


def ontology_path(lexicon: Lexicon) -> Path:
    """The corpus's OWN ontology, which is the first joined one.

    The first, not the only. Corpus-level statements -- `base`, `discriminator`,
    `partition` -- belong to the corpus and are read from here; the kinds are a union
    over `ontology_paths`.
    """
    return ontology_paths(lexicon)[0]


API_NAMES = ("api.py", "api")


def kind_of(path: Path) -> str:
    """A node's kind, read from its own frontmatter. One statement, and the only one.

    Deliberately NOT the directory. An ontology exists so that one tree can hold things of many
    kinds, each saying what it is. Deriving kind from the path welds the type system to
    the containment tree and leaves nowhere to state what a kind requires.

    The DIRECTORY would be a competing claim, not the declaration. With the frontmatter
    as the only statement there is nothing to disagree with, and `artifact/` does not
    read as a noun, because its README does not say so.
    """
    return str(_frontmatter.load(path).get("kind") or "")


def term_nodes(lexicon: Lexicon) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    """Every node that declares a kind, grouped by it. A node with no `kind:` is not a term.

    No filename or directory rule survives here: a README declaring `kind: noun` is a noun, a
    README declaring nothing is an index, and both can sit in the same tree. That is what the
    ontology is for.
    """
    out: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for entry in lexicon.nodes(origins=OWN_ONLY):
        if entry.kind:
            path = lexicon.path(entry)
            out.setdefault(entry.kind, []).append((path, _frontmatter.load(path)))
    return out


# What a kind NODE contributes to its kind's spec: a closed, declared set, not "every key
# that is not bookkeeping". A kind node is a node like any other and carries its own
# `name`/`summary`/`pnode`/`bearing`; sweeping those in would make one ontology parse
# differently depending on which of the two shapes it was written in, and the whole point
# is that the two shapes yield the same dict. The set is the meta-kind `kind` vocabulary
# declared at `architecture/ontology/ontology/kind.md`, not a shorter set invented here.
KIND_SPEC_KEYS = (
    "required",
    "optional",
    "depends_on",
    "precedence",
    "container",
    "abstract",
    "versioned",
)

#: The directory an ontology lives in, and whose name is what marks a graph-shaped one.
ONTOLOGY_DIRNAME = "ontology"


def is_kind_node(path: Path) -> bool:
    """Whether `path` declares a kind: `name:` (which kind) and `required:` (what it
    owes). Both, because `name:` alone is carried by every node in every corpus."""
    if path.name == "README.md":
        return False
    frontmatter = _frontmatter.load(path)
    return bool(frontmatter.get("name")) and "required" in frontmatter


def is_graph(meta: Path, declaration: Path) -> bool:
    """Whether `meta` is the GRAPH shape: a directory named `ontology`, indexed by its own
    `README.md`, holding at least one kind node.

    The NAME keeps a plain corpus root, content `.md` beside a `README.md`, from reading as
    a directory of kind nodes. The kind node is needed too: `docs/lexicon/graph/ontology/`
    is named `ontology` and holds a CLI noun's verb nodes, not a declaration.
    """
    return (
        meta.is_dir()
        and meta.name == ONTOLOGY_DIRNAME
        and declaration.name == "README.md"
        and any(is_kind_node(p) for p in meta.glob("*.md"))
    )


def kind_nodes(meta: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    """Every kind declared as its OWN node in the ontology directory `meta`, and where.

    The graph shape: one `.md` per kind beside the index, `name:` naming the kind (DECLARED,
    never the filename, as a content node's `kind:` is declared) and `required:` what
    it owes. A file beside the index that declares neither field is REPORTED, never skipped: a
    silently-dropped kind makes every node of it read as declaring a kind the ontology does
    not define, which points the finding at the content instead of at the declaration. A
    kind declared twice is reported too, because a kind has one home and picking a winner
    would mean the file said one thing and the checker did another.

    Raises `ValueError`, the refusal `ontology.py`'s callers already catch; `declared_kinds`
    turns it into the lexicon's own.
    """
    kinds: dict[str, dict[str, Any]] = {}
    where: dict[str, Path] = {}
    for path in sorted(meta.glob("*.md")):
        if path.name == "README.md":
            continue
        frontmatter = _frontmatter.load(path)
        if not frontmatter.get("name") or "required" not in frontmatter:
            raise ValueError(
                f"{path}: a kind node declares `name:` (the kind) and `required:` "
                "(the fields that kind owes, `[]` when none); this one declares "
                f"{sorted(frontmatter) or 'nothing'}"
            )
        name = str(frontmatter["name"])
        if name in where:
            raise ValueError(
                f"{path}: declares kind {name!r}, already declared by "
                f"{where[name]} — a kind has one home"
            )
        spec = {k: frontmatter[k] for k in KIND_SPEC_KEYS if k in frontmatter}
        spec["_pnode"] = frontmatter.get("pnode") or []
        kinds[name] = spec
        where[name] = path
    return kinds, where


def _supertypes(
    kinds: dict[str, dict[str, Any]], where: dict[str, Path]
) -> dict[str, list[str]]:
    """Each kind's supertypes: the `pnode` entries that resolve to another kind node.

    **A kind's `pnode` is inheritance**: a kind filed under another kind narrows it. A
    `pnode` landing outside the kind set is containment and inherits nothing.
    """
    by_path = {path.resolve(): name for name, path in where.items()}
    supers: dict[str, list[str]] = {}
    for name in kinds:
        own = where[name]
        parents = []
        for ref in kinds[name]["_pnode"]:
            parent = by_path.get((own.parent / str(ref)).resolve())
            if parent is not None and parent != name and parent not in parents:
                parents.append(parent)
        supers[name] = parents
    return supers


def inherit(
    kinds: dict[str, dict[str, Any]], where: dict[str, Path]
) -> dict[str, dict[str, Any]]:
    """Every kind's spec with its supertypes' folded in, supertype first.

    Only the LIST-valued spec keys are inherited -- `required`, `optional`, `depends_on` --
    because those say what an instance carries, and a narrowing carries everything its
    supertype does plus its own. The scalar ones are not: `abstract` is the clearest case,
    since a subkind of an abstract kind is normally the concrete one.

    A kind that inherits from itself through `pnode` is refused (`ValueError`). Stopping the
    walk instead would grade a corpus against an ontology the ontology reader refuses to
    load.
    """
    supers = _supertypes(kinds, where)
    resolved: dict[str, dict[str, Any]] = {}
    state: dict[str, int] = {}

    def walk(name: str) -> dict[str, Any]:
        if state.get(name) == 2:
            return resolved[name]
        if state.get(name) == 1:
            raise ValueError(
                f"{where[name]}: kind {name!r} inherits from itself through "
                "`pnode` — a graph of kinds must be acyclic"
            )
        state[name] = 1
        own = {k: v for k, v in kinds[name].items() if k != "_pnode"}
        inherited: dict[str, list[Any]] = {}
        for parent in supers[name]:
            for key, value in walk(parent).items():
                if not isinstance(value, list):
                    continue
                acc = inherited.setdefault(key, [])
                acc.extend(v for v in value if v not in acc)
        spec = dict(own)
        for key, acc in inherited.items():
            spec[key] = [*acc, *(v for v in (own.get(key) or []) if v not in acc)]
        state[name] = 2
        resolved[name] = spec
        return spec

    return {name: walk(name) for name in kinds}


def graph_kinds(
    meta: Path, declaration: Path, declared: dict[str, Any]
) -> dict[str, dict[str, Any]] | None:
    """The resolved kinds of the GRAPH-shaped ontology at `meta`, or None when it is a
    document (its index's own `kinds:` block, or no kinds at all).

    ONE implementation, read by both `declared_kinds` here and `ontology.load_ontology`.

    `declared` is the index's own frontmatter. An index carrying a `kinds:` block beside kind
    nodes is refused: an ontology is a document or a graph, never both.
    """
    if not is_graph(meta, declaration):
        return None
    kinds, where = kind_nodes(meta)
    if declared.get("kinds"):
        raise ValueError(
            f"{declaration}: declares a `kinds:` block AND has kind nodes beside it "
            f"({', '.join(sorted(kinds))}) — an ontology is a document or a "
            "graph, never both"
        )
    return inherit(kinds, where)


def _one_ontology_kinds(path: Path) -> dict[str, Any]:
    """The kinds ONE declaration at `path` holds -- the kind nodes beside it when it is a
    graph, its own `kinds:` block when it is a document.

    A declaration the shared reader refuses is a `LexiconError`: the lexicon cannot be graded
    against an ontology that does not load, and a run that skipped it would grade every node
    of the missing kind as declaring a kind nothing defines.
    """
    declared = _frontmatter.load(path)
    try:
        graph = graph_kinds(path.parent, path, declared)
    except ValueError as err:
        raise LexiconError(str(err)) from err
    if graph is not None:
        return graph
    kinds = declared.get("kinds")
    return dict(kinds) if isinstance(kinds, dict) else {}


def declared_kinds(lexicon: Lexicon) -> dict[str, Any]:
    """The kinds the ontologies of the union declare -- the UNION over every tree its
    index names, each read as its index's own `kinds:` block when it is a document and as
    the kind nodes beside that index when it is a graph.

    A union over `lexicon_corpora`: the repo's own tree and the one racecar delivers are two
    halves of one kind system, and a reader that stopped at the first would report every
    node of a delivered kind as declaring a kind nothing defines.

    **A kind declared in more than one corpus resolves to the first one**, and `lexicon_corpora` is
    what puts them in order: custom, then the repo's own, then the delivered corpus. The most
    specific declaration wins and canon is the fallback, so a repo CAN narrow a delivered
    kind -- `verb: {required: [params, handler]}` locally keeps asking for `handler` even
    where canon ships a plainer `verb`, and a local corpus that drops a field canon asks for
    is likewise obeyed. `shadowed_kinds` is how that resolution is reported rather than
    silent, which is what keeps a quieter gate visible.

    How ONE declaration yields its kinds is `graph_kinds`, the same function
    `ontology.load_ontology` reads, so the lexicon and the ontology reader cannot disagree
    about what a corpus declares. The join here is the union `load_ontology` also makes.
    """
    out: dict[str, Any] = {}
    for path in ontology_paths(lexicon):
        for name, spec in _one_ontology_kinds(path).items():
            out.setdefault(name, spec)
    return out


def shadowed_kinds(lexicon: Lexicon) -> dict[str, Path]:
    """Every kind declared in more than one of the joined corpora, mapped to the
    declaration whose copy LOST.

    Empty in the ordinary case. It is not a finding -- a repo is allowed to restate a
    delivered kind, and that is how it narrows one -- but it is never silent either: two
    files claiming one kind is exactly the state where a reader needs to be told which
    one the gate read.
    """
    seen: set[str] = set()
    out: dict[str, Path] = {}
    for path in ontology_paths(lexicon):
        for name in _one_ontology_kinds(path):
            if name in seen:
                out[name] = path
            else:
                seen.add(name)
    return out


def declared_nouns(lexicon: Lexicon) -> dict[tuple[str, ...], Path]:
    """Every node declaring `kind: noun`, keyed by its chain, in every domain.

    The chain is the node's DIRECTORY path, which is the whole projection claim: the position
    says which node it is, the frontmatter says what kind of thing it is. The empty chain is the
    root package — `docs/lexicon/README.md` mirrors `python -m <pkg>`. Which of them a run
    acts on is `eligible_nouns`'s question, not this one's.
    """
    return {
        entry.parts: lexicon.path(entry)
        for entry in lexicon.nodes(origins=OWN_ONLY, kind="noun")
    }


def declared_verbs(lexicon: Lexicon, chain: tuple[str, ...]) -> set[str]:
    """The verbs a noun answers to: the `kind: verb` nodes sitting beside its README.

    An EMPTY SET satisfies every claim made about it, so a filter that matches no node
    leaves the half of the projection that asks "does the noun's api expose each
    declared verb?" silently asserting nothing.
    """
    return {
        entry.stem
        for entry in lexicon.nodes(origins=OWN_ONLY, kind="verb")
        if entry.parts == chain and entry.filename != "README.md"
    }


def render(problems: list[str]) -> str:
    """The gate's one-block report, the shape `racecar.arch` composes from every checker."""
    if not problems:
        return "nounspace: OK"
    lines = [f"nounspace: {len(problems)} finding(s)"]
    lines += [f"  - {line}" for line in problems]
    return "\n".join(lines)


def has_nounspace(root: Path) -> bool:
    """Whether this repo declares a nounspace at all.

    The predicate `racecar.arch` uses to decide the repo is a subject of this rule. An
    adopter with no term tree is not failing the rule; the rule does not reach them, which
    is the same shape the Django and server guards already use.
    """
    return bool(declared_kinds(lexicon_corpora(root)))


SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".collections",
}

DOC_SUFFIXES = (".md",)

CODE_SUFFIXES = (".py", ".sh", ".mk")


def find_root(start: Path | None = None) -> Path:
    """The repo under check — STRICTLY, unlike the shared walk-up it wraps.

    Keyed on the repo rather than on a term tree because this script is delivered to
    adopters, and an adopter has no lexicon of its own. Finding the root must succeed
    there; finding nothing to check is then a legitimate answer rather than a failure to
    locate the repo. Keying on the tree would let the walk leave the repo entirely: a
    checkout nested under any directory that carries `docs/lexicon/` would be checked
    against that.

    So the strictness lives HERE, at one visible line, rather than in a private variant of
    the walk-up: `find_repo_root` returns its starting point when there is no `.git`, and
    that fallback is exactly the "broken run" this script refuses to make silent.
    """
    root = find_repo_root(start)
    if not ((root / ".racecar").is_dir() or (root / ".git").exists()):
        raise LexiconError(f"no repo root (no .racecar/ or .git) at or above {root}")
    return root


DEFAULT_DOMAIN = "racecar"


def noun_count(lexicon: Lexicon) -> int:
    """How many nouns this repo's own lexicon declares."""
    return len(lexicon.nodes(origins=OWN_ONLY, kind="noun"))


def partition_field(lexicon: Lexicon) -> str | None:
    """The field this lexicon partitions on, or None when it declares none.

    Opt-in per corpus, exactly as the graph engine treats it. An adopter's lexicon that
    declares no `partition:` has no domains and owes none -- forcing `domain:` onto every
    node of a single-domain tree would be a field with one value everywhere, which says
    nothing.
    """
    declared = _frontmatter.load(ontology_path(lexicon))
    value = declared.get("partition")
    return str(value) if value else None


def domains_of(node: Path) -> list[str]:
    """The domains a node declares. Absent is NOT "every domain" -- it is a finding here."""
    raw = _frontmatter.load(node).get("domain")
    if isinstance(raw, str):
        return [raw.strip()]
    return [str(d).strip() for d in raw] if isinstance(raw, list) else []


def declared_domains(lexicon: Lexicon) -> list[str]:
    """Every domain any of the repo's own nodes claims: the set `--domain` is validated
    against."""
    seen: set[str] = set()
    for entry in lexicon.nodes(origins=OWN_ONLY):
        seen.update(domains_of(lexicon.path(entry)))
    return sorted(seen)


def graded_here(node: Path, lexicon: Lexicon) -> bool:
    """Whether this repo's checks grade `node`: every node except one racecar delivered.

    The delivered copy (`.racecar/docs/lexicon`) is the one thing imported into the repo. It
    is racecar's to fix, and racecar grades it where it writes it; graded here, a finding would
    land on a file the next sync overwrites. Every other node is the repo's own file, whatever
    its `domain:` says. racecar's own canon is authored in place, not delivered, so racecar
    grades it.
    """
    entry = lexicon.entry_of(node)
    return entry is None or entry.origin != DELIVERED


def _sections(node: Path) -> set[str]:
    """The `## <name>` headings a node carries, lowercased."""
    return {h.title.strip().lower() for h in _markdown.read(node).headings(2)}


def _has_prose(node: Path) -> bool:
    """Whether a node says anything beyond its own headings.

    The test for a stub, and it is deliberately about CONTENT rather than a marker. A
    `bearing: draft` marker is also carried by hand-authored words whose author marked
    them draft on purpose, and a stub marked the same way hides among them.

    Emptiness cannot be gamed the way a field can. A node with a heading, a per-domain
    section header and nothing under either has not been written, whoever set its bearing.
    """
    doc = _markdown.read(node)
    return any(
        line.text.strip() and doc.heading_at(line.no) is None for line in doc.body()
    )


def _is_command(entry: Entry, lexicon: Lexicon) -> bool:
    """A verb node is a COMMAND when it sits under a noun; under a kind bucket it is a meaning.

    `graph/check.md` is `racecar.graph check`. `verb/check.md` is what the word means where it
    cuts across nouns, and addresses nothing. The test is the neighbour, not the filename: a
    noun directory carries a `README.md` declaring `kind: noun`.
    """
    if not entry.parts:
        return True
    parent = lexicon.at("/".join((*entry.parts, "README.md")), entry.origin)
    return parent is not None and parent.kind == "noun"


def _params_of(node: Path) -> list[str]:
    raw = _frontmatter.load(node).get("params")
    return [str(p) for p in raw] if isinstance(raw, list) else []


def _declared_name(lexicon: Lexicon) -> str | None:
    """The `name:` a corpus's root node declares, or None when it declares none.

    One read, two callers. `root_noun` and `corpus_domain` both want this string and want
    different answers when it is absent, so the read is here and each states its own
    fallback.
    """
    # The repo's own root node, read where the repo's own home is, so a name `declare` has
    # just written is the name read back.
    declared = _frontmatter.load(lexicon.own / "README.md").get("name")
    return str(declared).strip('"') if declared else None


def root_noun(lexicon: Lexicon) -> str:
    """What the root package is called, read from the node that declares it.

    The empty chain is the root, and it has no directory segment to be named by.

    The node's own `name:` is the answer, not the package directory: it is the declaration,
    and it is what every other noun in this graph is named by.

    Shares its reader with `corpus_domain` and differs only in what it falls back to. Both
    ask the root node for one string; a noun with no declaration is named by its directory,
    and a projection with no declaration is `DEFAULT_DOMAIN`. Two fallbacks, one read.
    """
    return _declared_name(lexicon) or lexicon.own.name


def corpus_domain(lexicon: Lexicon) -> str:
    """The domain a run acts on when `--domain` names none: the corpus's own.

    A lexicon's root node declares the name its words are fixed under, and every node below
    it claims that name in `domain:`. So the default projection is a question the corpus
    already answers, and reading it is the only way the answer can be right in more than one
    repo.

    A literal domain is correct in exactly one checkout and wrong in every other, and
    fails silently: a run in a repo whose nodes say `domain: [acme]` would select a
    domain no node there declares, so `list` prints zero rows and `check` reports each
    of that repo's nouns as undeclared. `DEFAULT_DOMAIN` is the answer for a corpus with
    no root node to ask.
    """
    return _declared_name(lexicon) or DEFAULT_DOMAIN


def verb_node(lexicon: Lexicon, noun: str, verb: str | None) -> Path:
    """Where one tuple's node lives. A dotted noun is the directories it nests in.

    The inverse of the chain `tuples()` walks, written here once so the two cannot part
    company. The root noun is the empty chain -- its verbs sit directly under the
    lexicon, with no directory of their own -- which is the same asymmetry `root_noun`
    exists to absorb.

    A tuple with no verb is the noun itself, and its node is the noun's README. Formatting
    `None` into a filename would give `nav/None.md`.

    In the repo's own home: a tuple is the repo's own command, and that is also where a
    writer puts one.
    """
    chain = () if noun == root_noun(lexicon) else tuple(noun.split("."))
    leaf = "README.md" if verb is None else f"{verb}.md"
    return lexicon.own.joinpath(*chain, leaf)


#: The param fields a node may omit, and what omitting one means (`param.md` in the ontology).
#: `required`: the verb refuses to run without it. `defined`: a person has written what it is;
#: a node a `create` wrote is not, and says so. `position`: the verbs, as `<noun>.<verb>`, that
#: take it by position rather than as a `--flag`.
PARAM_DEFAULTS: dict[str, Any] = {"required": False, "defined": False, "position": []}


def param_fields(meta: dict[str, Any]) -> dict[str, Any]:
    """A param node's `required`, `defined` and `position`, each defaulted where absent."""
    return {
        "required": meta.get("required") is True,
        "defined": meta.get("defined") is True,
        "position": [str(v) for v in meta.get("position") or []],
    }


def describe(lexicon: Lexicon, noun: str, verb: str | None = None) -> dict[str, Any]:
    """What the lexicon declares for one noun, or one of its verbs, as data.

    `{"noun": noun, "summary": ..., "verbs": {verb: {"summary": ..., "params":
    [{"name", "type", "summary", "required", "defined", "position"}, ...]}}}`, every verb
    when `verb` is None. A param with
    no node of its own, or a node that declares no `type`, comes back with type `None`;
    what a reader does with that is the reader's choice. Raises `LexiconError` when the
    noun, or the named verb, is not declared.
    """
    readme = verb_node(lexicon, noun, None)
    if not readme.is_file():
        raise LexiconError(f"{noun}: not declared ({readme} does not exist)")
    chain = () if noun == root_noun(lexicon) else tuple(noun.split("."))
    wanted = sorted(declared_verbs(lexicon, chain)) if verb is None else [verb]
    verbs: dict[str, Any] = {}
    for name in wanted:
        node = verb_node(lexicon, noun, name)
        if not node.is_file():
            raise LexiconError(f"{noun} {name}: not declared ({node} does not exist)")
        params = []
        for param in _params_of(node):
            # The param's node as the union resolves it: a word racecar delivers is
            # described from the delivered node when the repo holds none of its own.
            found = lexicon.find(f"param/{param}.md")
            meta = _frontmatter.load(found) if found is not None else {}
            params.append(
                {
                    "name": param,
                    "type": meta.get("type"),
                    "summary": meta.get("summary"),
                    **param_fields(meta),
                }
            )
        verbs[name] = {
            "summary": _frontmatter.load(node).get("summary"),
            "params": params,
        }
    return {
        "noun": noun,
        "summary": _frontmatter.load(readme).get("summary"),
        "verbs": verbs,
    }
