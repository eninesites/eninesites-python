"""CLI entry: python -m eninesites.theme

TODO — what `theme` means

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
from eninesites.schema import returns
from eninesites.theme import api
from eninesites.theme.lib.renderer import plaintext


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return [
        ("custom", "TODO — what `custom` means"),
    ]


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.theme", commands(), subcommands())


def _cmd_create(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.create_theme(name=args.name)
    return json_renderer.show(args, result, plaintext.print_create)


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_theme(
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_delete(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.delete_theme(name=args.name, force=args.force)
    return json_renderer.show(args, result, plaintext.print_delete)


def _cmd_check(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.check_theme(name=args.name, apply=args.apply)
    return json_renderer.show(args, result, plaintext.print_check)


def _cmd_review(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.review_theme(name=args.name)
    return json_renderer.show(args, result, plaintext.print_review)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        (
            "create",
            "Not available over the REST API: it exists only as `manage.py theme --create`",
        ),
        ("list", "List themes selectable by this site"),
        (
            "delete",
            "Not available over the REST API: it exists only as `manage.py theme --delete`",
        ),
        (
            "check",
            "Not available over the REST API: it exists only as `manage.py theme --check`",
        ),
        (
            "review",
            "Not available over the REST API: it exists only as `manage.py theme --review`",
        ),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.theme",
        description="TODO — what `theme` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", help="TODO — what `name` means")
    p_create.set_defaults(func=_cmd_create)

    p_list = sub.add_parser("list")
    p_list.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_list.add_argument("--api-key", help="TODO — what `api-key` means")
    p_list.add_argument("--base-url", help="TODO — what `base-url` means")
    p_list.add_argument("--project-name", help="TODO — what `project-name` means")
    p_list.set_defaults(func=_cmd_list)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--name", help="TODO — what `name` means")
    p_delete.add_argument(
        "--force", action="store_true", help="TODO — what `force` means"
    )
    p_delete.set_defaults(func=_cmd_delete)

    p_check = sub.add_parser("check")
    p_check.add_argument("--name", help="TODO — what `name` means")
    p_check.add_argument(
        "--apply", action="store_true", help="TODO — what `apply` means"
    )
    p_check.set_defaults(func=_cmd_check)

    p_review = sub.add_parser("review")
    p_review.add_argument("--name", help="TODO — what `name` means")
    p_review.set_defaults(func=_cmd_review)

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
