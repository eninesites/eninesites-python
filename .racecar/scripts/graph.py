#!/usr/bin/env python3
"""Project this repo's graphs into the README's ``## Graphs`` section.

**Counts are derived; the shape is authored.** Those are different kinds of claim and the
split is the whole design:

- **Every count comes from the artifact that already owns it** -- ``surface.jsonl``'s own
  line count, ``structural_findings``'s own node set, ``check_doc_graph``'s own ``in_scope``
  predicate. Nothing here re-derives a number from source, because that is a second home
  for a fact and it drifts.
- **Which graph feeds which is authored**, in each graph node's ``edges:``. "``check_surface.py``
  compares every row's ``cli`` against the walked command tree" is a structural claim no
  predicate recovers from source. So it is written down -- and then CHECKED: every edge
  names the file that implements it, and a missing file is a finding. The assertion can
  fail, which is what keeps it an assertion rather than a caption.

**Text boxes, not mermaid.** racecar contains no mermaid fence anywhere. The content is a
handful of boxes and arrows, which ASCII draws in a fenced ``text`` block that is diffable,
greppable, and renders identically on GitHub, in a terminal and in an agent's context.
``arch-python/SURFACES.md`` §1 already draws its shape this way, and ``render_cli_section``
already emits a fenced ``text`` block into this same README.

Usage:
    graph generate --docs                    # report; write nothing
    graph generate --docs --apply            # rewrite README.md's ## Graphs block
    graph generate --docs --strict           # exit 1 if that block is stale
    graph generate --docs --apply --strict   # rewrite it AND report it was stale

**The implementation is `lib/graph/`.** This file is the command line over it and nothing
else: a file directly under `scripts/` is something an adopter runs, and everything it
imports lives below `lib/`. `python -m racecar.graph` is the other route, and it runs this
file's `parser` and `main` under its own name.

Complexity: O(n) in tracked markdown plus one CLI-tree audit; the audit dominates.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from lib.graph import _build, _check, _generate, _materialize, _perimeter
from lib.shared import _cli
from lib.shared._as_json import add_json

#: This script's name on its own command line, and the default every route overrides.
PROG = "graph.py"


def parser(prog: str = PROG) -> argparse.ArgumentParser:
    """Build this script's parser, under `prog`. Does not call parse_args().

    One parser, so `python -m racecar.graph` offers exactly these flags with exactly this
    help: a wrapper that built its own would drift from it one word at a time.

    Subcommands rather than bare flags, because the routed surface spells these
    `python -m racecar.graph <verb>` and a script that has to translate its own verb into
    someone else's flags is a place for the two to drift apart. The five here are the five
    the lexicon declares for this noun: a delivered noun script creates a `bin` route for
    the WHOLE noun, and every tuple the lexicon declares has to answer on every route it
    has -- carrying only some of them is the drift, not the economy it looks like.
    """
    built = _cli.NounParser(prog=prog)
    sub = built.add_subparsers(dest="verb")

    gen = sub.add_parser(
        "generate", help="Project this repo's declared graphs onto a surface"
    )
    # Required, because it is the only artefact this verb knows. A missing argument gets
    # the help (CLI.md B2), as `surface generate --docs` does.
    gen.add_argument(
        "--docs",
        action="store_true",
        required=True,
        help="Generate the DOCS for the graphs, rather than the graphs themselves",
    )
    gen.add_argument("--apply", action="store_true", help="Rewrite the block for real")
    gen.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the block was stale, whether or not it was rewritten",
    )
    # One selector at most. `--all` is the default rather than a demand: `all.md` makes a
    # scope flag "often required, so that nothing runs against an unstated scope", and the
    # bar there is blast radius -- rewriting a block between markers is regenerable, so the
    # scope defaults and the word is still accepted so a script can state what it meant.
    scope = gen.add_mutually_exclusive_group()
    scope.add_argument(
        "--all", action="store_true", help="Every artifact this command produces"
    )
    scope.add_argument("--path", type=Path, default=None, help="That one artifact")
    scope.add_argument("--graph", default=None, help="That one declared graph")
    # `--json` shapes the report and never the work (`docs/lexicon/param/json.md`): the
    # same graphs, the same decision, the same exit code, rendered for a machine. What it
    # carries is the widened reader output -- nodes and edges, not the counts the prose
    # table shows -- because that is the whole report, and the table is a reduction of it.
    gen.add_argument(
        "--json", action="store_true", help="Emit the graphs as JSON instead of prose"
    )
    gen.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write the JSON to this file instead of stdout (requires --json)",
    )

    chk = sub.add_parser(
        "check",
        help="Gate the corpus: topology (shape) + ontology (types), the superset",
    )
    chk.add_argument("--data", type=Path, default=None, help="Corpus to gate")
    chk.add_argument("--meta", type=Path, default=None, help="Topology + ontology")

    mat = sub.add_parser("materialize", help="Render the tree, or one view of it")
    mat.add_argument("--data", type=Path, default=None, help="Corpus to read")
    mat.add_argument("--edges", action="store_true", help="Print the DAG's edges")
    mat.add_argument(
        "--orphans", action="store_true", help="Print nodes nothing reaches"
    )
    mat.add_argument(
        "--coverage", action="store_true", help="Declared against enforced"
    )

    per = sub.add_parser(
        "perimeter", help="Derive the real declaration set from the delivered checkers"
    )
    per.add_argument("--data", type=Path, default=None, help="Corpus to gate")

    bld = sub.add_parser(
        "build", help="Materialize a graph at --dest from source material at --data"
    )
    bld.add_argument("--data", type=Path, required=True, help="Source material")
    bld.add_argument("--dest", type=Path, required=True, help="Graph to write")
    bld.add_argument("--meta", type=Path, default=None, help="ontology.yaml")
    for verb_parser in sub.choices.values():
        add_json(verb_parser)  # `generate` keeps its own `--json`
    _cli.mark_subparsers(sub)
    return built


def main(argv: list[str] | None = None, prog: str = PROG) -> int:
    """Parse, then hand the verb to the one function that answers it."""
    built = parser(prog)
    args = _cli.parse_args(built, argv)
    if args.verb is None:
        # Bare: describe, never act (CLI.md B1).
        built.print_help()
        return 0
    dispatch: dict[str, Callable[[], int]] = {
        "generate": lambda: _generate.main(
            docs=args.docs,
            apply=args.apply,
            strict=args.strict,
            path=args.path,
            graph=args.graph,
            as_json=args.json,
            output=args.output,
        ),
        "check": lambda: _check.main(args.data, args.meta, as_json=args.json),
        "materialize": lambda: _materialize.main(
            args.data,
            edges=args.edges,
            orphans=args.orphans,
            coverage=args.coverage,
            as_json=args.json,
        ),
        "perimeter": lambda: _perimeter.main(args.data, as_json=args.json),
        "build": lambda: _build.main(
            args.data, args.dest, args.meta, as_json=args.json
        ),
    }
    return dispatch[args.verb]()


if __name__ == "__main__":
    sys.exit(main())
