"""Gate a graph: the superset of `racecar.graph.topology check` (shape — containment,
acyclicity) and `racecar.graph.ontology check` (types — declared kinds, required
fields, and every OTHER declared relation's actual usage — `ONTOLOGY.md` §"Relations
are declared, not just containment"). Reachable on its own as `racecar.graph check`
because most callers want all three questions answered at once; each half stays
independently reachable because a graph's shape can be well-formed while its types
are not, and the reverse.

Part of `lib.graph`; `scripts/graph.py` parses the command line and calls `main`. `run` is
the gate and returns its record; `renderer.text` is how the record reads.

Exit: 0 clean, 1 any error from any part.

Complexity: O(N) in corpus nodes -- one containment walk plus one ontology pass.
"""

from __future__ import annotations

import pathlib
import re
import sys
from pathlib import Path
from typing import Any

from lib import not_a_command
from lib.graph.renderer import text
from lib.ontology._kinds import (
    acyclic_kinds,
    load_ontology,
    ontology_shadowed,
    relation_findings,
)
from lib.shared import _markdown
from lib.shared._as_json import run_json
from lib.shared._root import find_repo_root
from lib.topology._walk import load, structural_findings

ROOT = find_repo_root(Path(__file__).resolve())
META_ROOT = ROOT / "architecture"


def _ontology_findings(
    data: pathlib.Path, meta: pathlib.Path, topology_meta: pathlib.Path
) -> list[str]:
    """Gate every node in `data` against `meta`'s own declared ontology.

    `topology_meta` is separate from `meta` on purpose: walking `data` to find
    its declared nodes (`lib.topology._walk.load`) needs the TOPOLOGY declaration
    (root discovery, tier depth), not the ontology one — the two `--meta`
    halves `racecar.graph check` reads (`meta/ontology`, `meta/topology`)
    answer different questions and neither substitutes for the other here.

    Absent is a legitimate state (`racecar.graph.ontology.lib._verbs`'s own
    policy for a corpus with no declared ontology) — a `meta` with no declared
    ontology returns no findings at all rather than refusing to gate structure.
    Declared but cyclic is a real error: an ontology whose own `depends_on`
    graph is not a DAG fails every node it would otherwise have gated, because
    there is no principled way to pick which half of a cycle is authoritative.
    """
    spec = load_ontology(meta)
    if not spec or not spec.get("kinds"):
        return []
    kinds = spec["kinds"]
    if not acyclic_kinds(kinds):
        return [
            f"{meta}: `kinds` has a cycle in `depends_on` — an ontology's own "
            "dependency graph must be acyclic"
        ]
    base_required = (spec.get("base") or {}).get("required") or []
    declared = load(data, topology_meta)

    findings: list[str] = []
    for nid, node in sorted(declared.items()):
        kind = node.get("kind")
        if kind is None:
            findings.append(f"{nid}: has no declared `kind`")
            continue
        spec_for_kind = kinds.get(kind)
        if spec_for_kind is None:
            findings.append(
                f"{nid}: declares kind {kind!r}, which the ontology under {meta} "
                "does not define"
            )
            continue
        missing = [
            field
            for field in (*base_required, *(spec_for_kind.get("required") or []))
            if node.get(field) is None
        ]
        if missing:
            findings.append(
                f"{nid}: kind {kind!r} requires {missing} — this node has none of it"
            )
    return findings


def _is_stub(doc: _markdown.Document) -> bool:
    """Whether a principle's README says nothing past its title: empty, or `## Notes` + TODO."""
    title = doc.headings(1)
    words: list[str] = []
    for line in doc.body():
        if not line.text.strip() or (title and line.no == title[0].no):
            continue
        heading = doc.heading_at(line.no)
        words += ["<h2>"] if heading is not None and heading.level == 2 else []
        words += (heading.title if heading is not None else line.text).split()
    return not words or [w.lower().rstrip(".") for w in words] == [
        "<h2>",
        "notes",
        "todo",
    ]


def _principles_findings(tax: pathlib.Path) -> list[str]:
    """A STATED PRINCIPLE MUST BE DESCRIBED, and a described one must be stated.

    **Racecar's own rule, so it lives in racecar's own gate.** It matches directories named
    `[PR]NN-<name>` and cross-references `### P-NN.` headings in `PRINCIPLES.md` — both of
    them racecar's filing convention rather than anything a topology declares. In an
    adopter `tax / "PRINCIPLES.md"` is not there. `scripts/topology.py` carries what a
    topology DECLARES; this is not that.

    A tree with no `PRINCIPLES.md` is skipped rather than having every root directory flagged
    as undescribed against an index that does not exist.
    """
    errors: list[str] = []
    by_id: dict[str, str] = {}
    for entry in tax.iterdir():
        m = (
            re.match(r"^(?P<id>[PR]\d\d)-[a-z]+$", entry.name)
            if entry.is_dir()
            else None
        )
        if m:
            raw = m.group("id")
            by_id[f"{raw[0]}-{raw[1:]}"] = entry.name
    principles_md = tax / "PRINCIPLES.md"
    if not principles_md.is_file():
        return errors
    stated = {
        m.group(1)
        for heading in _markdown.read(principles_md).headings(3)
        if (m := re.match(r"([PR]-\d\d)\.", heading.title))
    }
    for pid in sorted(set(by_id) - stated):
        errors.append(
            f"{by_id[pid]}: has a directory but no `### {pid}.` entry in PRINCIPLES.md"
        )
    for pid in sorted(stated - set(by_id)):
        errors.append(
            f"{pid}: stated in PRINCIPLES.md but has no "
            f"architecture/{pid[0]}{pid[2:]}-*/ directory"
        )
    for pid in sorted(set(by_id) & stated):
        name = by_id[pid]
        # A stub is a bare `## Notes` and a TODO. The floor is deliberately low -- this
        # check is here to catch an EMPTY root, not to grade prose, which is not a
        # checker's business (R-03).
        if _is_stub(_markdown.read(tax / name / "README.md")):
            errors.append(f"{name}: stated but not described — README.md is a stub")
    return errors


def run(
    data: pathlib.Path | None = None, meta: pathlib.Path | None = None
) -> dict[str, Any]:
    """Gate the graph at `data` (racecar's own `architecture/` absent one), against
    `meta`'s declared topology + ontology (`meta` absent defaults to `data`).

    `meta` here is the corpus's overall meta home, one level up from either
    declaration -- `racecar.graph check`'s one `--meta` covers both halves, so it
    reads `meta/topology/` and `meta/ontology/` itself rather than making the
    caller pass two paths. `racecar.graph.ontology`/`racecar.graph.topology`, run
    standalone, take `--meta` pointing directly AT their own declaration's
    directory instead -- same split, one level apart, because a composite verb
    and its two independently-reachable halves take the argument at different
    scopes on purpose.

    The record: `errors` from every part; `shadowed`, `[kind, loser]` for each kind more
    than one joined corpus declares; `contains`, each walked node's parent id (None for a
    root); and `peers`, each node's declared peer ids. Raises `NotADirectoryError` when
    `data` is not a directory.
    """
    tax = (data if data is not None else META_ROOT).resolve()
    if not tax.is_dir():
        raise NotADirectoryError(f"{tax} is not a directory")
    meta_root = (meta if meta is not None else tax).resolve()

    errors, on_disk, edges = structural_findings(tax, meta_root / "topology")
    errors.extend(_principles_findings(tax))
    errors.extend(
        _ontology_findings(tax, meta_root / "ontology", meta_root / "topology")
    )
    errors.extend(
        relation_findings(tax, meta_root / "ontology", meta_root / "topology")
    )

    # Which of the joined corpora each kind was read FROM, where more than one declares
    # it. A repo is ALLOWED to restate a kind the delivered corpus also declares -- that
    # is how it narrows one -- so this is not a finding. It is reported because a silent
    # winner is indistinguishable from a reader that found the other file.
    shadowed = [
        [kind, str(loser)]
        for kind, loser in sorted(ontology_shadowed(meta_root / "ontology").items())
    ]

    def _parent_id(d: pathlib.Path) -> str | None:
        if d.parent == tax:
            return None
        pid = d.parent.relative_to(tax).as_posix()
        return pid if pid in on_disk else None

    contains = {nid: _parent_id(d) for nid, d in on_disk.items()}
    return {
        "errors": errors,
        "shadowed": shadowed,
        "contains": contains,
        "peers": edges,
    }


def _show(data: pathlib.Path | None, meta: pathlib.Path | None) -> int:
    """Run the gate and print its record as text; 0 clean, 1 any error."""
    try:
        record = run(data, meta)
    except NotADirectoryError as err:
        print(text.refusal("check: error", err), file=sys.stderr)
        return 1
    print(text.check(record))
    return 1 if record["errors"] else 0


def main(
    data: pathlib.Path | None = None,
    meta: pathlib.Path | None = None,
    *,
    as_json: bool = False,
) -> int:
    """Gate the graph and print the verdict; under `as_json` the text goes to stderr and
    stdout carries the exit code, the result this verb declares."""
    return run_json(as_json, lambda: _show(data, meta))


if __name__ == "__main__":
    not_a_command()
