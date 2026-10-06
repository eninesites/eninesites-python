"""CLI entry: python -m eninesites.artifact.role

TODO — what `role` means

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

from eninesites.artifact.role import api
from eninesites.artifact.role.lib.renderer import plaintext
from eninesites.errors import ApiError
from eninesites.lib import dryrun
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.renderer import json as json_renderer
from eninesites.schema import returns


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.artifact.role", commands(), subcommands())


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_role(
        slug=args.slug,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_replace(args: argparse.Namespace) -> int:
    result = api.replace_role(
        slug=args.slug,
        role=args.role,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_replace)


def _cmd_assign(args: argparse.Namespace) -> int:
    result = api.assign_role(
        slug=args.slug,
        role=args.role,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_assign)


def _cmd_unassign(args: argparse.Namespace) -> int:
    result = api.unassign_role(
        slug=args.slug,
        role=args.role,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_unassign)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("list", "List XEO role codes assigned to artifact"),
        (
            "replace",
            "Replace the artifact's role set wholesale (idempotent; [] clears)",
        ),
        ("assign", "Add a single role to the artifact (idempotent)"),
        ("unassign", "TODO — what `unassign` means"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.artifact.role",
        description="TODO — what `role` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_list = sub.add_parser("list")
    p_list.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_list.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_list.add_argument("--api-key", help="TODO — what `api-key` means")
    p_list.add_argument("--base-url", help="TODO — what `base-url` means")
    p_list.add_argument("--project-name", help="TODO — what `project-name` means")
    p_list.set_defaults(func=_cmd_list)

    p_replace = sub.add_parser("replace")
    p_replace.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_replace.add_argument("--role", required=True, help="TODO — what `role` means")
    p_replace.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_replace.add_argument("--api-key", help="TODO — what `api-key` means")
    p_replace.add_argument("--base-url", help="TODO — what `base-url` means")
    p_replace.add_argument("--project-name", help="TODO — what `project-name` means")
    p_replace.set_defaults(func=_cmd_replace)

    p_assign = sub.add_parser("assign")
    p_assign.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_assign.add_argument("--role", required=True, help="TODO — what `role` means")
    p_assign.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_assign.add_argument("--api-key", help="TODO — what `api-key` means")
    p_assign.add_argument("--base-url", help="TODO — what `base-url` means")
    p_assign.add_argument("--project-name", help="TODO — what `project-name` means")
    p_assign.set_defaults(func=_cmd_assign)

    p_unassign = sub.add_parser("unassign")
    p_unassign.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_unassign.add_argument("--role", required=True, help="TODO — what `role` means")
    p_unassign.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_unassign.add_argument("--api-key", help="TODO — what `api-key` means")
    p_unassign.add_argument("--base-url", help="TODO — what `base-url` means")
    p_unassign.add_argument("--project-name", help="TODO — what `project-name` means")
    p_unassign.set_defaults(func=_cmd_unassign)

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
