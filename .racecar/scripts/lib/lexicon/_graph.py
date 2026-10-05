"""THE LIST: `(domain, noun, verb, node)`, and everything a run reads once.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A
caller imports what it needs: the tests, the `lexicon` noun's api and the delivered CLI
all reach the same functions instead of loading a script.

Complexity: O(P + A), P = nodes walked once into the list, A = the one CLI audit
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from lib.lexicon import _audit
from lib.lexicon._audit import (
    Node,
)
from lib.lexicon._eligible import eligible_nouns, in_selection
from lib.lexicon._nodes import (
    DEFAULT_DOMAIN,
    _is_command,
    _params_of,
    declared_domains,
    declared_kinds,
    domains_of,
    kind_of,
    ontology_path,
    pages,
    partition_field,
    root_noun,
    verb_node,
)
from lib.shared import _frontmatter
from lib.shared._root import package_dir, packages


def listing(terms: Path, selected: list[str]) -> list[dict[str, Any]]:
    """THE list, as records: `[{domain, noun, verb, node, params}, ...]`.

    One rendering of `tuples()`, and the only one. The tuple is
    `(domain, noun, verb, node)`; `params` is an attribute rendered beside it.

    Built from `tuples()`, not from `status_rows()`. `status_rows` unions what the lexicon
    DECLARES with what the tree IMPLEMENTS, which is right for a coverage table and wrong for
    this: a verb the tree grew and nobody declared is missing from canon, and listing it here
    would be the tool telling itself the verb exists. It is reported by `check` instead, and
    stays out of the list until a person puts it in.
    """
    return [
        {
            "domain": row.domain,
            "noun": row.noun,
            "verb": row.verb,
            "node": str(row.node),
            "params": list(attrs.params),
        }
        for row, attrs in tuples(terms, selected).items()
    ]


# ---------------------------------------------------------------------------------------------
# Grading: the list of tuples, one loop, n methods.
# ---------------------------------------------------------------------------------------------
class Row(NamedTuple):
    """THE tuple: `(domain, noun, verb, node)`. Unique across the first three.

    `node` is where the declaration lives, one per key, so carrying it costs nothing and means
    a method never goes looking. That is what makes every other node in the lexicon irrelevant
    to a check: `key/pnode.md` fixes a frontmatter key, `party/adopter.md` fixes a word, and
    `param/force.md` fixes a spelling for adopters to use. None of them is a command, and
    grading them as though they were would be telling the canon off for being a reference.

    `params` is NOT in here, and that is the rule rather than a preference. It is an ATTRIBUTE
    of this key — two verbs of one noun in one domain cannot exist, while the same verb under
    two nouns is two tuples, and no part of that depends on which flags a verb takes. Putting
    params in the key would make adding a flag a different tuple.

    **A noun with no verb of its own is `(domain, noun, None)`**, and its `node` is the noun's
    README. `python -m acme.nav` is a command whether or not `nav` has verbs, so a list that
    cannot hold it is missing one. Every place that reads the list AS VERBS skips these
    rows; every place that reads it as the set of declared nouns keeps them, and that is what
    they are for.
    """

    domain: str
    noun: str
    verb: str | None
    node: Path


def row_order(row: Row) -> tuple[str, str, str, str]:
    """The order the list is kept in: a noun's own row first, then its verbs.

    `sorted()` on bare rows compares `None` with a verb string under the same noun and raises
    `TypeError`, so every sort of rows goes through this rather than through tuple order.
    """
    return (row.domain, row.noun, row.verb or "", str(row.node))


class Attrs(NamedTuple):
    """What hangs off one tuple. Never part of it.

    `reaches` is what the node points at — the noun's README, the verb's meaning node where
    the word cuts across, and a node per param. Carried so a method starts from the tuple and
    never walks: a method that begins by walking the corpus is answering a question this list
    already answers.
    """

    params: tuple[str, ...]
    reaches: tuple[Path, ...]


class Graph(NamedTuple):
    """The list, and everything a run reads about the tree it is checked against — read ONCE.

    A method reads fields here; it does not walk anything.

    `cli` and `api` are the expensive reads — the CLI audit shells the whole command tree —
    so asking per row would multiply the gate's cost by the size of the list for an answer
    that cannot change during a run.
    """

    root: Path
    terms: Path
    selected: tuple[str, ...]
    pkg: Path | None
    kinds: dict[str, Any]
    base: tuple[str, ...]
    cli: dict[str, set[str]]
    api: dict[str, frozenset[str]]
    addressable: frozenset[tuple[str, ...]]
    canon: Path | None
    partitioned: bool
    rows: tuple[Row, ...]
    attrs: dict[Row, Attrs]
    verb_users: dict[str, frozenset[str]]
    param_users: dict[str, frozenset[str]]
    flag_types: dict[str, frozenset[str]]
    flag_canon: dict[str, Node]
    flag_local: dict[str, Node]
    verb_args: dict[tuple[str, str], tuple[dict[str, Any], ...]]


class Finding(NamedTuple):
    """One gap, as a record. Internal to a method; what a method RETURNS is an `Answer`."""

    where: str
    what: str
    method: str

    def __str__(self) -> str:
        return f"{self.where}: {self.what}"


class Answer(NamedTuple):
    """What one check says about one tuple: `(check, tuple, implemented, missing)`.

    One flat list of these is every answer from every check, so a caller filters rather than
    walking a structure — by check, by whether anything is missing, by noun.

    Every check answers in this shape, whichever direction it ran, which is what makes the
    answers countable and comparable instead of a pile of sentences.

    - `implemented` — evidence the surface holds up its end for this tuple.
    - `missing` — what it does not. Empty means the check passed.

    **When `missing` is non-empty on a REVERSE answer, `row` is a tuple the lexicon does not
    have.** It was synthesised from the surface — a command the CLI offers, a flag the code
    accepts — and it is exactly the argument `lexicon create --tuple` takes. The check does not
    just report the gap; it hands back the thing that closes it.

    A FORWARD answer's `row` always comes from the lexicon, so its `missing` means the surface
    is behind the declaration rather than the other way round.
    """

    check: str
    row: Row
    implemented: tuple[str, ...]
    missing: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        """Whether this check found nothing wrong about this tuple."""
        return not self.missing


def undeclared(domain: str, noun: str, verb: str | None, terms: Path) -> Row:
    """The tuple the lexicon WOULD have for a command the surface offers and it does not name.

    Its `node` is where that node would go, so the row is complete and feedable rather than a
    description of one. This is the value a reverse half returns and `create --tuple` takes.
    """
    return Row(domain, noun, verb, verb_node(terms, noun, verb))


class Word(NamedTuple):
    """One NODE of the lexicon, whatever kind it is. Not a tuple, and deliberately not.

    A `Row` is a command: `(domain, noun, verb, node)`, and only a verb node sitting under a
    noun ever becomes one. That leaves most of the corpus unreachable -- the nouns, the
    params, and the verb nodes under a kind bucket, which say what a word means where it cuts
    across nouns and address no command at all.

    So the field set is what every node has, plus one field for what only its own kind has:

    - `noun` is None under a kind bucket, because a bucket is not a noun, and a dotted chain
      where a noun nests (`graph.ontology`). A node in the corpus root belongs to the root
      noun, which its own node names.
    - `fields` carries the keys this kind's `required:` names, read off the node. A verb's
      `params`, a param's `type`, and nothing at all for the kinds that require nothing --
      the ontology says which, so a new kind needs no code here.
    """

    domain: str
    kind: str
    name: str
    noun: str | None
    node: Path
    fields: dict[str, Any]


def _noun_chain(node: Path, terms: Path) -> str | None:
    """The dotted noun a node hangs under, or None when no noun does.

    Every directory between the node and the corpus root must declare `kind: noun`. One that
    does not -- `param/`, an `index` -- means the node sits in a kind bucket, and a bucket
    addresses nothing. This is `_is_command`'s test applied to the whole chain rather than to
    the one directory above, because `graph/ontology/check.md` is two nouns deep and a
    one-level test cannot tell that from a bucket inside a noun.

    **A node sitting directly in the corpus root belongs to the ROOT noun**, which is named by
    its node rather than by a directory -- the same answer `tuples()` gives, and for the same
    reason. Returning None there instead would have made `racecar check` a command with a noun
    in one listing and no noun in the other, which is two routes disagreeing about one node.
    So None means one thing only: this node is in a kind bucket.
    """
    parts: list[str] = []
    directory = node.parent
    while directory != terms:
        readme = directory / "README.md"
        if not readme.is_file() or kind_of(readme, terms) != "noun":
            return None
        parts.append(directory.name)
        directory = directory.parent
    return ".".join(reversed(parts)) if parts else root_noun(terms)


def words(terms: Path, selected: list[str], kind: list[str]) -> list[dict[str, Any]]:
    """Every node of the named kinds, as records. The corpus by kind, not by command.

    READMEs are IN: a noun's node IS its README. `tuples()` carries each noun too, as a row
    with no verb, but only the nouns; this answers for every kind the ontology declares.

    `kind` empty means every kind, and is a LIST because the flag is repeatable -- named for
    the flag, the way `args.kind` is. Validation of what a caller may name belongs to the
    caller: the CLI checks `--kind` against the ontology's `kinds:` and refuses an unknown one
    by name, the same way it refuses an unknown `--domain`.
    """
    wanted = set(kind)
    required = declared_kinds(terms)
    found: list[Word] = []
    if not terms.is_dir():
        return []
    for node, _ in pages(terms):
        declares = kind_of(node, terms)
        if not declares or (wanted and declares not in wanted):
            continue
        meta = _frontmatter.load(node)
        spec = required.get(declares) or {}
        keys = spec.get("required") or [] if isinstance(spec, dict) else []
        declared = domains_of(node)
        for domain in declared or [DEFAULT_DOMAIN]:
            # Same rule the tuple walk states, and the same fallback: a node declaring NO
            # domain stays whatever was selected, because you cannot filter by a domain a
            # node does not have and the missing declaration is the thing to report. What an
            # absent declaration should default to is a separate question from what an
            # absent `--kind` should; this answers neither differently from `tuples()`.
            if not in_selection(declared, selected, domain):
                continue
            found.append(
                Word(
                    domain=domain,
                    kind=declares,
                    name=str(meta.get("name") or node.stem).strip('"'),
                    noun=_noun_chain(node, terms),
                    node=node,
                    fields={k: meta[k] for k in keys if k in meta},
                )
            )
    return [
        {
            "domain": w.domain,
            "kind": w.kind,
            "name": w.name,
            "noun": w.noun,
            "node": str(w.node),
            "fields": w.fields,
        }
        for w in sorted(found, key=lambda w: (w.domain, w.kind, w.name, str(w.node)))
    ]


def tuples(terms: Path, selected: list[str]) -> dict[Row, Attrs]:
    """THE list: every `(domain, noun, verb)` the graph declares, and what hangs off each.

    One walk of the corpus, and the only one. Every caller that wants the tuples reads
    this, so no two of them can disagree.
    """
    found: dict[Row, Attrs] = {}
    if not terms.is_dir():
        return found
    root = root_noun(terms)
    # The list starts from the eligible nouns. Every domain is asked for here, because
    # domains are applied per row below; what this leaves out is a reserved noun, and so
    # every verb under it.
    eligible = eligible_nouns(terms, declared_domains(terms))
    for node, _ in pages(terms):
        if kind_of(node, terms) != "verb" or node.name == "README.md":
            continue
        if not _is_command(node, terms):
            continue
        chain = node.relative_to(terms).parent.parts
        if chain not in eligible:
            continue
        noun = ".".join(chain) if chain else root
        verb = str(_frontmatter.load(node).get("name") or node.stem).strip('"')
        params = tuple(_params_of(node))
        reaches = tuple(
            p
            for p in (
                node.parent / "README.md",
                terms / "verb" / f"{verb}.md",
                *(terms / "param" / f"{flag}.md" for flag in params),
            )
            if p.exists() and p != node
        )
        declared = domains_of(node)
        for domain in declared or [DEFAULT_DOMAIN]:
            # A node declaring NO domain stays in the list whatever was selected. You cannot
            # filter by a domain a node does not have, and "declares no domain" is exactly
            # what has to be reported -- filtering it out would hide the finding for
            # every projection but the default one.
            if not in_selection(declared, selected, domain):
                continue
            found[Row(domain, noun, verb, node)] = Attrs(params, reaches)
    # Every noun, as its own row with no verb. Placed by `_noun_chain`, the rule `words()`
    # uses, so a README declaring `kind: noun` inside a kind bucket is not a command noun here
    # either.
    for node in eligible.values():
        noun_name = _noun_chain(node, terms)
        if noun_name is None:
            continue
        declared = domains_of(node)
        for domain in declared or [DEFAULT_DOMAIN]:
            if not in_selection(declared, selected, domain):
                continue
            found[Row(domain, noun_name, None, node)] = Attrs((), ())
    return dict(sorted(found.items(), key=lambda item: row_order(item[0])))


def addressable(root: Path) -> frozenset[tuple[str, ...]]:
    """Every chain in the repo's packages that a `python -m` invocation reaches, read once.

    A directory with a `__main__.py` is addressable; anything else is not. Precomputed rather
    than asked per row, so a method answering "does the CLI ship this word" is a membership
    test and not a second walk of the tree.
    """
    found: set[tuple[str, ...]] = set()
    for pkg in packages(root):
        for entry in pkg.rglob("__main__.py"):
            found.add(entry.parent.relative_to(pkg).parts)
    return frozenset(found)


def api_surface(root: Path) -> dict[str, frozenset[str]]:
    """`{dotted noun: the names its api exposes}` for every vertical under `src/`, read once.

    The other half of what a row is graded against. Precomputed for the reason `cli` is:
    asking per row would re-parse the same api modules once per verb, for an answer that
    cannot change during a run.
    """
    pkg = package_dir(root)
    if pkg is None:
        return {}
    out: dict[str, frozenset[str]] = {}
    for init in sorted(pkg.rglob("__init__.py")):
        module = init.parent
        chain = module.relative_to(pkg).parts
        if chain:
            out[".".join(chain)] = frozenset(_audit.api_functions(module))
    return out


def graph(
    root: Path, terms: Path, selected: list[str], canon: Path | None = None
) -> Graph:
    """Read the list and the tree once, into the value every method is graded against."""
    listed = tuples(terms, selected)
    # Both counts come FROM the list. A word cuts across when more than one tuple uses it,
    # which is a fact about the list.
    verb_users: dict[str, set[str]] = {}
    param_users: dict[str, set[str]] = {}
    for row, attrs in listed.items():
        if row.verb is None:
            continue
        verb_users.setdefault(row.verb, set()).add(row.noun)
        for flag in attrs.params:
            param_users.setdefault(flag, set()).add(f"{row.noun} {row.verb}")
    # Every spelling the code declares, from both routes, merged once. `collision` asks
    # whether one spelling carries two meanings and `flag-type` asks whether a node agrees
    # with the code.
    types: dict[str, set[str]] = {}
    if _audit.has_cli(root):
        for flag, kinds in _audit.declared_flag_types(root).items():
            types.setdefault(flag, set()).update(kinds)
    for flag, kinds in _audit.script_flag_types(root).items():
        types.setdefault(flag, set()).update(kinds)
    # Keyed by the node's FILE STEM, not by its declared `name`. A param references a node by
    # spelling, and the stem is that spelling; the declared `name` is a claim ABOUT it, and one
    # of the things graded is whether that claim carries stray dashes. Keyed by the
    # claim, a node whose name is wrong could not be found by the tuple that names it,
    # so the check that catches it would never run.
    canonical: dict[str, Node] = {}
    local: dict[str, Node] = {}
    for flag_node in _audit.flag_nodes(root, canon):
        stem = Path(flag_node.where.split(" ")[0]).stem
        (canonical if flag_node.canon else local)[stem] = flag_node
    return Graph(
        root=root,
        terms=terms,
        selected=tuple(selected),
        pkg=package_dir(root),
        kinds=declared_kinds(terms),
        base=tuple(
            (_frontmatter.load(ontology_path(terms)).get("base") or {}).get("required")
            or []
        ),
        cli=_audit.cli_verbs(root) if _audit.has_cli(root) else {},
        api=api_surface(root),
        addressable=addressable(root),
        canon=canon,
        partitioned=partition_field(terms) is not None,
        rows=tuple(listed),
        attrs=listed,
        verb_users={word: frozenset(who) for word, who in verb_users.items()},
        param_users={word: frozenset(who) for word, who in param_users.items()},
        flag_types={flag: frozenset(kinds) for flag, kinds in types.items()},
        flag_canon=canonical,
        flag_local=local,
        verb_args=_audit.cli_args(root) if _audit.has_cli(root) else {},
    )


def word_node(g: Graph, bucket: str, word: str) -> str | None:
    """Where the node fixing `word` in `bucket` (`verb` or `param`) is, or None.

    The one test of whether a word is fixed, for the check that reports a word with no node
    and for `--apply`, which writes the frame for one. A param's node may be in any corpus
    the lexicon joins, the delivered one included; the graph holds every one it found.
    """
    node = g.terms / bucket / f"{word}.md"
    if node.exists():
        return str(node)
    known = (
        (g.flag_canon.get(word) or g.flag_local.get(word))
        if bucket == "param"
        else None
    )
    return None if known is None else known.where


def answer(row: Row, implemented: list[str], found: list[Finding]) -> list[Answer]:
    """Fold a forward method's working into the one shape every check answers in.

    The `check` field is left blank here and stamped by `grade`, which knows which method it
    called. A method naming itself would be a second home for its own name, and the copy that
    drifts is always the one not doing the dispatching.

    A list, not a bare `Answer`, so forward and reverse have the same return type and `grade`
    does not branch on which half it called.
    """
    return [Answer("", row, tuple(implemented), tuple(found))]


def footprint(row: Row, g: Graph) -> tuple[Path, ...]:
    """The node this tuple declares itself on, and every node that node points at."""
    return (row.node, *g.attrs[row].reaches)
