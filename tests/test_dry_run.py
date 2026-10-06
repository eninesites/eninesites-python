"""``--dry-run`` on every write verb: the request it would send, returned and not sent.

Generic over ``surface.jsonl``: every row of ``"kind": "write"`` is run twice against the fake
server, once with ``--dry-run`` (no request but a GET may go out, and the result is the
planned request) and once for real (at most one request that is not a GET, which is what
makes the one request a dry run records the whole of what the verb would change).
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import FakeServer
from test_cli import _needed, _verbs

import eninesites.__main__ as root
import eninesites.site.__main__ as site
from eninesites.lib import dryrun
from eninesites.lib.client import config
from eninesites.schema import conforms

Run = Callable[..., tuple[int, str, str]]

ROWS = [
    json.loads(line)
    for line in (Path(__file__).resolve().parents[1] / "surface.jsonl")
    .read_text()
    .splitlines()
    if line.strip()
]
WRITES = [row for row in ROWS if row["kind"] == "write"]

#: What a write verb needs beyond its required flags to reach its request, from the
#: sample files every test finds in its working directory (``conftest.SAMPLE_FILES``).
INPUT: dict[str, list[str]] = {
    "root.login": ["--api-key", "k" * 40],
    "site.load": ["--path", "site.json"],
    "site.restore": ["--path", "site.zip"],
    "site.configure": ["--theme", "bauhaus"],
    "site.select": ["--domain", "example.com"],
    "theme.custom.import": ["--name", "mine", "--path", "theme.json"],
    "artifact.create": ["--name", "about"],
    "artifact.update": ["--title", "About"],
    "artifact.design.update": ["--data", "design.json"],
    "artifact.aeo.create": ["--data", "aeo.json"],
    "artifact.aeo.update": ["--data", "aeo.json"],
    "artifact.map.create": ["--data", "map.json"],
    "artifact.map.update": ["--data", "order.json"],
    "artifact.image.attach": ["--media", "1"],
    "tag.create": ["--name", "docs"],
    "tag.update": ["--name", "manuals"],
    "url.create": ["--data", "url.json"],
    "url.update": ["--data", "label.json"],
    "urlmap.create": ["--data", "urlmap.json"],
    "urlmap.update": ["--data", "canonical.json"],
    "media.upload": ["--files", "logo.png"],
    "media.update": ["--data", "filename.json"],
    "seo.create": ["--data", "seopage.json"],
    "seo.update": ["--data", "seotitle.json"],
}
#: Write verbs that, against the fake server's empty answers, have nothing to change: the
#: verb returns its ordinary result, dry run or not. Each is tested on its own below.
NOTHING_TO_CHANGE = {
    "artifact.role.unassign": "the role is not assigned, so nothing is sent",
    "root.logout": "no key is stored, so nothing is removed",
}


def command(row: dict[str, Any]) -> tuple[ModuleType, list[str]]:
    """The row's node and an argv that reaches its request."""
    module, verb = str(row["cli"]).removeprefix("python -m ").rsplit(" ", 1)
    node = importlib.import_module(f"{module}.__main__")
    needed = _needed(_verbs(node)[verb])
    given = INPUT.get(row["id"], [])
    for flag in given[
        ::2
    ]:  # a flag INPUT names replaces the made-up value _needed gave it
        if flag in needed:
            del needed[needed.index(flag) : needed.index(flag) + 2]
    return node, [verb, *needed, *given]


def not_available(node: ModuleType, verb: str) -> bool:
    """Whether the noun's api declares the verb has no REST endpoint."""
    return verb in getattr(node.api, "NOT_OVER_REST", ())


def test_the_marked_verbs_are_the_write_rows() -> None:
    """``dryrun.writes`` and ``surface.jsonl`` name the same 51 verbs: one cannot drift."""
    marked = set()
    for row in ROWS:
        node, argv = command(row)
        if dryrun.is_write(node.api.VERBS[argv[0]]):
            marked.add(row["id"])
    assert marked == {row["id"] for row in WRITES}
    assert len(marked) == 51


@pytest.mark.parametrize("row", WRITES, ids=[row["id"] for row in WRITES])
def test_a_dry_run_sends_no_write(
    row: dict[str, Any], server: FakeServer, run_cli: Run
) -> None:
    node, argv = command(row)
    code, out, err = run_cli(node.main, [*argv, "--dry-run", "--json"])
    assert [c.method for c in server.calls if c.method != "GET"] == []
    if not_available(node, argv[0]):
        assert (code, json.loads(err)["code"]) == (2, "not_available")
        return
    assert (code, err) == (0, ""), err
    result = json.loads(out)
    if row["id"] in NOTHING_TO_CHANGE:
        assert not dryrun.is_planned(result)
        return
    assert conforms(result, dryrun.PlannedRequest) == [], result
    assert result["method"] in ("POST", "PUT", "PATCH", "DELETE", "WRITE", "REMOVE")


@pytest.mark.parametrize("row", WRITES, ids=[row["id"] for row in WRITES])
def test_a_write_verb_sends_at_most_one_write(
    row: dict[str, Any], server: FakeServer, run_cli: Run
) -> None:
    """The premise of ``--dry-run``: one recorded request is all a verb would change."""
    node, argv = command(row)
    run_cli(node.main, [*argv, "--json"])
    assert len([c for c in server.calls if c.method != "GET"]) <= 1


def test_a_dry_run_prints_the_request_as_text(run_cli: Run) -> None:
    node, argv = command(next(r for r in WRITES if r["id"] == "artifact.create"))
    code, out, _ = run_cli(node.main, [*argv, "--dry-run"])
    assert code == 0
    assert out.startswith("would send: POST /api/v1/site/example.com/artifacts/\n")
    assert out.rstrip().endswith("Dry run: nothing was sent or written.")


def test_select_under_dry_run_saves_nothing(run_cli: Run) -> None:
    code, out, _ = run_cli(
        site.main, ["select", "--domain", "example.com", "--dry-run", "--json"]
    )
    assert code == 0
    assert json.loads(out)["method"] == "WRITE"
    assert not config.config_path().exists()


def test_login_under_dry_run_stores_no_key(server: FakeServer, run_cli: Run) -> None:
    code, out, _ = run_cli(
        root.main, ["login", "--api-key", "k" * 40, "--dry-run", "--json"]
    )
    planned = json.loads(out)
    assert code == 0
    assert [c.method for c in server.calls] == ["GET"]
    assert planned["method"] == "WRITE"
    assert "k" * 40 not in out  # the key is shown redacted, never whole
    assert not config.config_path().exists()


def test_logout_under_dry_run_removes_nothing(run_cli: Run) -> None:
    config.update_profile("default", api_key="k" * 40)
    before = config.config_path().read_text()
    code, out, _ = run_cli(root.main, ["logout", "--dry-run", "--json"])
    assert code == 0
    assert json.loads(out)["method"] == "REMOVE"
    assert config.config_path().read_text() == before


def test_unassign_under_dry_run_plans_the_put(server: FakeServer, run_cli: Run) -> None:
    node = importlib.import_module("eninesites.artifact.role.__main__")
    argv = ["unassign", *_needed(_verbs(node)["unassign"])]
    code_index = argv.index("--role") + 1 if "--role" in argv else None
    run_cli(node.main, [*argv, "--json"])  # learn the path the verb reads
    path = server.calls[0].path
    server.calls.clear()
    role = argv[code_index] if code_index else "x"
    server.add("GET", path, {"roles": [role]})
    code, out, err = run_cli(node.main, [*argv, "--dry-run", "--json"])
    assert (code, err) == (0, ""), err
    assert json.loads(out)["method"] == "PUT"
    assert [c.method for c in server.calls] == ["GET"]


def test_done_passes_a_result_and_refuses_a_plan() -> None:
    planned = dryrun.Planned("DELETE", "/api/v1/x/").record()
    with pytest.raises(TypeError, match="planned request"):
        dryrun.done(planned)
    assert dryrun.done({"domain": "example.com"}) == {"domain": "example.com"}
