"""CLI entry: python -m eninesites.media

TODO — what `media` means

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
from eninesites.media import api
from eninesites.media.lib.renderer import plaintext
from eninesites.schema import returns


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.media", commands(), subcommands())


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_media(
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_upload(args: argparse.Namespace) -> int:
    result = api.upload_media(
        files=args.files,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_upload)


def _cmd_get(args: argparse.Namespace) -> int:
    result = api.get_media(
        slug=args.slug,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_get)


def _cmd_update(args: argparse.Namespace) -> int:
    result = api.update_media(
        slug=args.slug,
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        data=args.data,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_update)


def _cmd_delete(args: argparse.Namespace) -> int:
    result = api.delete_media(
        slug=args.slug,
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
        ("list", "List media files (paginated)"),
        ("upload", "Upload media files (max 10MB each, supports multiple)"),
        ("get", "Get media"),
        ("update", "Update media filename"),
        ("delete", "Delete media"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.media",
        description="TODO — what `media` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_list = sub.add_parser("list")
    p_list.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_list.add_argument("--api-key", help="TODO — what `api-key` means")
    p_list.add_argument("--base-url", help="TODO — what `base-url` means")
    p_list.add_argument("--project-name", help="TODO — what `project-name` means")
    p_list.set_defaults(func=_cmd_list)

    p_upload = sub.add_parser("upload")
    p_upload.add_argument("--files", required=True, help="TODO — what `files` means")
    p_upload.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_upload.add_argument("--api-key", help="TODO — what `api-key` means")
    p_upload.add_argument("--base-url", help="TODO — what `base-url` means")
    p_upload.add_argument("--project-name", help="TODO — what `project-name` means")
    p_upload.set_defaults(func=_cmd_upload)

    p_get = sub.add_parser("get")
    p_get.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_get.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_get.add_argument("--api-key", help="TODO — what `api-key` means")
    p_get.add_argument("--base-url", help="TODO — what `base-url` means")
    p_get.add_argument("--project-name", help="TODO — what `project-name` means")
    p_get.set_defaults(func=_cmd_get)

    p_update = sub.add_parser("update")
    p_update.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_update.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_update.add_argument("--api-key", help="TODO — what `api-key` means")
    p_update.add_argument("--base-url", help="TODO — what `base-url` means")
    p_update.add_argument("--project-name", help="TODO — what `project-name` means")
    p_update.add_argument("--data", type=Path, help="TODO — what `data` means")
    p_update.set_defaults(func=_cmd_update)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument(
        "--slug",
        required=True,
        help="Artifact name (tried first) or slug (fallback lookup key)",
    )
    p_delete.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_delete.add_argument("--api-key", help="TODO — what `api-key` means")
    p_delete.add_argument("--base-url", help="TODO — what `base-url` means")
    p_delete.add_argument("--project-name", help="TODO — what `project-name` means")
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
