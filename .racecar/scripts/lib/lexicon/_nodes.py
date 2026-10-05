"""Reading the graph: what a node declares, and where the declarations live.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A
caller imports what it needs: the tests, the `lexicon` noun's api and the delivered CLI
all reach the same functions instead of loading a script.

Complexity: O(N), N = nodes read (one frontmatter parse each, memoized per path)
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

from lib.shared import _constants, _frontmatter
from lib.shared._root import find_repo_root

# The three exit codes, beside the error they sit next to. They live with the CHECKS rather
# than with the command line because a check is what decides which one a run earns; a surface
# only reports it.
OK, FINDINGS, UNMET = 0, 1, 2


class LexiconError(Exception):
    """The lexicon cannot be graded at all — a broken run, not a finding."""


# Three names for one error: all three mean the same thing.
NounspaceError = VocabularyError = NomenclatureError = LexiconError

DEFAULT_TERMS = Path("docs") / "lexicon"

# The two corpora that JOIN, in resolution order. `docs/lexicon` is the repo's own words;
# `.racecar/docs/lexicon` is the half racecar DELIVERS, at the same relative position in
# every governed repo. Each is ignored when it is not on disk.
#
# Hardcoded rather than declared because there is nothing for a declaration to decide --
# every governed repo has these two or fewer -- and because a repo that had to declare the
# delivered tree before it was read would spend the whole window between the sync and the
# edit reporting every node of a delivered kind as declaring a kind nothing defines.
# Anything BEYOND the pair is declared, at `[tool.racecar.lexicon] corpora` in
# pyproject.toml, which is where a project's own bindings already live.
CORPUS_REL = Path("docs") / "lexicon"

# The provenance stamps racecar writes at the boundary root: git's own tree object id for
# each tree it delivered, ONE PER TREE. Not one umbrella sha over `.racecar/` -- the two
# halves are delivered by different rules and answer different questions, and a single
# number could only ever say "something under here changed", which names nothing and is
# repaired by nothing.
#
# What they buy is ONE question per tree: are these still the bytes racecar shipped? A
# delivered kind node is read as DATA, and a `required:` list edited by hand in the
# delivered half changes what every gate in the repo demands while still looking like canon.
# A delivered CHECKER is worse -- it IS the gate. The stamps do not prevent either; nothing
# in a repo can. They make the tree say so.
#
# Absent stamp means trust it: a tree delivered without a stamp, or placed by hand, is
# not evidence of tampering. A stamp that DISAGREES is, and the lexicon's disagreement
# drops the delivered corpus from the join -- ignored, not an error, because a mangled
# delivery is the author's own doing and it must not take the repo's own lexicon down with
# it.
#
# Read from `lib.shared._constants`, which is the DELIVERED mirror of
# `racecar.lib.delivery.record` -- the side that writes them. This file cannot import the
# library and does not need to: the mirror sits beside it in the same delivered directory,
# and `find_repo_root` already comes from there.
DELIVERY_ROOT = _constants.DELIVERY_ROOT
LEXICON_STAMP_REL = _constants.LEXICON_STAMP_REL
SCRIPTS_STAMP_REL = _constants.SCRIPTS_STAMP_REL

# Paths already reported as mismatched, so a join that runs once per corpus root does not
# print the same line ten times.
_STAMP_REPORTED: set[str] = set()

ONTOLOGY_REL = Path("ontology") / "README.md"


def _pyproject_of(terms: Path) -> Path | None:
    """The nearest `pyproject.toml` at or above `terms`, or None.

    Walked rather than taken from `find_repo_root`, because this must answer for a corpus
    that is not in a git checkout at all -- a fixture, or a tree being scaffolded.
    """
    for parent in [terms.resolve(), *terms.resolve().parents]:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _declared_corpora(terms: Path) -> list[Path]:
    """The extra corpora `[tool.racecar.lexicon] corpora` names, as paths under the root
    that declares them. Absent table, absent key and a non-list value all mean none.

    Hand-parsed, not `tomllib`: this module is delivered into repos running Python
    versions racecar does not pick, and the one value it wants is a list of strings under
    a named table. A shape it cannot read yields no corpora, which is the same answer as
    declaring none.
    """
    pyproject = _pyproject_of(terms)
    if pyproject is None:
        return []
    root = pyproject.parent
    out: list[Path] = []
    in_table = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_table = stripped.rstrip() == "[tool.racecar.lexicon]"
            continue
        if not in_table or not stripped.startswith("corpora"):
            continue
        _, _, value = stripped.partition("=")
        for item in re.findall(r"""["']([^"']+)["']""", value):
            out.append(root / item.rstrip("/"))
    return out


def _is_corpus_root(terms: Path) -> bool:
    """Whether `terms` is a corpus ROOT (`.../docs/lexicon`) rather than a node inside one.

    The guard that keeps the join from firing on a directory that merely sits under a
    corpus. `docs/lexicon/graph/` holds a CLI noun, and walking up from it would find the
    delivered corpus and fold another repo's kinds into one noun's ontology -- an ontology
    assembled out of position rather than out of a declaration.
    """
    return terms.name == CORPUS_REL.name and terms.parent.name == CORPUS_REL.parent.name


def _blob_sha(path: Path) -> bytes:
    """git's blob object id for one file, raw. `sha1("blob <len>\\0" + bytes)`."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).digest()


def is_bytecode(name: str) -> bool:
    """Whether `name` is something the interpreter writes beside a delivered module.

    `__pycache__/` and `*.pyc` / `*.pyo`: what `templates/classic/gitignore` ignores, so what
    git leaves out of the tree `tree_sha` has to agree with. The ONE statement of it, because
    it has two readers that must agree: `tree_sha` leaves these out of the hash, and sync
    deletes them from `.racecar/` before it runs. A delete that removed one set while the
    hash skipped another would leave the stamp wrong for whatever fell between them.
    """
    return name == "__pycache__" or name.endswith((".pyc", ".pyo"))


def tree_sha(root: Path) -> str:
    """git's tree object id for a directory, computed without git and without writing.

    **THE AUTHORED HOME.** `racecar.lib._corpora` wraps this rather than copying it, the
    same direction `racecar.lexicon.lib._graph` states for the tuple list: a delivered file
    cannot import the library, so the library imports the delivered file and there is one
    implementation. Two spellings of a hash is how a stamp comes to disagree with itself on
    a tree nobody touched -- an accusation of tampering that the tool itself manufactured.

    The whole point of matching git's own algorithm rather than inventing a digest is that
    the recorded value is reproducible by hand: `git rev-parse <ref>:.racecar/scripts` in the
    repo that received it prints the same forty characters. A checksum of our own devising
    would be a number only this code can explain.

    Entries sort by name with a directory sorted as `name/` -- git's rule, and getting it
    wrong yields a plausible sha that matches nothing. Mode is `100644` or `100755` off the
    execute bit; symlinks and submodules cannot appear in a delivered corpus of markdown.

    Bytecode is left out (`is_bytecode`), because git leaves it out. Running any delivered
    checker writes `.racecar/scripts/lib/**/__pycache__/`, and hashing it would make
    every later sync rewrite a stamp nothing changed, and write one that matches no
    commit.
    """
    entries: list[tuple[bytes, bytes, bytes]] = []
    for child in sorted(
        (p for p in root.iterdir() if not is_bytecode(p.name)),
        key=lambda p: p.name + ("/" if p.is_dir() else ""),
    ):
        if child.is_dir():
            entries.append(
                (b"40000", child.name.encode(), bytes.fromhex(tree_sha(child)))
            )
        else:
            mode = b"100755" if child.stat().st_mode & 0o111 else b"100644"
            entries.append((mode, child.name.encode(), _blob_sha(child)))
    body = b"".join(mode + b" " + name + b"\0" + sha for mode, name, sha in entries)
    return hashlib.sha1(
        b"tree %d\0" % len(body) + body, usedforsecurity=False
    ).hexdigest()


def _delivered_is_intact(delivery_root: Path, corpus: Path) -> bool:
    """Whether the delivered corpus still holds the bytes the stamp says racecar delivered.

    True when there is no stamp, when it is empty, and when it agrees. False only when a
    stamp exists and names a different tree -- and that False drops the delivered corpus
    from the join rather than raising, with one line on stderr so the drop is not silent.
    A silent skip is the shape of every checker that passes because it read nothing.
    """
    stamp = delivery_root / LEXICON_STAMP_REL
    if not stamp.is_file():
        return True
    recorded = stamp.read_text(encoding="utf-8").split()
    if not recorded or recorded[0] == tree_sha(corpus):
        return True
    key = str(corpus)
    if key not in _STAMP_REPORTED:
        _STAMP_REPORTED.add(key)
        print(
            f"lexicon: {corpus} does not match the tree {stamp} records "
            f"({recorded[0][:12]}) -- the delivered corpus is edited, and it is left OUT "
            "of the join. Re-run the sync to restore it.",
            file=sys.stderr,
        )
    return False


#: The delivered corpus has TWO positions, and they are the same corpus seen from each end of
#: the delivery. `docs/rc_lexicon` is where it is AUTHORED, which is the position racecar
#: itself has and no adopter does; `.racecar/docs/lexicon` is where it LANDS. Both are read
#: here so racecar joins its own canon by POSITION, exactly as an adopter does, and therefore
#: at the same precedence. Declaring it instead (`[tool.racecar.lexicon] corpora`) would
#: put it on the CUSTOM leg, which outranks the repo's own corpus -- the opposite order
#: from the one racecar ships.
#:
#: **AUTHORED FIRST, and that order is the whole of it.** A repo can hold both at once:
#: syncing racecar into itself is allowed, and the manifest's document rows write
#: `.racecar/docs/lexicon/` when it happens. Read received-first, the copy would shadow the
#: file racecar authors -- editing `docs/rc_lexicon/ontology/verb.md` would then change
#: nothing until the next sync, and the provenance stamp would agree because the bytes matched
#: when it was written. Two homes for one fact with the drift invisible, which is the failure
#: this repo exists to catch. Authored beats received, the same way a declared corpus beats
#: the repo's own and the repo's own beats canon: the more specific statement wins.
DELIVERED_RELS = (Path("docs") / "rc_lexicon", Path(DELIVERY_ROOT) / CORPUS_REL)


def delivered_corpus(terms: Path) -> Path | None:
    """The delivered corpus at either of its two positions, or None when neither is there.

    Found by walking up from `terms` rather than computed from a repo root, for the same
    reason `_pyproject_of` walks: this must answer for a corpus that is not in a git
    checkout at all. The two corpora are not siblings, so the relationship is stated here
    rather than spelled into every path that needs it.

    A corpus whose provenance stamp disagrees with it is not returned at all -- it is dropped
    from the join rather than trusted, and `_delivered_is_intact` says so on stderr.
    """
    for parent in [terms.resolve(), *terms.resolve().parents]:
        for rel in DELIVERED_RELS:
            candidate = parent / rel
            if candidate.is_dir():
                if not _delivered_is_intact(parent / DELIVERY_ROOT, candidate):
                    return None
                return candidate
    return None


def corpora(terms: Path) -> list[Path]:
    """**Step one, and the one home for it.** The corpus roots that JOIN to make the corpus
    `terms` names, in RESOLUTION ORDER. Every entry exists; an absent one is skipped, never
    an error.

    THE ORDER IS THE PRECEDENCE RULE, and everything downstream inherits it:

        custom  >  the repo's own `docs/lexicon`  >  the delivered corpus

    Custom first: a corpus a project went out of its way to declare at
    `[tool.racecar.lexicon] corpora` is the most specific statement in the repo, and a
    declaration that could be overruled by the thing it was written to override would be
    pointless. The repo's own corpus next. Canon LAST, as the fallback — a delivered kind
    supplies what nothing local says, and yields wherever something local does.

    That means an adopter CAN narrow a delivered kind's `required:` and the narrower list
    wins. It is a deliberate trade: `required:` composes with `base.required`, so a local
    answer that wins can make a gate quieter than canon wrote it. The alternative — canon
    first — makes canon unoverridable, and a repo that cannot disagree with a default has no
    way to be right when the default is wrong for it. Both readers print which copy was
    shadowed, so a quieter gate is visible rather than silent.

    One home because the order of operations is the same for all three declarations: join the
    sources, generate the ontology / topology / graph from the union, then operate on
    that. The ontology's second step is
    `ontology_paths` here and `lib.ontology._kinds._ontology_sources`; the topology's is
    `lib.topology._walk._topology_sources`. The graph's data walk reads
    one tree, and it will read this function rather than a second copy of it.

    `_is_corpus_root` is what keeps this from firing on a directory that merely sits under a
    corpus -- see its own note.
    """
    if not _is_corpus_root(terms) or not terms.is_dir():
        return [terms]
    delivered = delivered_corpus(terms)
    ordered = [
        *_declared_corpora(terms),
        terms,
        *([delivered] if delivered else []),
    ]
    out: list[Path] = []
    seen: set[Path] = set()
    for candidate in ordered:
        if candidate.is_dir() and candidate.resolve() not in seen:
            seen.add(candidate.resolve())
            out.append(candidate)
    return out


def _own_ontology(terms: Path) -> Path:
    """ONE corpus's own ontology declaration: the first `ontology:` entry that exists, or
    the conventional location when it declares none."""
    declared = _frontmatter.load(terms / "README.md").get("ontology") or []
    for entry in declared if isinstance(declared, list) else [declared]:
        # Normalized, not resolved: an entry may reach out of the corpus, and `terms /
        # that` keeps the `..` in the middle of every path this hands to a FINDING.
        # Collapsing it is cosmetic for the filesystem and load-bearing for the reader;
        # `resolve()` would also make it absolute, which is not this function's to decide.
        candidate = Path(os.path.normpath(terms / str(entry).rstrip("/")))
        if candidate.is_dir():
            return candidate / "README.md"
        if candidate.is_file():
            return candidate
    return terms / ONTOLOGY_REL


def ontology_paths(terms: Path) -> list[Path]:
    """**Step two for the ontology.** One declaration per joined corpus (`corpora`), in
    that order, skipping a corpus that has none -- or the conventional location when the
    join yields nothing at all, so a caller always has a path to name in a finding.
    """
    found = [_own_ontology(corpus) for corpus in corpora(terms)]
    return [path for path in found if path.is_file()] or [terms / ONTOLOGY_REL]


def ontology_path(terms: Path) -> Path:
    """The corpus's OWN ontology, which is the first joined one.

    The first, not the only. Corpus-level statements -- `base`, `discriminator`,
    `partition` -- belong to the corpus and are read from here; the kinds are a union
    over `ontology_paths`.
    """
    return ontology_paths(terms)[0]


API_NAMES = ("api.py", "api")


def kind_of(path: Path, terms: Path) -> str:  # pylint: disable=unused-argument
    """A node's kind, read from its own frontmatter. One statement, and the only one.

    Deliberately NOT the directory. An ontology exists so that one tree can hold things of many
    kinds, each saying what it is. Deriving kind from the path welds the type system to
    the containment tree and leaves nowhere to state what a kind requires.

    The DIRECTORY would be a competing claim, not the declaration. With the frontmatter
    as the only statement there is nothing to disagree with, and `artifact/` does not
    read as a noun, because its README does not say so.
    """
    return str(_frontmatter.load(path).get("kind") or "")


def pages(terms: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every page under `terms`, in path order, each with its frontmatter.

    The one walk of a lexicon tree. Every reader that needs the tree's pages takes this
    list and filters it; none walks the tree itself.
    """
    if not terms.is_dir():
        return []
    return [(path, _frontmatter.load(path)) for path in sorted(terms.rglob("*.md"))]


def term_nodes(terms: Path) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    """Every node that declares a kind, grouped by it. A node with no `kind:` is not a term.

    No filename or directory rule survives here: a README declaring `kind: noun` is a noun, a
    README declaring nothing is an index, and both can sit in the same tree. That is what the
    ontology is for.
    """
    out: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for path, meta in pages(terms):
        kind = str(meta.get("kind") or "")
        if kind:
            out.setdefault(kind, []).append((path, meta))
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


def declared_kinds(terms: Path) -> dict[str, Any]:
    """The kinds the ontologies under `terms` declare -- the UNION over every tree its
    index names, each read as its index's own `kinds:` block when it is a document and as
    the kind nodes beside that index when it is a graph.

    A union over `corpora`: the repo's own tree and the one racecar delivers are two
    halves of one kind system, and a reader that stopped at the first would report every
    node of a delivered kind as declaring a kind nothing defines.

    **A kind declared in more than one corpus resolves to the first one**, and `corpora` is
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
    for path in ontology_paths(terms):
        for name, spec in _one_ontology_kinds(path).items():
            out.setdefault(name, spec)
    return out


def shadowed_kinds(terms: Path) -> dict[str, Path]:
    """Every kind declared in more than one of the joined corpora, mapped to the
    declaration whose copy LOST.

    Empty in the ordinary case. It is not a finding -- a repo is allowed to restate a
    delivered kind, and that is how it narrows one -- but it is never silent either: two
    files claiming one kind is exactly the state where a reader needs to be told which
    one the gate read.
    """
    seen: set[str] = set()
    out: dict[str, Path] = {}
    for path in ontology_paths(terms):
        for name in _one_ontology_kinds(path):
            if name in seen:
                out[name] = path
            else:
                seen.add(name)
    return out


NOUNSPACE_REL = Path(".")


def declared_nouns(nounspace: Path) -> dict[tuple[str, ...], Path]:
    """Every node declaring `kind: noun`, keyed by its chain, in every domain.

    The chain is the node's DIRECTORY path, which is the whole projection claim: the position
    says which node it is, the frontmatter says what kind of thing it is. The empty chain is the
    root package — `docs/lexicon/README.md` mirrors `python -m <pkg>`. Which of them a run
    acts on is `eligible_nouns`'s question, not this one's.
    """
    found: dict[tuple[str, ...], Path] = {}
    for node, meta in pages(nounspace):
        if str(meta.get("kind") or "") != "noun":
            continue
        rel = node.parent.relative_to(nounspace)
        found[() if rel == Path(".") else rel.parts] = node
    return found


def declared_verbs(nounspace: Path, chain: tuple[str, ...]) -> set[str]:
    """The verbs a noun answers to: the `kind: verb` nodes sitting beside its README.

    An EMPTY SET satisfies every claim made about it, so a filter that matches no node
    leaves the half of the projection that asks "does the noun's api expose each
    declared verb?" silently asserting nothing.
    """
    directory = nounspace.joinpath(*chain)
    if not directory.is_dir():
        return set()
    return {
        node.stem
        for node in sorted(directory.glob("*.md"))
        if node.name != "README.md" and kind_of(node, nounspace) == "verb"
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
    return bool(declared_kinds(root / DEFAULT_TERMS))


FLAG_DIR = Path("docs") / "lexicon" / "param"

NOUN_DIR = Path("docs") / "lexicon"

CANON_ENV = "RACECAR_ROOT"

#: The installed racecar skill: `skills/racecar` in `$CLAUDE_CONFIG_DIR`, else `~/.claude`.
_CLAUDE_HOME = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
SKILL_LINK = Path(_CLAUDE_HOME) / "skills" / "racecar"

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".collections",
}

NOUN_TREE = Path("docs") / "lexicon"

FLAG_TREE = Path("docs") / "lexicon" / "param"

# ONE tree. `FLAG_TREE` is a sub-path of `NOUN_TREE`, so listing both would read every
# param node twice -- and, worse, read it the second time WITHOUT the `--` prefix below.
TERM_TREES = (NOUN_TREE,)

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


def noun_count(terms: Path) -> int:
    """How many nouns this lexicon declares.

    Counted over the whole tree rather than through `nodes()`, which excludes READMEs --
    and a noun's node IS its README, so routing this through `nodes()` would count no
    nouns.
    """
    if not terms.is_dir():
        return 0
    return sum(1 for _, meta in pages(terms) if meta.get("kind") == "noun")


def partition_field(terms: Path) -> str | None:
    """The field this lexicon partitions on, or None when it declares none.

    Opt-in per corpus, exactly as the graph engine treats it. An adopter's lexicon that
    declares no `partition:` has no domains and owes none -- forcing `domain:` onto every
    node of a single-domain tree would be a field with one value everywhere, which says
    nothing.
    """
    declared = _frontmatter.load(ontology_path(terms))
    value = declared.get("partition")
    return str(value) if value else None


def domains_of(node: Path) -> list[str]:
    """The domains a node declares. Absent is NOT "every domain" -- it is a finding here."""
    raw = _frontmatter.load(node).get("domain")
    if isinstance(raw, str):
        return [raw.strip()]
    return [str(d).strip() for d in raw] if isinstance(raw, list) else []


def declared_domains(terms: Path) -> list[str]:
    """Every domain any node claims, which is the set `--domain` is validated against."""
    seen: set[str] = set()
    for node, _ in pages(terms):
        seen.update(domains_of(node))
    return sorted(seen)


def _sections(node: Path) -> set[str]:
    """The `## <name>` headings a node carries, lowercased."""
    body = _frontmatter.split(node.read_text(encoding="utf-8"))[1]
    return {m.group(1).strip().lower() for m in re.finditer(r"^##\s+(.+)$", body, re.M)}


def _has_prose(node: Path) -> bool:
    """Whether a node says anything beyond its own headings.

    The test for a stub, and it is deliberately about CONTENT rather than a marker. A
    `bearing: draft` marker is also carried by hand-authored words whose author marked
    them draft on purpose, and a stub marked the same way hides among them.

    Emptiness cannot be gamed the way a field can. A node with a heading, a per-domain
    section header and nothing under either has not been written, whoever set its bearing.
    """
    body = _frontmatter.split(node.read_text(encoding="utf-8"))[1]
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return True
    return False


def _is_command(node: Path, terms: Path) -> bool:
    """A verb node is a COMMAND when it sits under a noun; under a kind bucket it is a meaning.

    `graph/check.md` is `racecar.graph check`. `verb/check.md` is what the word means where it
    cuts across nouns, and addresses nothing. The test is the neighbour, not the filename: a
    noun directory carries a `README.md` declaring `kind: noun`.
    """
    parent = node.parent / "README.md"
    if node.parent == terms:
        return True
    return parent.exists() and kind_of(parent, terms) == "noun"


def _params_of(node: Path) -> list[str]:
    raw = _frontmatter.load(node).get("params")
    return [str(p) for p in raw] if isinstance(raw, list) else []


def _declared_name(terms: Path) -> str | None:
    """The `name:` a corpus's root node declares, or None when it declares none.

    One read, two callers. `root_noun` and `corpus_domain` both want this string and want
    different answers when it is absent, so the read is here and each states its own
    fallback.
    """
    declared = _frontmatter.load(terms / "README.md").get("name")
    return str(declared).strip('"') if declared else None


def root_noun(terms: Path) -> str:
    """What the root package is called, read from the node that declares it.

    The empty chain is the root, and it has no directory segment to be named by.

    The node's own `name:` is the answer, not the package directory: it is the declaration,
    and it is what every other noun in this graph is named by.

    Shares its reader with `corpus_domain` and differs only in what it falls back to. Both
    ask the root node for one string; a noun with no declaration is named by its directory,
    and a projection with no declaration is `DEFAULT_DOMAIN`. Two fallbacks, one read.
    """
    return _declared_name(terms) or terms.name


def corpus_domain(terms: Path) -> str:
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
    return _declared_name(terms) or DEFAULT_DOMAIN


def verb_node(terms: Path, noun: str, verb: str | None) -> Path:
    """Where one tuple's node lives. A dotted noun is the directories it nests in.

    The inverse of the chain `tuples()` walks, written here once so the two cannot part
    company. The root noun is the empty chain -- its verbs sit directly under the
    lexicon, with no directory of their own -- which is the same asymmetry `root_noun`
    exists to absorb.

    A tuple with no verb is the noun itself, and its node is the noun's README. Formatting
    `None` into a filename would give `nav/None.md`.
    """
    chain = () if noun == root_noun(terms) else tuple(noun.split("."))
    leaf = "README.md" if verb is None else f"{verb}.md"
    return terms.joinpath(*chain, leaf)


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


def describe(terms: Path, noun: str, verb: str | None = None) -> dict[str, Any]:
    """What the lexicon declares for one noun, or one of its verbs, as data.

    `{"noun": noun, "summary": ..., "verbs": {verb: {"summary": ..., "params":
    [{"name", "type", "summary", "required", "defined", "position"}, ...]}}}`, every verb
    when `verb` is None. A param with
    no node of its own, or a node that declares no `type`, comes back with type `None`;
    what a reader does with that is the reader's choice. Raises `LexiconError` when the
    noun, or the named verb, is not declared.
    """
    readme = verb_node(terms, noun, None)
    if not readme.is_file():
        raise LexiconError(f"{noun}: not declared ({readme} does not exist)")
    chain = () if noun == root_noun(terms) else tuple(noun.split("."))
    wanted = sorted(declared_verbs(terms, chain)) if verb is None else [verb]
    verbs: dict[str, Any] = {}
    for name in wanted:
        node = verb_node(terms, noun, name)
        if not node.is_file():
            raise LexiconError(f"{noun} {name}: not declared ({node} does not exist)")
        params = []
        for param in _params_of(node):
            meta = _frontmatter.load(terms / "param" / f"{param}.md")
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
