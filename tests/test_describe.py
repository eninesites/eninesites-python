"""``python -m eninesites describe``: every command as data, read from the cli, never restated."""

from __future__ import annotations

import json
from collections.abc import Callable

from test_cli import VERBS

import eninesites.__main__ as root
from eninesites.errors import ErrorResult
from eninesites.lib import dryrun
from eninesites.root.api import describe_root
from eninesites.root.lib.results import DescribeRoot
from eninesites.schema import conforms, json_schema

Run = Callable[..., tuple[int, str, str]]


def by_command() -> dict[str, dict[str, object]]:
    return {c["command"]: dict(c) for c in describe_root()["commands"]}


def test_every_verb_of_every_node_is_described() -> None:
    root_verbs = {f"python -m eninesites {v}" for v in dict(root.subcommands())}
    noun_verbs = {verb.prog for _, verb in VERBS}
    assert set(by_command()) == root_verbs | noun_verbs


def test_each_output_is_its_node_output() -> None:
    commands = by_command()
    for node, verb in VERBS:
        name = verb.prog.rsplit(" ", 1)[1]
        published = dict((p["phase"], s) for p, s in node.output())[name]
        assert json.loads(str(commands[verb.prog]["output"])) == published, verb.prog


def test_each_command_lists_its_flags_and_whether_it_writes() -> None:
    commands = by_command()
    for node, verb in VERBS:
        row = commands[verb.prog]
        flags = {f for arg in row["args"] for f in arg["flags"]}  # type: ignore[attr-defined]
        assert flags == {
            f
            for a in verb._actions
            for f in a.option_strings
            if f not in ("-h", "--help")
        }, verb.prog
        name = verb.prog.rsplit(" ", 1)[1]
        assert row["writes"] is dryrun.is_write(node.api.VERBS[name])
        assert ("--dry-run" in flags) is row["writes"]


def test_describe_conforms_and_carries_the_shared_shapes(run_cli: Run) -> None:
    code, out, err = run_cli(root.main, ["describe", "--json"])
    result = json.loads(out)
    assert (code, err) == (0, "")
    assert conforms(result, DescribeRoot) == []
    assert json.loads(result["error"]) == json_schema(ErrorResult)
    assert json.loads(result["planned"]) == json_schema(dryrun.PlannedRequest)
    assert sum(c["writes"] for c in result["commands"]) == 51
