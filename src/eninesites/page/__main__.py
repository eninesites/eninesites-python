"""CLI entry: python -m eninesites.page

TODO — what `page` means

A thin surface over ``api``: each verb is one ``_cmd_<verb>`` that calls one api function
and hands its result to a renderer. It decides nothing and prints nothing itself. Every
verb takes ``--json``: the api result as JSON, the shape ``output()`` publishes, instead of
the text view. ``main()`` is ``lib.cli.run``: an ``ApiError`` the api raises is printed on
stderr and its ``exit_code`` returned.
"""

# Every verb's parser block restates the shared --domain, --api-key, --base-url and
# --project-name flags, because racecar's audit reads each flag from that verb's own
# add_argument call; factoring them into a helper would hide them from it. The repetition
# across nouns is that form's, so pylint's duplicate-code check does not apply here.
# pylint: disable=duplicate-code

from __future__ import annotations

import argparse

from eninesites.errors import ApiError
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.renderer import json as json_renderer
from eninesites.page import api
from eninesites.page.lib.renderer import plaintext
from eninesites.schema import returns


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.page", commands(), subcommands())


def _cmd_crawl(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.crawl_page(url=args.url)
    return json_renderer.show(args, result, plaintext.print_crawl)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        (
            "crawl",
            "Not available over the REST API: it exists only as the chat tool `crawl_url`",
        ),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.page",
        description="TODO — what `page` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_crawl = sub.add_parser("crawl")
    p_crawl.add_argument("--url", help="TODO — what `url` means")
    p_crawl.set_defaults(func=_cmd_crawl)

    for verb_parser in sub.choices.values():
        json_renderer.add_flag(verb_parser)
    return p


def main(argv: list[str] | None = None) -> int:
    """Run one verb; with none, list the sub-nouns, or print the help when there are none."""
    listing = _print_commands if commands() else None
    return run(parser(), argv, refusal=ApiError, error=plaintext.error, listing=listing)


def output() -> list[tuple[dict[str, object], dict[str, object]]]:
    """(params, schema) per verb, generated from each api function's return type."""
    return [({"phase": verb}, returns(fn)) for verb, fn in sorted(api.VERBS.items())]


if __name__ == "__main__":
    raise SystemExit(main())
