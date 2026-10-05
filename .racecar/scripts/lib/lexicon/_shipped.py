"""The `shipped` rule: a word this repo's CLI ships, on a node that disowns its domain.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. Its own
module because it is the one rule whose subject is a NODE rather than a tuple, and because
`_checks.py` is at its line ceiling — a rule that sweeps the corpus reads differently from
the per-tuple checks beside it.

Complexity: O(P + N), P = nodes swept once, N = nouns in the one cached CLI audit
"""

from __future__ import annotations

from lib.lexicon._graph import Answer, Finding, Graph, undeclared
from lib.lexicon._nodes import (
    DEFAULT_DOMAIN,
    corpus_domain,
    domains_of,
    kind_of,
    pages,
)
from lib.shared import _frontmatter
from lib.shared._root import package_dir


def shipped_words(g: Graph) -> dict[str, frozenset[str]]:
    """Every word this repo's CLI ships, as `{dotted noun: the verbs under it}` plus the nouns.

    Read from the CLI audit rather than from `addressable()`. `addressable()` answers "is this
    a directory holding a `__main__.py`", which is true of a noun and false of every verb: the
    two supported shapes make a verb an argparse subcommand or a leaf module, and neither is a
    directory. So against it the chain term `(*chain, name)` is unmatchable for every
    verb, and only the bare-name term fires -- matching on spelling alone against an
    unrelated package that shares it.
    """
    # Both sides are made PACKAGE-RELATIVE before they meet. `g.cli` keys a noun by its full
    # dotted module path (`racecar.lexicon`), `g.addressable` by its chain under the package
    # (`('lexicon',)`), and a node's chain is the second of those. Merging them as they come
    # puts every verb under a key no node can ever look up, so the verb half would
    # silently never match -- the same class of quiet miss this whole check is about.
    pkg = package_dir(g.root)
    prefix = f"{pkg.name}." if pkg else ""
    out: dict[str, frozenset[str]] = {}
    for noun, verbs in g.cli.items():
        relative = noun[len(prefix) :] if prefix and noun.startswith(prefix) else noun
        out[relative] = frozenset(verbs)
    for chain in g.addressable:
        if chain:
            out.setdefault(".".join(chain), frozenset())
    return out


def shipped_findings(g: Graph) -> list[Answer]:
    """Does any node disown this repo's domain while this repo's CLI ships its word?

    Borrowing a word INTO racecar's surface makes racecar one of its fixers, whatever its
    provenance.

    **A sweep of the corpus, not a per-tuple check.** A tuple is a command, and a
    command's nodes declare this repo's own domain by construction, so a per-tuple guard
    fires on every node it is shown. The borrowed words are precisely the ones NO tuple
    reaches: they sit in the kind buckets (`param/`, `rule/`, `verb/`).
    """
    if not g.partitioned or DEFAULT_DOMAIN not in (g.selected or (DEFAULT_DOMAIN,)):
        return []
    # THE WORDS TO COMPARE AGAINST ARE RACECAR'S, NOT THIS REPO'S.
    #
    # The rule is "borrowing a word INTO racecar's surface makes racecar one of its fixers".
    # `shipped_words` reads `g.cli`, which is whatever repo is being graded. In racecar those
    # two sets are the same set. In an adopter they are different: `acme` naming its
    # own verb `bar`, in its own domain, with no `racecar bar` anywhere, would be told
    # racecar must be a fixer of it -- one finding per node, for every command it
    # declares and every noun, none of them a borrowed word, and no way to clear any of
    # them because the claim they ask for is false.
    #
    # An adopter cannot know racecar's vocabulary: racecar delivers its checkers but not its
    # lexicon, so there is nothing to read. The honest answer is then no findings rather than
    # a confident wrong one -- the same call `_cli_gap` makes for the root noun. Where the
    # corpus IS racecar's, the two sets coincide.
    if corpus_domain(g.terms) != DEFAULT_DOMAIN:
        return []
    shipped = shipped_words(g)
    out: list[Answer] = []
    for node, _ in pages(g.terms):
        mine = domains_of(node)
        if not mine or DEFAULT_DOMAIN in mine:
            continue
        name = str(_frontmatter.load(node).get("name") or node.stem).strip('"')
        chain = node.relative_to(g.terms).parent.parts
        dotted = ".".join(chain)
        # A node under a noun is graded against THAT noun's verbs; a node with no chain is the
        # top-level borrowing the bare-name term was written for. Matching a nested node
        # on its bare name would report an adopter's every noun for a word its CLI ships
        # elsewhere. Three ways the CLI can ship this word, and the first is the chain
        # term: a word addressed as its own node.
        hit = ".".join((*chain, name)) in shipped
        # A verb: the word is a subcommand of the noun its node sits under.
        hit = hit or (bool(chain) and name in shipped.get(dotted, frozenset()))
        # A noun's own README, named for the directory it sits in.
        hit = hit or (bool(chain) and name == chain[-1] and dotted in shipped)
        # A node with NO chain is the top-level borrowing the bare-name term was written
        # for. Applying that term to a nested node would report an adopter's every noun
        # against a word its CLI ships somewhere else entirely.
        hit = hit or (not chain and name in shipped)
        # A VERB-bucket node fixes what a word means where it cuts across nouns, and racecar
        # ships that word as a verb of some noun. `param/host.md` is not the same case and
        # must not match: it fixes the flag `--host`, which is a different thing wearing a
        # noun's spelling.
        hit = hit or (
            kind_of(node, g.terms) == "verb"
            and any(name in verbs for verbs in shipped.values())
        )
        if not hit:
            continue
        out.append(
            Answer(
                "",
                undeclared(DEFAULT_DOMAIN, dotted or name, name, g.terms),
                (),
                (
                    Finding(
                        str(node),
                        f"`domain: {mine}` omits `{DEFAULT_DOMAIN}`, but the CLI ships "
                        f"`{name}`. Shipping a borrowed word makes racecar one of its fixers.",
                        "",
                    ),
                ),
            )
        )
    return out
