"""CLI entry: python -m eninesites.site

TODO — what `site` means

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
from eninesites.site import api
from eninesites.site.lib.renderer import plaintext


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return []


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites.site", commands(), subcommands())


def _cmd_create(args: argparse.Namespace) -> int:
    result = api.create_site(
        name=args.name,
        user=args.user,
        domain=args.domain,
        email=args.email,
        phone=args.phone,
        theme=args.theme,
        plan=args.plan,
        sample=args.sample,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        data=args.data,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_create)


def _cmd_list(args: argparse.Namespace) -> int:
    result = api.list_site(
        api_key=args.api_key, base_url=args.base_url, project_name=args.project_name
    )
    return json_renderer.show(args, result, plaintext.print_list)


def _cmd_dump(args: argparse.Namespace) -> int:
    result = api.dump_site(
        domain=args.domain,
        output=args.output,
        format_=args.format_,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_dump)


def _cmd_load(args: argparse.Namespace) -> int:
    result = api.load_site(
        domain=args.domain,
        name=args.name,
        user=args.user,
        email=args.email,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        path=args.path,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_load)


def _cmd_restore(args: argparse.Namespace) -> int:
    result = api.restore_site(
        mode=args.mode,
        domain=args.domain,
        name=args.name,
        user=args.user,
        plan=args.plan,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        path=args.path,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_restore)


def _cmd_copy(args: argparse.Namespace) -> int:
    result = api.copy_site(
        domain=args.domain,
        to=args.to,
        user=args.user,
        name=args.name,
        plan=args.plan,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_copy)


def _cmd_configure(args: argparse.Namespace) -> int:
    result = api.configure_site(
        domain=args.domain,
        title=args.title,
        subtitle=args.subtitle,
        copyright_=args.copyright_,
        theme=args.theme,
        colors_primary=args.colors_primary,
        colors_secondary=args.colors_secondary,
        colors_accent=args.colors_accent,
        colors_body=args.colors_body,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        path=args.path,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_configure)


def _cmd_delete(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.delete_site(domain=args.domain, dry_run=args.dry_run)
    return json_renderer.show(args, result, plaintext.print_delete)


def _cmd_check(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.check_site(domain=args.domain)
    return json_renderer.show(args, result, plaintext.print_check)


def _cmd_review(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.review_site(domain=args.domain)
    return json_renderer.show(args, result, plaintext.print_review)


def _cmd_select(args: argparse.Namespace) -> int:
    result = api.select_site(
        domain=args.domain,
        project_name=args.project_name,
        api_key=args.api_key,
        base_url=args.base_url,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_select)


def _cmd_randomize_subdomain(args: argparse.Namespace) -> int:
    result = api.randomize_subdomain_site(
        domain=args.domain,
        api_key=args.api_key,
        base_url=args.base_url,
        project_name=args.project_name,
        dry_run=args.dry_run,
    )
    return json_renderer.show(args, result, plaintext.print_randomize_subdomain)


def _cmd_propose(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.propose_site(description=args.description, name_hint=args.name_hint)
    return json_renderer.show(args, result, plaintext.print_propose)


def _cmd_build(args: argparse.Namespace) -> int:
    # The api verb only refuses (not over REST), so it never returns.
    # pylint: disable-next=assignment-from-no-return
    result = api.build_site(proposal=args.proposal, dry_run=args.dry_run)
    return json_renderer.show(args, result, plaintext.print_build)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("create", "Create a new site"),
        ("list", "List sites accessible to the authenticated user"),
        ("dump", "Export site data as JSON, YAML, CSV, zip, or media zip"),
        ("load", "Import/upsert content into existing site"),
        ("restore", "Import/upsert content into existing site"),
        ("copy", "Duplicate the site into a new domain"),
        (
            "configure",
            (
                "Update site configuration, theme, colors, design tokens, and/or"
                " custom CSS"
            ),
        ),
        (
            "delete",
            (
                "Not available over the REST API: it exists only as `manage.py site"
                " --delete`"
            ),
        ),
        (
            "check",
            (
                "Not available over the REST API: it exists only as `manage.py site"
                " --check`"
            ),
        ),
        (
            "review",
            (
                "Not available over the REST API: it exists only as `manage.py site"
                " --review`"
            ),
        ),
        ("select", "TODO — what `select` means"),
        ("randomize-subdomain", "Randomize the site's subdomain"),
        (
            "propose",
            (
                "Not available over the REST API: it exists only as the chat tool"
                " `propose_site_from_description`"
            ),
        ),
        (
            "build",
            (
                "Not available over the REST API: it exists only as the chat tool"
                " `build_site_from_spec`"
            ),
        ),
    ]


# One add_argument per lexicon param of each verb: the lexicon decides the length.
def parser() -> argparse.ArgumentParser:  # pylint: disable=too-many-statements
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites.site",
        description="TODO — what `site` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", help="TODO — what `name` means")
    p_create.add_argument("--user", help="TODO — what `user` means")
    p_create.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_create.add_argument("--email", help="TODO — what `email` means")
    p_create.add_argument("--phone", help="TODO — what `phone` means")
    p_create.add_argument("--theme", help="TODO — what `theme` means")
    p_create.add_argument("--plan", type=Path, help="TODO — what `plan` means")
    p_create.add_argument("--sample", help="TODO — what `sample` means")
    p_create.add_argument("--api-key", help="TODO — what `api-key` means")
    p_create.add_argument("--base-url", help="TODO — what `base-url` means")
    p_create.add_argument("--project-name", help="TODO — what `project-name` means")
    p_create.add_argument("--data", type=Path, help="TODO — what `data` means")
    p_create.set_defaults(func=_cmd_create)

    p_list = sub.add_parser("list")
    p_list.add_argument("--api-key", help="TODO — what `api-key` means")
    p_list.add_argument("--base-url", help="TODO — what `base-url` means")
    p_list.add_argument("--project-name", help="TODO — what `project-name` means")
    p_list.set_defaults(func=_cmd_list)

    p_dump = sub.add_parser("dump")
    p_dump.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_dump.add_argument("--output", type=Path, help="TODO — what `output` means")
    p_dump.add_argument(
        "--format", dest="format_", metavar="FORMAT", help="TODO — what `format` means"
    )
    p_dump.add_argument("--api-key", help="TODO — what `api-key` means")
    p_dump.add_argument("--base-url", help="TODO — what `base-url` means")
    p_dump.add_argument("--project-name", help="TODO — what `project-name` means")
    p_dump.set_defaults(func=_cmd_dump)

    p_load = sub.add_parser("load")
    p_load.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_load.add_argument("--name", help="TODO — what `name` means")
    p_load.add_argument("--user", help="TODO — what `user` means")
    p_load.add_argument("--email", help="TODO — what `email` means")
    p_load.add_argument("--api-key", help="TODO — what `api-key` means")
    p_load.add_argument("--base-url", help="TODO — what `base-url` means")
    p_load.add_argument("--project-name", help="TODO — what `project-name` means")
    p_load.add_argument("--path", type=Path, help="TODO — what `path` means")
    p_load.set_defaults(func=_cmd_load)

    p_restore = sub.add_parser("restore")
    p_restore.add_argument("--mode", help="TODO — what `mode` means")
    p_restore.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_restore.add_argument("--name", help="TODO — what `name` means")
    p_restore.add_argument("--user", help="TODO — what `user` means")
    p_restore.add_argument("--plan", type=Path, help="TODO — what `plan` means")
    p_restore.add_argument("--api-key", help="TODO — what `api-key` means")
    p_restore.add_argument("--base-url", help="TODO — what `base-url` means")
    p_restore.add_argument("--project-name", help="TODO — what `project-name` means")
    p_restore.add_argument("--path", type=Path, help="TODO — what `path` means")
    p_restore.set_defaults(func=_cmd_restore)

    p_copy = sub.add_parser("copy")
    p_copy.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_copy.add_argument("--to", required=True, help="TODO — what `to` means")
    p_copy.add_argument("--user", help="TODO — what `user` means")
    p_copy.add_argument("--name", help="TODO — what `name` means")
    p_copy.add_argument("--plan", type=Path, help="TODO — what `plan` means")
    p_copy.add_argument("--api-key", help="TODO — what `api-key` means")
    p_copy.add_argument("--base-url", help="TODO — what `base-url` means")
    p_copy.add_argument("--project-name", help="TODO — what `project-name` means")
    p_copy.set_defaults(func=_cmd_copy)

    p_configure = sub.add_parser("configure")
    p_configure.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_configure.add_argument("--title", help="TODO — what `title` means")
    p_configure.add_argument("--subtitle", help="TODO — what `subtitle` means")
    p_configure.add_argument(
        "--copyright",
        dest="copyright_",
        metavar="COPYRIGHT",
        help="TODO — what `copyright` means",
    )
    p_configure.add_argument("--theme", help="TODO — what `theme` means")
    p_configure.add_argument(
        "--colors-primary", help="TODO — what `colors-primary` means"
    )
    p_configure.add_argument(
        "--colors-secondary", help="TODO — what `colors-secondary` means"
    )
    p_configure.add_argument(
        "--colors-accent", help="TODO — what `colors-accent` means"
    )
    p_configure.add_argument("--colors-body", help="TODO — what `colors-body` means")
    p_configure.add_argument("--api-key", help="TODO — what `api-key` means")
    p_configure.add_argument("--base-url", help="TODO — what `base-url` means")
    p_configure.add_argument("--project-name", help="TODO — what `project-name` means")
    p_configure.add_argument("--path", type=Path, help="TODO — what `path` means")
    p_configure.set_defaults(func=_cmd_configure)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_delete.set_defaults(func=_cmd_delete)

    p_check = sub.add_parser("check")
    p_check.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_check.set_defaults(func=_cmd_check)

    p_review = sub.add_parser("review")
    p_review.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_review.set_defaults(func=_cmd_review)

    p_select = sub.add_parser("select")
    p_select.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_select.add_argument("--project-name", help="TODO — what `project-name` means")
    p_select.add_argument("--api-key", help="TODO — what `api-key` means")
    p_select.add_argument("--base-url", help="TODO — what `base-url` means")
    p_select.set_defaults(func=_cmd_select)

    p_randomize_subdomain = sub.add_parser("randomize-subdomain")
    p_randomize_subdomain.add_argument(
        "--domain", help="Site domain (canonical Site.domain; no alias mechanism)"
    )
    p_randomize_subdomain.add_argument("--api-key", help="TODO — what `api-key` means")
    p_randomize_subdomain.add_argument(
        "--base-url", help="TODO — what `base-url` means"
    )
    p_randomize_subdomain.add_argument(
        "--project-name", help="TODO — what `project-name` means"
    )
    p_randomize_subdomain.set_defaults(func=_cmd_randomize_subdomain)

    p_propose = sub.add_parser("propose")
    p_propose.add_argument("--description", help="TODO — what `description` means")
    p_propose.add_argument("--name-hint", help="TODO — what `name-hint` means")
    p_propose.set_defaults(func=_cmd_propose)

    p_build = sub.add_parser("build")
    p_build.add_argument("--proposal", help="TODO — what `proposal` means")
    p_build.set_defaults(func=_cmd_build)

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
