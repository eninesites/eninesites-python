"""Every ontology verb's text view, rendered from the record the verb returns.

The one home of what a person reads. `scripts/ontology.py` and
`python -m racecar.graph.ontology` both call a verb for its record and hand the record here,
so the two routes print the same lines because only this module prints them. `--json` prints
the record itself; every number a line shows is read off that record.

Complexity: O(K) in the kinds a record carries
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lib import not_a_command

if TYPE_CHECKING:
    from lib.ontology._check import Checked
    from lib.ontology._kinds import Proposal


def proposal(record: Proposal) -> str:
    """`identify` and `derive`: one line per proposed kind, or why there is nothing to propose."""
    if not record.kinds:
        return "identify: nothing to propose — no `.md` sources carry a `kind` field"
    lines = []
    for kind, fields in sorted(record.kinds.items()):
        deps = record.dag.get(kind)
        suffix = f"  depends_on: {', '.join(deps)}" if deps else ""
        lines.append(
            f"  {kind:20} requires: {', '.join(fields) or '(none observed)'}{suffix}"
        )
    return "\n".join(lines)


def check(record: Checked, domains: list[str] | None) -> str:
    """`check`: the sources scored, and the declared ontology's share of them or its misfit.

    `domains` is the projection the caller asked for, named in the line because the fit of
    one projection is a different number from the fit of the whole corpus.
    """
    where = f" [domain: {', '.join(domains)}]" if domains else ""
    if record.best is not None:
        return (
            f"check: {record.total} sources{where}: "
            f"{100 * (1 - record.unmapped_fraction):.0f}% {record.best}, "
            f"{100 * record.unmapped_fraction:.0f}% unmapped"
        )
    return (
        f"check: {record.total} sources{where}: no declared ontology fits "
        f"({100 * record.unmapped_fraction:.0f}% unmapped)"
    )


def refusal(label: str, err: object) -> str:
    """One line naming what could not run and why: `<label>: <reason>`."""
    return f"{label}: {err}"


if __name__ == "__main__":
    not_a_command()
