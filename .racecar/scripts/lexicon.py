#!/usr/bin/env python3
"""The lexicon: racecar's graph of named artifacts, and the one tool that grades it.

`docs/lexicon/` holds every NAMED thing racecar ships or borrows — nouns, verbs, params,
nodes, keys, artifacts, facts. `architecture/` holds the IDEAS. The line between them is
whether an authority fixes the name: Ansible could rename `playbook` tomorrow and racecar
would follow, so `playbook` is a lexicon word; nobody can rename idempotence-the-property,
so P-05's argument is architecture.

**The lexicon is many graphs in one, demarcated by `domain:`.** `--domain` does not filter
rows, it projects a subgraph out. A word both domains use is the single vertex where the two
meet, which is the whole reason this is one tree and not three: separate trees cannot share a
vertex, and `host` would exist twice.

`domain:` records who FIXES a word, not who mentions it. Borrowing a word into racecar's own
surface makes racecar a fixer of it too — once `racecar host` ships, what it does under that
name is racecar's to keep stable — so a borrowed word racecar ships carries both, and its node
owes a section each.

A node's kind is its frontmatter declaration, never its directory: flag nodes carry
`kind: param`.

    lexicon check    grade the lexicon against itself and against src/<pkg>
    lexicon list     one row per noun and verb: domain, noun, verb, node, params
    lexicon create   declare a noun, verb or param, or put one reported tuple into canon
    lexicon derive   the entries the cli implements and the lexicon lacks, as create commands

Delivered to adopters, so it imports no `racecar` package: an adopter carries this checker
without carrying the library it grades.

**The implementation is `lib/lexicon/`**, one module per verb (`_check`, `_list`, `_create`,
`_derive`), each with a `main` over the values this file's parser produced. This file is the
command line over them and nothing else, the shape `graph.py` and `surface.py` have.

Complexity: O(P log P + F*D + T*L), P = lexicon nodes (one frontmatter parse each, memoized
by (base, subdir)), F*D = flag spellings x declaration sites from one cached CLI audit,
T*L = retired terms x lines scanned, prefiltered by a substring test before any regex runs.
"""

import argparse
import sys
from pathlib import Path

from lib.lexicon import _check, _create, _derive, _list
from lib.lexicon._eligible import eligible_domains
from lib.lexicon._nodes import (
    CANON_ENV,
    DEFAULT_TERMS,
    FLAG_DIR,
    OK,
    UNMET,
    LexiconError,
    find_root,
)
from lib.lexicon.renderer import text
from lib.shared import _cli


def _resolve(args: argparse.Namespace) -> tuple[Path, Path, list[str]]:
    root = args.root.resolve() if args.root else find_root()
    terms = args.data.resolve() if args.data else root / DEFAULT_TERMS
    selected = eligible_domains(
        terms, getattr(args, "domain", None), every=getattr(args, "all", False)
    )
    return root, terms, selected


def _add_common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--root", type=Path, default=None, help="the repo to act on")
    sub.add_argument(
        "--data", type=Path, default=None, help="the corpus a graph command reads"
    )
    sub.add_argument(
        "--domain",
        action="append",
        default=None,
        help="which projection to act on (repeatable; default: this corpus's own)",
    )
    sub.add_argument(
        "--all",
        action="store_true",
        help="operate on everything rather than a named subset",
    )


def parser(prog: str = "lexicon.py") -> argparse.ArgumentParser:
    """The command line, for this script and for every route that wraps it.

    One parser, so `python -m racecar.lexicon` offers exactly these flags with exactly
    this help: a wrapper that built its own would drift from it one word at a time.
    """
    built = _cli.NounParser(prog=prog, description=__doc__.splitlines()[0])
    phases = built.add_subparsers(dest="phase")

    check = phases.add_parser(
        "check", help="Grade the lexicon and the tree it projects onto"
    )
    _add_common(check)
    check.add_argument(
        "--canon",
        type=Path,
        default=None,
        help=f"the racecar checkout holding {FLAG_DIR} (default: ${CANON_ENV}, "
        "the installed skill, or this repo)",
    )
    check.add_argument(
        "--apply",
        action="store_true",
        help="do the work for real — stub what is missing",
    )
    check.add_argument(
        "--answers",
        action="store_true",
        help="every tuple against every check, passes included — the whole answer set",
    )
    check.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on any finding, not only a blocking one",
    )
    check.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON on stdout instead of prose",
    )
    check.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="the destination file to write the JSON to (implies --json)",
    )

    lister = phases.add_parser(
        "list", help="The tuple list: (domain, noun, verb, params)"
    )
    _add_common(lister)
    lister.add_argument(
        "--kind",
        action="append",
        default=None,
        help="list the WORDS of this kind instead of the commands (repeatable)",
    )
    lister.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON on stdout instead of prose",
    )
    lister.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="the destination file to write the JSON to (implies --json)",
    )
    lister.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on any finding, not only a blocking one; a listing has none",
    )

    create = phases.add_parser(
        "create",
        help="Declare a noun, verb or param, or put one reported tuple into canon",
    )
    _add_common(create)
    create.add_argument("--apply", action="store_true", help="do the work for real")
    # One of the two forms is required, and argparse says so: with neither, the verb's
    # help and `needs --noun or --tuple` rather than a refusal (arch-python/CLI.md B2).
    # With both, it refuses rather than silently dropping `--tuple`.
    form = create.add_mutually_exclusive_group(required=True)
    form.add_argument(
        "--tuple",
        action="append",
        default=None,
        metavar="DOMAIN/NOUN/VERB",
        help="put ONE tuple into canon, spelled exactly as `check` hands it back "
        "(repeatable); the one intentional act in this system",
    )
    form.add_argument(
        "--noun",
        default=None,
        help="declare this noun (dotted for a sub-noun); get-or-create",
    )
    create.add_argument("--verb", default=None, help="declare this verb of --noun")
    create.add_argument(
        "--param",
        action="append",
        default=None,
        help="declare this param of --verb (repeatable)",
    )
    create.add_argument(
        "--json",
        action="store_true",
        help="emit what was declared or created as JSON on stdout instead of prose",
    )
    create.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="the destination file to write the JSON to (implies --json)",
    )
    create.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero on any finding, not only a blocking one; a create has none",
    )

    derive_verb = phases.add_parser(
        "derive",
        help="The entries the cli implements and the lexicon lacks, as create commands",
    )
    # Not `_add_common`: `--domain` and `--all` pick a projection to grade, and derive
    # grades nothing. The same four flags as `racecar.lexicon derive`, so the two routes are
    # one command.
    derive_verb.add_argument(
        "--root", type=Path, default=None, help="repo to act on (default: .git walk-up)"
    )
    derive_verb.add_argument(
        "--data", type=Path, default=None, help="the graph (default: docs/lexicon)"
    )
    derive_verb.add_argument(
        "--apply",
        action="store_true",
        help="do the work for real — run each create; default prints them only",
    )
    derive_verb.add_argument("--json", action="store_true", help="the records, as JSON")
    _cli.mark_subparsers(phases)
    return built


def main(argv: list[str] | None = None, prog: str = "lexicon.py") -> int:
    """One tool over the lexicon: grade it, list it, or declare in it."""
    parser_ = parser(prog)
    args = _cli.parse_args(parser_, argv)
    if not args.phase:
        parser_.print_help()
        return OK

    try:
        root, terms, selected = _resolve(args)
    except LexiconError as err:
        print(text.cannot_run(err), file=sys.stderr)
        return UNMET

    # `create` is what makes a lexicon, so a repo without one is where it starts.
    if not terms.exists() and args.phase != "create":
        as_json = getattr(args, "json", False)
        print(
            text.no_lexicon(root),
            file=sys.stderr if as_json else sys.stdout,
        )
        if as_json:
            print("[]")
        return OK

    # A table rather than a compare chain: a verb is one entry, which is the same reason the
    # checks are a loop over a list. `check` is the default because it is what a bare
    # invocation of this script means.
    dispatch = {
        "list": lambda: _list.main(
            terms, selected, kind=args.kind, as_json=args.json, output=args.output
        ),
        "create": lambda: _create.main(
            root,
            terms,
            selected,
            noun=args.noun,
            verb=args.verb,
            params=args.param,
            tuples=args.tuple,
            apply=args.apply,
            as_json=args.json,
            output=args.output,
        ),
        "derive": lambda: _derive.main(
            root, terms, apply=args.apply, as_json=args.json
        ),
    }
    run = dispatch.get(args.phase)
    try:
        return (
            run()
            if run
            else _check.main(
                root,
                terms,
                selected,
                canon=args.canon,
                apply=args.apply,
                answers=args.answers,
                strict=args.strict,
                as_json=args.json,
                output=args.output,
            )
        )
    except LexiconError as err:
        # Every verb, not just `check`. A bad `--tuple` reaching the top as a traceback
        # would tell a caller what line raised and not what they typed wrong.
        print(text.cannot_run(err), file=sys.stderr)
        return UNMET


if __name__ == "__main__":
    sys.exit(main())
