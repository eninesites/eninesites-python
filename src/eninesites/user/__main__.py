"""CLI entry: python -m eninesites.user

Site user management

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
from eninesites.lib import dryrun
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.renderer import json as json_renderer
from eninesites.schema import returns
from eninesites.user import api
from eninesites.user.lib.renderer import plaintext


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.user", commands(), subcommands())


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_user(
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_add(args: argparse.Namespace) -> int:
    result = api.add_user(
        username=args.username,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        role=args.role,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_add)


def _cmd_get(args: argparse.Namespace) -> int:
    result = api.get_user(
        username=args.username,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_get)


def _cmd_update(args: argparse.Namespace) -> int:
    result = api.update_user(
        username=args.username,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        role=args.role,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_update)


def _cmd_remove(args: argparse.Namespace) -> int:
    result = api.remove_user(
        username=args.username,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_remove)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("list", "List site users (paginated)"),
        ("add", "Add an existing user to the site, or update their role (admin only)"),
        ("get", "Get site user"),
        ("update", "Update user role (admin only)"),
        (
            "remove",
            "Remove a user from the site, unless they are its last admin (admin only)",
        ),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.user",
        description="Site user management",
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

    p_add = sub.add_parser("add")
    p_add.add_argument(
        "--username", required=True, help="Username of an existing eninesites user"
    )
    p_add.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_add.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_add.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_add.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_add.add_argument(
        "--role",
        required=True,
        help="AEO role code for content, or admin/editor/reader for users",
    )
    p_add.set_defaults(func=_cmd_add)

    p_get = sub.add_parser("get")
    p_get.add_argument(
        "--username", required=True, help="Username of an existing eninesites user"
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
        "--username", required=True, help="Username of an existing eninesites user"
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
        "--role",
        required=True,
        help="AEO role code for content, or admin/editor/reader for users",
    )
    p_update.set_defaults(func=_cmd_update)

    p_remove = sub.add_parser("remove")
    p_remove.add_argument(
        "--username", required=True, help="Username of an existing eninesites user"
    )
    p_remove.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_remove.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_remove.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_remove.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_remove.set_defaults(func=_cmd_remove)

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
