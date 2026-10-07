"""The coverage table: what the lexicon declares beside what each route offers.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A
caller imports what it needs: the tests, the `lexicon` noun's api and the delivered CLI
all reach the same functions instead of loading a script.

Complexity: O(N*V), N = declared nouns, V = verbs each, over precomputed surfaces
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from lib.lexicon import _audit
from lib.lexicon._corpora import Lexicon
from lib.lexicon._eligible import eligible_nouns
from lib.lexicon._graph import Graph
from lib.lexicon._loop import Checked, matrix
from lib.lexicon._nodes import (
    DEFAULT_DOMAIN,
    _params_of,
    corpus_domain,
    declared_verbs,
    domains_of,
    root_noun,
    verb_node,
)
from lib.shared._as_json import FORM_PARAMS
from lib.shared._root import package_dir


def site_noun(chain: tuple[str, ...], pkg: Path | None, noun: str) -> str:
    """The noun as `_audit.flag_sites` spells it in a site: `api`, never `racecar.api`.

    `flag_sites` strips the package prefix and `cli_verbs` keeps it, so every reader holding
    both has to say which key space it is in. `racecar.api check` matched against sites
    reading `api check` finds nothing, and every command backed by the package would
    list no implemented params at all. One home for the strip, so the two cannot
    disagree. The root's own verbs are sited under the package's name (`racecar check`),
    which is its node's `name` in racecar and need not be in an adopter.
    """
    if chain:
        return ".".join(chain)
    return pkg.name if pkg else noun


def long_flags_at(sites_by_flag: dict[str, set[str]], site: str, verb: str) -> set[str]:
    """The LONG flags `flag_sites` records at `site verb`, spelled without their dashes.

    Long only: a short flag is a terse spelling of a word a node already fixes, so counting
    `-v` beside `--verbose` reports a gap that is one flag written twice.
    """
    return {
        flag[2:]
        for flag, sites in sites_by_flag.items()
        if flag.startswith("--") and f"{site} {verb}" in sites
    }


def status_rows(
    lexicon: Lexicon, root: Path, selected: list[str]
) -> list[dict[str, Any]]:
    """Every `(domain, noun, verb, params)` row, each carrying whether it is DECLARED and
    whether it is IMPLEMENTED.

    One source for the table, `list --json` and `check --json`, because three mechanisms
    answering one question is how they come to disagree.

    Rows are the UNION of both sides, never the declaration alone. A view built from the
    lexicon outwards can only ever report nodes with no code; the drift that is easier to
    acquire is code with no node, and it is invisible from that direction.
    """
    pkg = package_dir(root)
    # No `except LexiconError` here: an audit that could not read the tree is a refusal
    # (`_audit.cli_tree`), and turning it into `{}` would report every verb unimplemented --
    # or, where the lexicon is empty too, nothing at all -- from a tree nobody read.
    offered = _audit.cli_verbs(root) if _audit.has_cli(root) else {}
    declared_flags = _audit.flag_sites(root) if _audit.has_cli(root) else {}
    wanted = set(selected)

    rows_out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for chain, node in sorted(eligible_nouns(lexicon, selected).items()):
        # The gather has already dropped anything outside `selected`, so this
        # intersection is never empty -- it picks WHICH of the node's domains
        # labels the row.
        doms = domains_of(node) or [DEFAULT_DOMAIN]
        # The empty chain is the root package. Its row is named for the package, which
        # is what its node declares.
        noun = ".".join(chain) or root_noun(lexicon)
        dotted = ".".join((pkg.name, *chain)) if pkg else noun
        # BOTH routes, unioned. The projection accepts either `src/<pkg>/<noun>/` or a
        # delivered `scripts/<noun>.py`, and the CLI audit only ever sees the first, so a
        # script-backed noun has to be asked for separately. `len(chain) == 1` because
        # `scripts/` is flat: a sub-noun cannot be script-backed.
        #
        # KNOWN LIMIT: a union, not a resolution. A noun with BOTH a
        # module and a same-named script has the two surfaces merged silently, and a
        # disagreement between them is invisible here. `lexicon` is one:
        # `scripts/lexicon.py` is the delivered implementation and
        # `src/racecar/lexicon/` wraps it so the tuple list has an api. Both offer
        # check/create/list and they agree — but nothing here would notice if they
        # stopped.
        from_script = _audit.script_surface(root, noun) if len(chain) == 1 else {}
        implemented = offered.get(dotted, set()) | set(from_script)
        for verb in sorted(declared_verbs(lexicon, chain) | implemented):
            seen.add((noun, verb))
            # `verb_node` rather than a local join: one home for the path, and the
            # root-noun case comes with it.
            node_for = verb_node(lexicon, noun, verb)
            declared_params = set(_params_of(node_for)) if node_for.exists() else set()
            live_params = long_flags_at(
                declared_flags, site_noun(chain, pkg, noun), verb
            ) | from_script.get(verb, set())
            # The row's domain is the VERB's, not the noun's. A noun may be borrowed and
            # shipped -- `host` is `[ansible, racecar]` -- while the verb racecar put on it
            # is racecar's alone. Labelling from the noun's node would report every
            # verb of `host` as `ansible`, disagreeing with `tuples()`, which reads the
            # verb node.
            verb_doms = domains_of(node_for) if node_for.exists() else []
            label = sorted(set(verb_doms or doms) & wanted) or sorted(
                set(doms) & wanted
            )
            rows_out.append(
                {
                    "domain": label[0],
                    "noun": noun,
                    "verb": verb,
                    "params": sorted(declared_params | live_params),
                    "in_graph": node_for.exists(),
                    "implemented": verb in implemented,
                    "params_in_graph": sorted(declared_params),
                    "params_implemented": sorted(live_params),
                }
            )

    # Implemented nouns the lexicon never declared. Absent these, a noun added to the code
    # and never written down is simply not in the report at all.
    for dotted, verbs_here in sorted(offered.items()):
        if not pkg or not dotted.startswith(f"{pkg.name}."):
            continue
        noun = dotted[len(pkg.name) + 1 :]
        for verb in sorted(verbs_here):
            if (noun, verb) in seen:
                continue
            rows_out.append(
                {
                    # The corpus's own domain, not racecar's. This row is a verb THIS repo
                    # implements and never declared, so labelling it `racecar` in an
                    # adopter would name a fixer that has never heard of the verb.
                    "domain": corpus_domain(lexicon),
                    "noun": noun,
                    "verb": verb,
                    "params": sorted(long_flags_at(declared_flags, noun, verb)),
                    "in_graph": False,
                    "implemented": True,
                    "params_in_graph": [],
                    "params_implemented": sorted(
                        long_flags_at(declared_flags, noun, verb)
                    ),
                }
            )
    return sorted(rows_out, key=lambda r: (r["noun"], r["verb"]))


class Reach(NamedTuple):
    """One noun's counts: what the LEXICON declares, and what each route actually carries.

    `bin` is `scripts/<noun>.py`; `cli` is `python -m <pkg>.<noun>`. Separate columns because
    they are separate surfaces -- a noun may have either, both or neither -- and collapsing
    them into one "implemented" number loses which one moved. `None` means the route is
    ABSENT, which is not the same as zero: a noun with no script has nothing to disagree
    with, and scoring it `0 <` would put a mismatch marker on every module-backed noun and
    make the marker worthless.
    """

    noun: str
    verbs: int
    verbs_bin: int | None
    verbs_cli: int | None
    params: int
    params_bin: int | None
    params_cli: int | None


def reach(lexicon: Lexicon, root: Path, selected: list[str]) -> list[Reach]:
    """Per noun, the lexicon's counts beside each route's."""
    pkg = package_dir(root)
    # Refused rather than emptied, for the reason `status_rows` states.
    offered = _audit.cli_verbs(root) if _audit.has_cli(root) else {}
    flags = _audit.flag_sites(root) if _audit.has_cli(root) else {}
    verb_args = _audit.cli_args(root) if _audit.has_cli(root) else {}
    out: list[Reach] = []

    for chain in sorted(eligible_nouns(lexicon, selected)):
        noun = ".".join(chain) or root_noun(lexicon)
        dotted = ".".join((pkg.name, *chain)) if pkg else noun
        site = site_noun(chain, pkg, noun)

        declared = declared_verbs(lexicon, chain)
        want_params: set[str] = set()
        for verb in declared:
            want_params |= set(_params_of(verb_node(lexicon, noun, verb)))

        script = _audit.script_surface(root, noun) if len(chain) == 1 else {}
        has_bin = bool(script) or (root / "scripts" / f"{noun}.py").is_file()
        bin_params: set[str] = set()
        for got in script.values():
            bin_params |= got

        cli_here = offered.get(dotted)
        # Per VERB, never the node's own flags. `--root` sits on `racecar.arch` itself and
        # belongs to no verb node, so counting it would report `>` on half the tree -- a
        # gap between two things that are not measuring the same set.
        verbs_here = (cli_here or set()) | set(script)
        # `flag_sites` keys by the noun WITHOUT the package prefix (`site_noun`). Comparing
        # `dotted` against a stripped site matches nothing, and every noun's CLI param
        # count would read 0 with the gate green, because this table is a rendering and
        # a `!` row is not a finding. A count of zero and a count nobody computed look
        # identical.
        cli_params = {
            flag[2:]
            for flag, sites in flags.items()
            if flag.startswith("--") and any(f"{site} {v}" in sites for v in verbs_here)
        }
        # A positional is a param too, spelled by its dest; it has no `--` site to find.
        cli_params |= {
            str(arg["dest"]).replace("_", "-")
            for (module, verb), args in verb_args.items()
            if module == dotted and verb in verbs_here
            for arg in args
            if not arg.get("flags")
        }
        out.append(
            Reach(
                noun,
                len(declared),
                len(script) if has_bin else None,
                len(cli_here) if cli_here is not None else None,
                len(want_params - FORM_PARAMS),
                len(bin_params - FORM_PARAMS) if has_bin else None,
                len(cli_params - FORM_PARAMS) if cli_here is not None else None,
            )
        )
    return out


def document(g: Graph, run: Checked) -> dict[str, Any]:
    """`check --json`: the one document both routes print, `{domains, rows, nouns, findings,
    answers}`.

    The same rows `list --json` emits, each carrying the two verdicts; the per-noun counts the
    coverage table renders from, so the table is derivable from the document rather than only
    printable; every finding as a `{severity, subject, rule, message}` record; and every tuple
    against every check. `g` is the graph and `run` what `_loop.checked` returned for it.
    """
    selected = list(g.selected)
    return {
        "domains": selected,
        "rows": [
            {
                "domain": r["domain"],
                "noun": r["noun"],
                "verb": r["verb"],
                "params": r["params"],
                "in_graph": r["in_graph"],
                "implemented": r["implemented"],
            }
            for r in status_rows(g.lexicon, g.root, selected)
        ],
        "nouns": [
            {
                "noun": n.noun,
                "verbs": n.verbs,
                "verbs_bin": n.verbs_bin,
                "verbs_cli": n.verbs_cli,
                "params": n.params,
                "params_bin": n.params_bin,
                "params_cli": n.params_cli,
            }
            for n in reach(g.lexicon, g.root, selected)
        ],
        "findings": run.findings,
        "answers": matrix(run.answers, g.root),
    }
