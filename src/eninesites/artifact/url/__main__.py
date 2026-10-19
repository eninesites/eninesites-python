"""CLI entry: python -m eninesites.artifact.url

Add/remove external URLs for your artifacts

A thin surface over ``api``: each verb is one ``_cmd_<verb>`` that calls one api function
and hands its result to a renderer. It decides nothing and prints nothing itself. Every
verb takes ``--json``: the api result as JSON, the shape ``output()`` publishes, instead of
the text view. ``main()`` is ``lib.cli.run``: an ``ApiError`` the api raises is printed on
stderr and its ``exit_code`` returned.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from eninesites.artifact.url import api
from eninesites.artifact.url.lib.renderer import plaintext
from eninesites.errors import ApiError
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.renderer import json as json_renderer
from eninesites.schema import returns


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.artifact.url", commands(), subcommands())


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_url(
        slug=args.slug,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_attach(args: argparse.Namespace) -> int:
    result = api.attach_url(
        slug=args.slug,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        name=args.name,
        order=args.order,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_attach)


def _cmd_get(args: argparse.Namespace) -> int:
    result = api.get_url(
        slug=args.slug,
        id_=args.id_,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_get)


def _cmd_update(args: argparse.Namespace) -> int:
    result = api.update_url(
        slug=args.slug,
        id_=args.id_,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        data=args.data,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_update)


def _cmd_detach(args: argparse.Namespace) -> int:
    result = api.detach_url(
        slug=args.slug,
        id_=args.id_,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_detach)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("list", "List an artifact's external URLs, in order"),
        ("attach", "Attach a saved URL to an artifact"),
        ("get", "Get one of an artifact's external URLs"),
        ("update", "Reorder an external URL, or point it at another saved URL"),
        ("detach", "Detach an external URL from an artifact (the saved URL stays)"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.artifact.url",
        description="Add/remove external URLs for your artifacts",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_list = sub.add_parser("list")
    p_list.add_argument(
        "--slug",
        required=True,
        help="Artifact name or slug; for media and tags, their slug",
    )
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

    p_attach = sub.add_parser("attach")
    p_attach.add_argument(
        "--slug",
        required=True,
        help="Artifact name or slug; for media and tags, their slug",
    )
    p_attach.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_attach.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_attach.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_attach.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_attach.add_argument(
        "--name", required=True, help="Name of the site, theme, artifact, tag or URL"
    )
    p_attach.add_argument(
        "--order", help="Position among the artifact's URLs (default: 0, first)"
    )
    p_attach.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent or written, and change nothing",
    )
    p_attach.set_defaults(func=_cmd_attach)

    p_get = sub.add_parser("get")
    p_get.add_argument(
        "--slug",
        required=True,
        help="Artifact name or slug; for media and tags, their slug",
    )
    p_get.add_argument(
        "--id",
        dest="id_",
        required=True,
        help="Entry id, from the matching list command",
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
        "--slug",
        required=True,
        help="Artifact name or slug; for media and tags, their slug",
    )
    p_update.add_argument(
        "--id",
        dest="id_",
        required=True,
        help="Entry id, from the matching list command",
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
    p_update.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent or written, and change nothing",
    )
    p_update.set_defaults(func=_cmd_update)

    p_detach = sub.add_parser("detach")
    p_detach.add_argument(
        "--slug",
        required=True,
        help="Artifact name or slug; for media and tags, their slug",
    )
    p_detach.add_argument(
        "--id",
        dest="id_",
        required=True,
        help="Entry id, from the matching list command",
    )
    p_detach.add_argument(
        "--domain", help="Your site's domain (overrides the one set by site select)"
    )
    p_detach.add_argument("--api-key", help="Your API key (overrides the stored one)")
    p_detach.add_argument(
        "--base-url", help="Server to talk to (default: https://eninesites.com)"
    )
    p_detach.add_argument(
        "--project-name", help="Config profile to use (default: default)"
    )
    p_detach.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent or written, and change nothing",
    )
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
