"""What a command acts on: the domains it selects and the nouns eligible in them.

Part of `lib.lexicon`. A command builds each of these lists once, where its arguments are
parsed, and hands them on; nothing downstream rebuilds them.
"""

from __future__ import annotations

from pathlib import Path

from lib.lexicon._nodes import (
    DELIVERED_RELS,
    corpus_domain,
    declared_domains,
    declared_nouns,
    delivered_corpus,
    domains_of,
)
from lib.shared import _frontmatter


def in_selection(declared: list[str], selected: list[str], domain: str) -> bool:
    """Whether a node declaring `declared` domains is in this run's selection as `domain`.

    A node declaring NO domain stays in whatever was selected: you cannot filter by a domain
    a node does not have, and "declares no domain" is exactly what has to be reported.
    """
    return not (declared and selected and domain not in selected)


def reserved_nouns(terms: Path) -> frozenset[str]:
    """The nouns the delivered lexicon reserves: `kind: noun` with `status: reserved`.

    A reserved noun is not eligible: no repo may declare it, and the tuple list leaves it
    out. It binds a repo that RECEIVES the delivered lexicon (`.racecar/docs/lexicon/`), not
    racecar, which authors it (`docs/rc_lexicon/`) and holds the word's owner.
    """
    delivered = delivered_corpus(terms)
    if delivered is None or delivered.parts[-len(DELIVERED_RELS[1].parts) :] != (
        DELIVERED_RELS[1].parts
    ):
        return frozenset()
    return frozenset(
        str(meta.get("name")).strip('"')
        for readme in delivered.glob("*/README.md")
        if (meta := _frontmatter.load(readme)).get("kind") == "noun"
        and meta.get("status") == "reserved"
    )


def eligible_nouns(nounspace: Path, selected: list[str]) -> dict[tuple[str, ...], Path]:
    """The nouns a run acts on: `declared_nouns` in the `selected` domains, less the reserved.

    `selected` is REQUIRED, so the rule "a pass grades one projection" is not re-typed
    at each reader, where one reader that forgot to filter would grade the ansible
    projection and report racecar's nodes. A caller that must supply the projection
    cannot forget it; `eligible_domains` is where a run's projection comes from.

    A noun declaring NO domain is in every selection, by `in_selection`'s rule: you cannot
    filter by a domain a node does not have, and "declares no domain" has to be reported.
    """
    reserved = reserved_nouns(nounspace)
    found: dict[tuple[str, ...], Path] = {}
    for chain, node in declared_nouns(nounspace).items():
        if chain and chain[0] in reserved:
            continue
        declared = domains_of(node)
        if any(in_selection(declared, selected, domain) for domain in declared or [""]):
            found[chain] = node
    return found


def eligible_domains(
    terms: Path, requested: list[str] | None = None, *, every: bool = False
) -> list[str]:
    """The domains a run acts on, built once: every declared domain under `every`, else the
    ones `requested`, else the corpus's own.

    A requested domain the lexicon declares nothing under is not an error: it holds nothing,
    so every verb answers with nothing, which is the true answer. The default is the corpus's
    own domain, read from its root node, never the literal `racecar`, which is this repo's
    answer and nobody else's.
    """
    if every:
        return declared_domains(terms)
    if requested is not None:
        return list(requested)
    return [corpus_domain(terms)]
