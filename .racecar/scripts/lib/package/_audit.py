"""The `audit` verb: check the commits already made against shared/COMMITS.md.

Part of `lib.package`; `scripts/package.py` parses the command line and calls `main`, and
`racecar.package.api.audit` returns what `run` returns. The rules are
`_commit_history.py`'s; this maps its findings to the record and prints nothing but in `main`.

Exit: 0, or 1 with `--strict` and a finding; 2 for a range that does not resolve.

Complexity: O(C) in the commits audited, each a handful of git calls
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from lib import not_a_command
from lib.package import _commit_history as _history
from lib.package._error import FINDINGS, OK, PackageError
from lib.package.renderer import text


def run(
    root: Path, *, audit_all: bool = False, since: str | None = None
) -> list[dict[str, str]]:
    """The audit's findings, each `{severity, subject, rule, message}`.

    `_commit_history.Finding.subject` is the commit's OWN message-subject line (e.g. "fix:
    x"), not this shape's `subject` (the finding's identity -- which commit). Mapped:
    `Finding.sha` becomes the identity, and `Finding.subject` has no field of its own
    here, so it is folded into `message` ahead of `detail` rather than dropped --
    `audit_history` sets it to "" for a whole-log finding (e.g.
    `released-version-unrecorded`) with no single commit subject.

    Every rule here is a real violation of an already-canonical convention (COMMITS.md) --
    "ships as canonical but is wrong" is Major's own definition. The auditor tracks no
    per-rule severity to translate instead, and inventing one is a taxonomy judgment it
    gives no basis for.
    """
    # The default scope is history since the repo began enforcing its conventions, because
    # prehistory buries what is still actionable. `--all` and `--since` both set the range.
    if audit_all and since is not None:
        raise PackageError(
            "audit: --all and --since are exclusive; each sets the range"
        )
    revs, _label = _history.resolve_revs(all_=audit_all, since=since, root=root)
    return [
        {
            "severity": "Major",
            "subject": finding.sha,
            "rule": finding.rule,
            "message": (
                f"{finding.subject}: {finding.detail}"
                if finding.subject
                else finding.detail
            ),
        }
        for finding in _history.audit_history(revs, root)
    ]


def main(
    root: Path,
    *,
    audit_all: bool = False,
    since: str | None = None,
    strict: bool = False,
    as_json: bool = False,
) -> int:
    """Print the findings, as JSON or as `renderer.text`'s report."""
    try:
        findings = run(root, audit_all=audit_all, since=since)
    except PackageError as exc:
        print(exc, file=sys.stderr)
        return exc.code
    print(
        json.dumps(findings, indent=2)
        if as_json
        else text.audit(findings, strict=strict)
    )
    return FINDINGS if findings and strict else OK


if __name__ == "__main__":
    not_a_command()
