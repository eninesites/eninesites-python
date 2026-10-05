"""Grade the CLI tree against `surface.jsonl` — the WHAT, not the HOW.

`arch-python/SURFACES.md` §19 gives a governed package one spec file, one row per
capability, carrying that capability's `cli`, `web`, `rest` and `mcp` bindings side by
side. This checker is what makes that file a source rather than a description.

The pairing to hold in mind:

    check_cli_commands   the HOW — every node has `__main__.py` + `commands()`, the
                         listing matches, the parser is built but not run at import
    check_surface        the WHAT — the verbs that exist are the verbs that were
                         specified, and the specified ones exist

Neither substitutes for the other. A tree can satisfy every structural rule in §3 and
still offer a verb nobody designed, or be missing one that was. Conversely a tree can
match its spec exactly and still build the parser at import time. The two failures have
nothing to do with each other, which is why they are two checkers.

## The columns the server's rails read

The checker also grades the columns the generated server's two rails read: a `kind` outside
`read | write | job`, a `rest` method missing or outside `GET | POST | DELETE`, a `GET` on
a write, a `DELETE` on a read, an exposed row with no `scope`, and a write whose scope tier
is not `write` or `admin`. `racecar.package`'s generator imports those rules from here.

## Closure runs in both directions

A spec that only required every declared verb to exist would let the tree grow verbs
nobody declared. One that only required every verb to be declared would let the spec keep
rows for verbs long deleted. §17 is blunt about the half-measure:

    a spec without closure in both directions is strictly worse than the derivation
    racecar already has: it adds a place to lie and removes nothing.

## The spec is the source; the tree is what changes

When the two disagree, this checker reports the TREE as wrong. That direction is not
politeness. A spec its implementer may edit to match what they built is not a spec, it is
a transcript, and it cannot fail.

## Applicability

Repos with no `surface.jsonl` are skipped, not failed. Declaring a surface spec is a
choice a package makes; §19 does not require one, and a checker that failed every repo
without one would be enforcing a rule nobody wrote.

Usage:
    python scripts/check_surface.py                 # discover src/<pkg>
    python scripts/check_surface.py --root <path>   # grade another repo
    python scripts/check_surface.py --json

Exit 0 when the spec and the tree agree (or no spec exists), 1 on any divergence,
2 on a usage error.

Complexity: O(n + m), n = surface.jsonl rows, m = CLI tree nodes walked
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lib.shared import _spec
from lib.shared._root import package_root

# The walker runs in a SUBPROCESS with the target's `src` on sys.path. Importing an
# arbitrary repo's package into this process would run its module-scope code inside the
# checker, and a repo whose `__main__.py` does work at import (itself a §3 violation)
# would take the checker down with it instead of being reported.
#
# A LEAF THAT DECLARES NO `subcommands()` IS A VERB LEAF, AND ITS OWN BARE PATH IS THE
# INVOCATION. `CLI.md` §"Noun or verb" does not merely permit that shape, it mandates it —
# "a verb leaf cannot take a subparser", so "needing a subparser therefore forces a noun
# leaf" — and §`subcommands()` says a pure flag-based leaf "declare[s] nothing". Emitting
# only `subcommands()` rows would therefore make the one shape the CLI rules require
# unrepresentable: declare its real path and closure would report it as not existing.
# The discriminator is the FUNCTION's absence, which is the same fact CLI.md states, not
# an empty return from a node that owns subparsers.
_WALKER = r"""
import importlib, json, sys
pkg = sys.stdin.read()
found = []
queue = [(pkg, importlib.import_module(pkg + ".__main__"))]
while queue:
    path, node = queue.pop()
    for verb, _ in node.subcommands() if hasattr(node, "subcommands") else []:
        found.append("python -m %s %s" % (path, verb))
    children = list(node.commands()) if hasattr(node, "commands") else []
    if not hasattr(node, "subcommands") and not children:
        found.append("python -m %s" % path)
    for name, _ in children:
        child = path + "." + name
        queue.append((child, importlib.import_module(child + ".__main__")))
print(json.dumps(sorted(found)))
"""

# `absent` and `broken` are kept apart deliberately. A bare `except Exception: False`
# reads an ImportError inside a module that plainly exists as "not built yet", so a row
# marked `proposed` whose implementation is present but crashing on import is reported as
# conforming. That is the checker agreeing with the spec about a module neither of them
# could load.
_RESOLVER = r"""
import importlib, inspect, json, sys
out = {}
for fn in json.loads(sys.stdin.read()):
    module_name, _, attr = fn.rpartition(".")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        absent = missing == module_name or module_name.startswith(missing + ".")
        out[fn] = {"state": "absent" if absent else "broken:%s" % exc}
    except Exception as exc:
        out[fn] = {"state": "broken:%s: %s" % (type(exc).__name__, exc)}
    else:
        # `fn` may name a MODULE (`pkg.api.package.commit`) rather than a callable on
        # one. `hasattr(parent, "commit")` is False for an unimported submodule and True
        # once anything imports it, so testing only the attribute makes the answer depend
        # on what ran first. Import the full path as a fallback and the answer is stable.
        if hasattr(module, attr):
            target = getattr(module, attr)
            try:
                # The api's SIGNATURE is what a surface binds, so it is the answer the spec's
                # `params` column is checked against. Read in the probe, not here: it is the
                # process that already imported the module, and the checker does not import
                # an arbitrary repo's code into itself.
                names = list(inspect.signature(target).parameters)
            except (TypeError, ValueError):
                names = None  # a module rather than a callable, or an unreadable signature
            out[fn] = {"state": "present", "params": names}
        else:
            try:
                importlib.import_module(fn)
            except ModuleNotFoundError:
                out[fn] = {"state": "absent"}
            except Exception as exc:
                out[fn] = {"state": "broken:%s: %s" % (type(exc).__name__, exc)}
            else:
                # A MODULE, not a callable: it has no signature to compare a row against.
                out[fn] = {"state": "present", "params": None}
print(json.dumps(out))
"""


def _params_finding(
    rel: str,
    row: dict[str, object],
    fn: str,
    signature: list[str] | None,
    status: object,
) -> list[str]:
    """Whether the row's `params` is the bound `fn`'s signature, as a finding or nothing.

    **A surface is one projection of the api**, so `params` is the api callable's parameter
    list — not the flags one projection happens to spell for them. The CLI's flags are that
    projection's own declaration and live on the verb's node under `docs/lexicon/`; a REST or
    MCP face binds these names. Two columns called `params` meaning different things
    would let rows drift with every gate green.

    Silent where there is nothing to compare: `fn` may name a module rather than a callable,
    and a `proposed` row has no implementation to read a signature from.
    """
    if signature is None or status == "proposed":
        return []
    listed = row.get("params")
    declared = set(listed) if isinstance(listed, list) else set()
    actual = set(signature)
    if declared == actual:
        return []
    missing = ", ".join(f"`{p}`" for p in sorted(actual - declared))
    extra = ", ".join(f"`{p}`" for p in sorted(declared - actual))
    detail = "; ".join(
        part
        for part in (
            (
                f"{fn} takes {missing} and the row does not declare them"
                if missing
                else ""
            ),
            (
                f"the row declares {extra} and {fn} takes no such parameter"
                if extra
                else ""
            ),
        )
        if part
    )
    return [
        f"{rel}: `{row['id']}`'s `params` is not `{fn}`'s signature — {detail}. "
        "A surface is one projection of the api, so this column is the api's parameters; "
        "a flag spelling belongs to the projection that spells it."
    ]


# THE WRITE RAIL'S RULES, IN ONE HOME. The generated server refuses a write unless writes
# are switched on, and refuses a call whose token lacks the row's scope, so both rails read
# `kind` and `scope`. `racecar.package`'s generator imports these three functions rather
# than restating them, so the generator and this checker cannot refuse different pairs.
KINDS = ("read", "write", "job")
METHODS = ("GET", "POST", "DELETE")
_WRITE_TIERS = ("write", "admin")


def kind_findings(ident: str, kind: object) -> list[str]:
    """A `kind` outside `read | write | job`, as a finding; the write rail has nothing to read."""
    if kind in KINDS:
        return []
    return [f"`{ident}` has kind {kind!r}; a kind is one of {', '.join(KINDS)}"]


def method_findings(ident: str, kind: object, method: object) -> list[str]:
    """A method that is missing, unknown, or contradicts HTTP for this `kind`.

    `POST` with `read` is allowed: a read whose input is too large for a query string is
    still a read. `GET` with a write is not, because a GET is safe by definition (RFC 9110
    §9.2.1) and would be served with the write rail off. `DELETE` with a read is the mirror.
    """
    if method not in METHODS:
        return [
            f"`{ident}` has method {method!r}; a method is declared, never defaulted, "
            f"and is one of {', '.join(METHODS)}"
        ]
    if method == "GET" and kind in ("write", "job"):
        return [
            f"`{ident}` is a {kind} bound to GET; a GET is safe by definition, so the "
            "server would serve it with the write rail off"
        ]
    if method == "DELETE" and kind == "read":
        return [f"`{ident}` is a read bound to DELETE"]
    return []


def scope_findings(ident: str, kind: object, scope: object) -> list[str]:
    """A missing scope, or a write or job whose scope tier is not `write` or `admin`.

    This checks that scope and kind agree without deriving one from the other: the tier is
    the last `:` segment of `<repo>:<vertical>:<tier>` (AUTH.md), read, never computed.
    """
    if not scope:
        return [f"`{ident}` has no scope; a scope is declared, never derived"]
    tier = str(scope).rsplit(":", 1)[-1]
    if kind in ("write", "job") and tier not in _WRITE_TIERS:
        return [
            f"`{ident}` is a {kind} with scope `{scope}`; a {kind} needs a "
            f"{' or '.join(_WRITE_TIERS)} tier"
        ]
    return []


def rail_findings(row: dict[str, object]) -> list[str]:
    """The write-rail rules over one spec row: its kind, each `rest` method, its scope.

    A scope is required once the row is exposed (`rest` or `mcp` populated, §19), and a
    scope that is declared is graded against the kind whether or not it is exposed yet.
    """
    ident, kind = str(row["id"]), row.get("kind")
    rest = row.get("rest") or []
    if kind is None and not (rest or row.get("mcp")):
        # A null field is not yet known, not wrong: `lexicon create` writes the row with
        # what the lexicon knows, and the kind arrives with the face that serves it.
        return []
    found = kind_findings(ident, kind)
    for entry in rest if isinstance(rest, list) else []:
        method = entry.get("method") if isinstance(entry, dict) else None
        found += method_findings(ident, kind, method)
    if rest or row.get("mcp") or row.get("scope") is not None:
        found += scope_findings(ident, kind, row.get("scope"))
    return found


def _run(script: str, arg: str, root: Path) -> object:
    """Run one of the probe scripts against the target repo; return its parsed output.

    `arg` travels over the child's STDIN, not as an argv element. `_RESOLVER`'s `arg` is
    a JSON array of every row's `fn`, one entry per spec row, and argv has a ceiling
    `stdin` does not: the OS's `ARG_MAX` (`getconf ARG_MAX`, typically a few MB). A spec
    large enough to approach it would raise an unhandled `OSError` from `subprocess.run`
    itself, before this function's own `except subprocess.TimeoutExpired` or
    `proc.returncode != 0` handling ran -- the same reason `xargs` exists: move the
    payload off the command line and onto a stream a process reads instead of receives
    as an argument.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            input=arg,
            capture_output=True,
            text=True,
            cwd=str(root),
            env=_env(),
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(
            "check_surface: a target module's import hung the probe past 120s "
            f"({exc})"
        ) from exc
    if proc.returncode != 0:
        raise SystemExit(
            f"check_surface: could not walk the CLI tree — {proc.stderr.strip()[:400]}"
        )
    return json.loads(proc.stdout)


def _env() -> dict[str, str]:
    """The parent environment, imported here so the module top stays free of `os`."""
    import os  # pylint: disable=import-outside-toplevel

    return dict(os.environ)


# DFS colours for the `requires` cycle walk. GREY is "on the current path", which is what
# distinguishes a cycle from a diamond: a node reached twice by different paths is BLACK
# the second time and is ordinary composition, not a loop.
_WHITE, _GREY, _BLACK = 0, 1, 2


def requires_findings(rows: list[dict[str, object]], rel: object) -> list[str]:
    """Gate the `requires` graph: totality, then acyclicity.

    `requires` is the one column whose values are primary keys of this same table
    (SURFACES.md §19), so the rows form a directed graph. Nothing else in the repo watches
    it: import-linter's contracts see IMPORT edges, and a prerequisite is a runtime
    ordering that need involve no import at all.

    Three states, and they are not the same. An ABSENT key means no prerequisites and is
    silent — a spec that omits the column is a legitimate absence (§4: gate
    what has no legitimate instance, weigh the rest). An explicit `[]` means the same
    thing, declared. `null` is REFUSED rather than coerced to either: an unknown edge set
    is not something acyclicity can be decided over, so treating it as empty would be
    guessing, and guessing is what a spec exists to stop.

    Cycles are reported once each, by the row that closes them, rather than once per
    member — a three-row cycle is one fact, and naming it three times reads as three
    problems.
    """
    findings: list[str] = []
    ids = {str(r["id"]) for r in rows}
    edges: dict[str, list[str]] = {}
    for row in rows:
        rid = str(row["id"])
        if "requires" not in row:
            edges[rid] = []
            continue
        value = row["requires"]
        if value is None:
            findings.append(
                f"{rel}: `{rid}` has `requires: null`. Omit the key, or write `[]` — "
                "an unknown edge set is not something acyclicity can be decided over."
            )
            edges[rid] = []
            continue
        if not isinstance(value, list):
            findings.append(f"{rel}: `{rid}` has a non-list `requires`")
            edges[rid] = []
            continue
        targets = [str(v) for v in value]
        for target in targets:
            if target not in ids:
                findings.append(
                    f"{rel}: `{rid}` requires `{target}`, which no row declares. A "
                    "prerequisite naming nothing is a runner that cannot proceed and "
                    "cannot say why."
                )
        edges[rid] = [t for t in targets if t in ids]

    # Iterative DFS with an explicit stack: the same shape check_doc_graph uses, and for
    # the same reason -- a deep chain must not become a RecursionError.
    colour = dict.fromkeys(edges, _WHITE)
    for start in sorted(edges):
        if colour[start] != _WHITE:
            continue
        stack: list[tuple[str, list[str]]] = [(start, list(edges[start]))]
        colour[start] = _GREY
        path = [start]
        while stack:
            node, remaining = stack[-1]
            if not remaining:
                colour[node] = _BLACK
                stack.pop()
                path.pop()
                continue
            nxt = remaining.pop(0)
            if colour.get(nxt) == _GREY:
                loop = path[path.index(nxt) :] + [nxt]
                findings.append(
                    f"{rel}: `requires` cycle: {' -> '.join(loop)}. A prerequisite graph "
                    "with a cycle is a runner that never terminates."
                )
                continue
            if colour.get(nxt) == _BLACK:
                continue
            colour[nxt] = _GREY
            path.append(nxt)
            stack.append((nxt, list(edges[nxt])))
    return findings


def audit(root: Path) -> tuple[list[str], int, list[str]]:
    """Return `(findings, rows graded, notes)`; no findings means the tree conforms.

    `notes` are the informational lines -- no spec to grade, verbs declared and not yet
    built -- which are not findings. They are returned rather than printed so `main` decides
    where they go: stdout beside the findings, or stderr under `--json`, where stdout is
    exactly one JSON document and a line of prose ahead of it would make it unparseable.

    The two passes below (`declared - built - proposed`, then `built - declared`) are
    plain two-way set difference reconciling desired state (the spec) against actual
    state (the probed tree) — the same shape as a Kubernetes controller's reconcile
    loop, with `proposed` carved out as the one sanctioned lag between the two.
    """
    located = _spec.find_spec(root)
    if located is None:
        return [], 0, ["no surface.jsonl — nothing to grade (info)"]
    spec, pkg = located
    if pkg is None:
        return (
            [],
            0,
            [
                f"{spec}: no package under src/ to walk, so its cli column is ungraded (info)"
            ],
        )
    try:
        rows = _spec.read_rows(spec)
    except _spec.SpecError as exc:
        raise SystemExit(f"check_surface: {exc}") from exc
    rel = spec.relative_to(root)
    # A library with no command line has no `__main__.py`, so there is no tree to walk:
    # importing `<pkg>.__main__` would only raise. Nothing is built, and the comparison
    # below still names any row that claims a command exists.
    has_cli = (package_root(root) / pkg / "__main__.py").is_file()
    walked: list[str] = (
        _run(_WALKER, pkg, root) if has_cli else []  # type: ignore[assignment]
    )
    built = set(walked)
    # `cli` is `str | null` and NOT required (§19), so a row binding no command line is
    # skipped rather than required or stringified. `str(r["cli"])` would raise
    # `KeyError` on an omitted key and turn a `null` into the string `"None"`, which
    # would then fail closure and reach a reader as a finding about a verb named `None`.
    # A traceback is not a stricter finding, it is the absence of one: nothing
    # observable separates "checked and allowed" from "could not check".
    declared = {str(r["cli"]) for r in rows if r.get("cli")}
    # A row's `status` decides whether "declared and not built" is a finding at all.
    proposed = {
        str(r["cli"]) for r in rows if r.get("cli") and r.get("status") == "proposed"
    }
    findings = []
    notes = []

    # A SPEC AHEAD OF ITS IMPLEMENTATION IS NOT A DEFECT. `proposed` is the state of
    # having decided what to build and not yet built it, which is strictly better than
    # not having decided — you know the name of what is missing. Failing on it would make
    # a repo that wrote a spec score worse than one that wrote none, and the way to a
    # green gate would be to delete the plan. Only a row claiming to be built, and not
    # being, is a divergence.
    for verb in sorted(declared - built - proposed):
        findings.append(
            f"{rel}: `{verb}` is declared `exists` and does not. BUILD IT — the spec is "
            "the source; removing the row is not the available fix. (A verb genuinely "
            "not built yet belongs in the spec as `proposed`, which is not a finding.)"
        )
    pending = sorted(proposed - built)
    if pending:
        notes.append(
            f"{len(pending)} verb(s) declared and not yet built "
            f"(info, not a finding): {', '.join(pending)}"
        )
    # The mirror of the `fn` axis's stale-`proposed` check below: a verb genuinely
    # built and callable, whose spec row still says `proposed`, is a finding on the
    # `cli` axis too -- the same reconcile-loop shape, just the other resolver.
    for verb in sorted(proposed & built):
        findings.append(
            f"{rel}: `{verb}` is marked `proposed` and now exists — the row needs its "
            "status flipped"
        )
    for verb in sorted(built - declared):
        findings.append(
            f"{rel}: `{verb}` exists and is not declared. Either remove the verb, or have "
            "the spec's owner declare it. Widening the spec to match is the same drift "
            "with the evidence erased."
        )

    findings.extend(requires_findings(rows, rel))
    findings.extend(f"{rel}: {f}" for row in rows for f in rail_findings(row))

    # A row with no `fn` names no callable yet, so there is nothing to resolve: `null` is
    # the value a row has between `lexicon create` and the face that builds it.
    named = [r for r in rows if r.get("fn")]
    resolved = (
        _run(_RESOLVER, json.dumps([str(r["fn"]) for r in named]), root)
        if named
        else {}
    )
    for row in named:
        fn, status = str(row["fn"]), row.get("status")
        answer = resolved[fn]  # type: ignore[index]
        state = str(answer["state"])
        if state.startswith("broken:"):
            findings.append(
                f"{rel}: `{fn}` exists and raised on import — {state[len('broken:'):]}. "
                "Neither `exists` nor `proposed` is true of a module that cannot load."
            )
        elif status == "proposed" and state == "present":
            findings.append(
                f"{rel}: `{fn}` is marked `proposed` and now exists — the row needs its "
                "status flipped"
            )
        elif status != "proposed" and state == "absent":
            findings.append(f"{rel}: `{fn}` is marked `{status}` and does not resolve")

        findings += _params_finding(str(rel), row, fn, answer.get("params"), status)

    return findings, len(rows), notes


def main(argv: list[str] | None = None) -> int:
    """Parse argv, audit the repo, and return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path("."), help="Repo to grade (default: CWD)"
    )
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON")
    args = parser.parse_args(argv)

    findings, graded, notes = audit(args.root.resolve())
    for note in notes:
        print(f"check_surface: {note}", file=sys.stderr if args.json else sys.stdout)
    if args.json:
        print(json.dumps({"findings": findings, "rows": graded}, indent=2))
    else:
        for f in findings:
            print(f"check_surface: {f}")
        if graded:
            print(f"check_surface: {len(findings)} finding(s) over {graded} row(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
