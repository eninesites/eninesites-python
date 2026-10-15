"""CLI entry: python -m eninesites.url

External URL catalog — the external sibling of Media

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
from eninesites.url import api
from eninesites.url.lib.renderer import plaintext


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.url", commands(), subcommands())


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_url(
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_create(args: argparse.Namespace) -> int:
    result = api.create_url(
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        data=args.data,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_create)


def _cmd_get(args: argparse.Namespace) -> int:
    result = api.get_url(
        name=args.name,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_get)


def _cmd_update(args: argparse.Namespace) -> int:
    result = api.update_url(
        name=args.name,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        data=args.data,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_update)


def _cmd_delete(args: argparse.Namespace) -> int:
    result = api.delete_url(
        name=args.name,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_delete)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("list", "List external URL catalog entries (paginated)"),
        ("create", "Create an external URL catalog entry"),
        ("get", "Get external URL catalog entry"),
        ("update", "Update external URL catalog entry"),
        ("delete", "Delete external URL catalog entry"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.url",
        description="External URL catalog — the external sibling of Media",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_list = sub.add_parser("list")
    p_list.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_list.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_list.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_list.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_list.set_defaults(func=_cmd_list)

    p_create = sub.add_parser("create")
    p_create.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_create.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_create.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_create.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_create.add_argument(
        "--data", type=Path, help="JSON file with extra fields (- reads from stdin)"
    )
    p_create.set_defaults(func=_cmd_create)

    p_get = sub.add_parser("get")
    p_get.add_argument(
        "--name", required=True, help="Name of the site, theme, artifact, tag or URL"
    )
    p_get.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_get.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_get.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_get.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_get.set_defaults(func=_cmd_get)

    p_update = sub.add_parser("update")
    p_update.add_argument(
        "--name", required=True, help="Name of the site, theme, artifact, tag or URL"
    )
    p_update.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_update.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_update.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_update.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_update.add_argument(
        "--data", type=Path, help="JSON file with extra fields (- reads from stdin)"
    )
    p_update.set_defaults(func=_cmd_update)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument(
        "--name", required=True, help="Name of the site, theme, artifact, tag or URL"
    )
    p_delete.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_delete.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_delete.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_delete.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_delete.set_defaults(func=_cmd_delete)

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
