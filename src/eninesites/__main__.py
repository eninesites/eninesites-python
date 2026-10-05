"""CLI entry: python -m eninesites

TODO — what `eninesites` means

The package's own command line: it lists the nouns this package composes in ``commands()``
and runs the verbs declared on the package itself. Their code is ``eninesites.root``, so a root
verb is addressed like any other noun's, from ``api`` to its renderer.

A thin surface over ``api``: each verb is one ``_cmd_<verb>`` that calls one api function
and hands its result to a renderer. It decides nothing and prints nothing itself. Every
verb takes ``--json``: the api result as JSON, the shape ``output()`` publishes, instead of
the text view. ``main()`` is ``lib.cli.run``: an ``ApiError`` the api raises is printed on
stderr and its ``exit_code`` returned.
"""

from __future__ import annotations

import argparse

from eninesites.errors import ApiError
from eninesites.lib.cli import NounParser, print_commands, run
from eninesites.lib.client import prompt
from eninesites.lib.renderer import json as json_renderer
from eninesites.root import api
from eninesites.root.lib.renderer import plaintext
from eninesites.schema import returns


def commands() -> list[tuple[str, str]]:
    """This node's sub-nouns, as (name, summary); its verbs are declared in subcommands()."""
    return [
        ("site", "TODO — what `site` means"),
        ("theme", "TODO — what `theme` means"),
        ("artifact", "TODO — what `artifact` means"),
        ("tag", "TODO — what `tag` means"),
        ("url", "External URL catalog — the external sibling of Media"),
        ("urlmap", "Custom URL mappings for artifacts"),
        ("media", "Media upload and management"),
        ("user", "Site user management"),
        ("audit", "TODO — what `audit` means"),
        ("aeo", "TODO — what `aeo` means"),
        ("page", "TODO — what `page` means"),
        ("chat", "TODO — what `chat` means"),
        ("seo", "SEO page management"),
    ]


def _print_commands() -> None:
    """This node's listing: its sub-nouns, then its verbs. The body is lib/cli.py's."""
    print_commands(__package__ or "eninesites", commands(), subcommands())


def _cmd_login(args: argparse.Namespace) -> int:
    # The key is asked for (hidden) or read from stdin when --api-key is absent: reading
    # the person's input is the surface's job, so the api takes the key as a value.
    result = api.login_root(
        api_key=args.api_key or prompt.read_api_key(),
        base_url=args.base_url,
        project_name=args.project_name,
    )
    return json_renderer.show(args, result, plaintext.print_login)


def _cmd_logout(args: argparse.Namespace) -> int:
    result = api.logout_root(project_name=args.project_name, all_=args.all_)
    return json_renderer.show(args, result, plaintext.print_logout)


def _cmd_config(args: argparse.Namespace) -> int:
    result = api.config_root(
        api_key=args.api_key, base_url=args.base_url, project_name=args.project_name
    )
    return json_renderer.show(args, result, plaintext.print_config)


def subcommands() -> list[tuple[str, str]]:
    """One (verb, summary) per verb: the one home of each verb's help text."""
    return [
        ("login", "TODO — what `login` means"),
        ("logout", "TODO — what `logout` means"),
        ("config", "TODO — what `config` means"),
    ]


def parser() -> argparse.ArgumentParser:
    """Build the parser without parsing: the audit and --help both read this."""
    p = NounParser(
        prog="python -m eninesites",
        description="TODO — what `eninesites` means",
        nodes=commands(),
    )
    sub = p.verbs(subcommands(), dest="phase")

    p_login = sub.add_parser("login")
    p_login.add_argument("--api-key", help="TODO — what `api-key` means")
    p_login.add_argument("--base-url", help="TODO — what `base-url` means")
    p_login.add_argument("--project-name", help="TODO — what `project-name` means")
    p_login.set_defaults(func=_cmd_login)

    p_logout = sub.add_parser("logout")
    p_logout.add_argument("--project-name", help="TODO — what `project-name` means")
    p_logout.add_argument(
        "--all", dest="all_", action="store_true", help="TODO — what `all` means"
    )
    p_logout.set_defaults(func=_cmd_logout)

    p_config = sub.add_parser("config")
    p_config.add_argument("--api-key", help="TODO — what `api-key` means")
    p_config.add_argument("--base-url", help="TODO — what `base-url` means")
    p_config.add_argument("--project-name", help="TODO — what `project-name` means")
    p_config.set_defaults(func=_cmd_config)

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
