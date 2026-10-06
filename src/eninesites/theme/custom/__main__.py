"""CLI entry: python -m eninesites.theme.custom

TODO — what `custom` means

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
from pathlib import Path

from eninesites.errors import ApiError
from eninesites.lib import dryrun
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.renderer import json as json_renderer
from eninesites.schema import returns
from eninesites.theme.custom import api
from eninesites.theme.custom.lib.renderer import plaintext


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.theme.custom", commands(), subcommands())


def _cmd_export(args: argparse.Namespace) -> int:
    result = api.export_custom(
        name=args.name,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_export)


def _cmd_import(args: argparse.Namespace) -> int:
    result = api.import_custom(
        name=args.name,
        parent=args.parent,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        path=args.path,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_import)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("export", "Export a custom theme by name"),
        ("import", "Import or update a custom theme from an exported payload"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.theme.custom",
        description="TODO — what `custom` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_export = sub.add_parser("export")
    p_export.add_argument("--name", help="TODO — what `name` means")
    p_export.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_export.add_argument("--api-key", help="TODO — what `api-key` means")
    p_export.add_argument("--base-url", help="TODO — what `base-url` means")
    p_export.add_argument("--project-name", help="TODO — what `project-name` means")
    p_export.set_defaults(func=_cmd_export)

    p_import = sub.add_parser("import")
    p_import.add_argument("--name", help="TODO — what `name` means")
    p_import.add_argument("--parent", help="TODO — what `parent` means")
    p_import.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_import.add_argument("--api-key", help="TODO — what `api-key` means")
    p_import.add_argument("--base-url", help="TODO — what `base-url` means")
    p_import.add_argument("--project-name", help="TODO — what `project-name` means")
    p_import.add_argument("--path", type=Path, help="TODO — what `path` means")
    p_import.set_defaults(func=_cmd_import)

    for verb_parser in sub.choices.values():
        json_renderer.add_flag(verb_parser)
    for name, verb_parser in sub.choices.items():
        if dryrun.is_write(api.VERBS[name]):
            dryrun.add_flag(verb_parser)
    return p


def main(argv: list[str] | None = None) -> int:
    """Run one verb; with none, list the sub-nouns, or print the help when there are none."""
    listing = _print_commands if commands() else None
    return run(
        parser(),
        argv,
        refusal=ApiError,
        error=plaintext.error,
        listing=listing,
        json_error=json_renderer.error,
    )


def output() -> list[tuple[dict[str, object], dict[str, object]]]:
    """(params, schema) per verb, generated from each api function's return type."""
    return [({"phase": verb}, returns(fn)) for verb, fn in sorted(api.VERBS.items())]


if __name__ == "__main__":
    raise SystemExit(main())
