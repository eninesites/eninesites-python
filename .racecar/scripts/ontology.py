#!/usr/bin/env python3
"""Check, or derive, the ontology a body of source material conforms to (`ONTOLOGY.md`).

Three verbs, two operations. `identify` and `derive` both infer a candidate ontology from
field presence in `--data` -- the same underlying pass -- and differ only in whether the
result is written to `--meta`: `identify` reports, read-only; `derive` writes. Two named
verbs rather than one verb and a mode flag, so a caller scanning `--help` sees the
read/write split in the verb's name. `check` is the different operation: scoring `--data`
against an ALREADY-declared ontology at `--meta`.

    ontology identify --data D [--json]
    ontology derive   --data D --meta M [--json]
    ontology check    --data D --meta M [--domain X ...] [--json]

**The implementation is `lib/ontology/`.** This file is the command line over it and
nothing else: a file directly under `scripts/` is something an adopter runs, and everything
it imports lives below `lib/`. `lib.ontology._kinds` reads a declared ontology, samples a
corpus and scores or infers; `_identify`, `_derive` and `_check` are the verbs.
`racecar.graph.ontology` is the other route, and it runs this file's `parser` and `main`
under its own name.

Delivered to adopters, so it imports no `racecar` package: racecar DELIVERS an ontology
(`docs/rc_lexicon/ontology/`, landing at `.racecar/docs/lexicon/ontology/`) whose kind nodes
are read as data, and a reader has to travel with the thing it reads.

Complexity: O(S), S = sources read (one frontmatter parse each) x C corpora joined
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib.ontology import _check, _derive, _identify
from lib.shared import _cli
from lib.shared._as_json import add_json


def parser(prog: str = "ontology.py") -> argparse.ArgumentParser:
    """The command line, for this script and for every route that wraps it.

    One parser, so `python -m racecar.graph.ontology` offers exactly these flags with
    exactly this help: a wrapper that built its own would drift from it one word at a time.
    """
    built = _cli.NounParser(
        prog=prog,
        description="racecar ontology lib (what kinds does a corpus contain?)",
    )
    verbs = built.add_subparsers(dest="phase")

    identify = verbs.add_parser(
        "identify", help="Infer a candidate ontology from --data, read-only"
    )
    identify.add_argument(
        "--data", type=Path, required=True, help="Corpus to infer from"
    )

    derive = verbs.add_parser(
        "derive", help="Infer a candidate ontology from --data, write it to --meta"
    )
    derive.add_argument("--data", type=Path, required=True, help="Corpus to infer from")
    derive.add_argument(
        "--meta", type=Path, required=True, help="Where to write the proposal"
    )

    check = verbs.add_parser(
        "check", help="Score --data against the ontology declared at --meta"
    )
    check.add_argument("--data", type=Path, required=True, help="Corpus to score")
    check.add_argument(
        "--meta", type=Path, required=True, help="Declared ontology to score against"
    )
    check.add_argument(
        "--domain",
        action="append",
        default=None,
        help="Project onto one domain before grading (repeatable). Requires the corpus to "
        "declare `partition:`; a corpus without one is abstract and has no projections.",
    )
    for verb_parser in verbs.choices.values():
        add_json(verb_parser)
    _cli.mark_subparsers(verbs)
    return built


def main(argv: list[str] | None = None, prog: str = "ontology.py") -> int:
    """Print help when called bare; otherwise run the requested verb."""
    parser_ = parser(prog)
    args = _cli.parse_args(parser_, argv)
    if args.phase is None:
        parser_.print_help()
        return 0
    if args.phase == "check":
        return _check.main(args.data, args.meta, args.domain, as_json=args.json)
    if args.phase == "derive":
        return _derive.main(args.data, args.meta, as_json=args.json)
    return _identify.main(args.data, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
