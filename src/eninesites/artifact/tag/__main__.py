"""CLI entry: python -m eninesites.artifact.tag

TODO — what `tag` means

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

from eninesites.artifact.tag import api
from eninesites.artifact.tag.lib.renderer import plaintext
from eninesites.errors import ApiError
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.renderer import json as json_renderer
from eninesites.schema import returns


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.artifact.tag", commands(), subcommands())


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_tag(
        slug=args.slug,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_attach(args: argparse.Namespace) -> int:
    result = api.attach_tag(
        slug=args.slug,
        tag=args.tag,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_attach)


def _cmd_detach(args: argparse.Namespace) -> int:
    result = api.detach_tag(
        slug=args.slug,
        tag=args.tag,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_detach)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("list", "List tags on artifact"),
        ("attach", "Assign tag to artifact (idempotent)"),
        ("detach", "Remove tag from artifact"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.artifact.tag",
        description="TODO — what `tag` means",
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

    p_attach = sub.add_parser("attach")
    p_attach.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_attach.add_argument("--tag", required=True, help="TODO — what `tag` means")
    p_attach.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_attach.add_argument("--api-key", help="TODO — what `api-key` means")
    p_attach.add_argument("--base-url", help="TODO — what `base-url` means")
    p_attach.add_argument("--project-name", help="TODO — what `project-name` means")
    p_attach.set_defaults(func=_cmd_attach)

    p_detach = sub.add_parser("detach")
    p_detach.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_detach.add_argument("--tag", required=True, help="TODO — what `tag` means")
    p_detach.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_detach.add_argument("--api-key", help="TODO — what `api-key` means")
    p_detach.add_argument("--base-url", help="TODO — what `base-url` means")
    p_detach.add_argument("--project-name", help="TODO — what `project-name` means")
    p_detach.set_defaults(func=_cmd_detach)

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
