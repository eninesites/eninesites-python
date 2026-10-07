"""Audit the COMMIT LOG against shared/COMMITS.md — the checks a commit-msg hook cannot make.

Every other commit gate racecar ships runs at commit-msg time and sees exactly one
message. That leaves three blind spots this closes:

  1. **Replayed commits are never gated.** Git does not run commit-msg hooks on a
     rebase `pick`. A commit that lands by rebase — reordered, rescued, replayed under
     a repair — bypasses check_commit_message and check_version_bump entirely, however
     correctly they are installed. Only a post-hoc pass over the log can see it.

  2. **Cross-commit rules have no single-message answer.** "Every released version has
     exactly one changelog section" and "the brief's generated stamp travels with the
     version home" are statements about the log, not about a message. check_changelog.py comes
     closest and still compares only the NEWEST heading to the working tree, so a
     version superseded a day later is unguarded forever after.

  3. **Merge commits are gated by nothing at all.** Every message gate skips a `Merge `
     subject by prefix, and pre-commit never fires because a merge runs
     `pre-merge-commit`. That matters because a merge is where a version bump goes
     missing silently: two branches that each bumped from one base wrote the IDENTICAL
     string into the version home, so git auto-merges it without a conflict and one
     release is discarded with every gate still green. audit_merge is the only thing
     looking.

Scope is deliberately bounded by --since (default: the commit that introduced this
repo's `.pre-commit-config.yaml`). History from before a repo enforced its conventions
is not drift, it is prehistory, and reporting it buries the findings that can still be
acted on. Widen it with `--since <ref>` or `--all` when you actually want the whole log.

Advisory by default: exit 0 and print the findings, because a commit that has shipped is
the owner's to rewrite or leave (shared/OWNERSHIP.md). `--strict` exits 1 for CI.

Part of `lib.package`: the `audit` verb (`_audit.run`) reads this, and nothing here
prints. The report is `renderer.text.audit`'s.

Usage:
    python3 .racecar/scripts/package.py audit       # the delivered route
    python -m racecar.package audit                  # since the hooks landed
    python -m racecar.package audit --since v1.0.0    # since a ref
    python -m racecar.package audit --all --strict     # whole log, gating
    python -m racecar.package audit --json             # machine-readable

Exit 0 when clean (or advisory), 1 with --strict and any finding, 2 on a usage error.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lib import not_a_command
from lib.package._error import PackageError
from lib.shared import _commits, _markdown
from lib.shared._constants import RELEASE_RE, RELEASE_TITLE_RE

SUBJECT_MAX = 72

_FOOTER_RE = re.compile(r"^Bump version to (\d+\.\d+\.\d+)\.$", re.MULTILINE)


@dataclass(frozen=True)
class Finding:
    """One defect: the commit it lives in, a stable rule id, and what is wrong."""

    sha: str
    rule: str
    subject: str
    detail: str


def _git(*args: str, root: Path | None = None) -> str | None:
    """Run git in `root` and return stdout, or None when the command fails (object absent).

    `root` None is the working directory. Every public function here takes the same
    `root` and hands it down, because the audit is about ONE repository's log: without
    `-C` a caller's `--root` would be dropped at this line, and the audit would grade
    whatever repo the process is standing in.
    """
    prefix = ["git"] if root is None else ["git", "-C", str(root)]
    result = subprocess.run(
        [*prefix, *args], capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def version_at(rev: str, root: Path | None = None) -> str | None:
    """The version home's value at `rev`, per COMMITS.md "Version home".

    `[project].version` where a `[project]` table exists, else a root `VERSION` file.
    Both are checked because both are legal and one log can contain BOTH -- reading
    only pyproject.toml would report every version held in `VERSION` as though it never
    existed.
    """
    for home in ("pyproject.toml", "VERSION"):
        version = _commits.version_from(_git("show", f"{rev}:{home}", root=root), home)
        if version is not None:
            return str(version)
    return None


def parents_of(sha: str, root: Path | None = None) -> list[str]:
    """The parent SHAs of `sha`, in order. Two or more means a merge."""
    return (_git("log", "-1", "--format=%P", sha, root=root) or "").split()


def audit_merge(sha: str, root: Path | None = None) -> list[Finding]:
    """The one COMMITS.md finding that only a MERGE commit can carry.

    audit_commit returns early on a `Merge ` subject, and rightly: the format and
    type->bump rules do not apply to a message git wrote. But merges are where a bump goes
    missing, and nothing else racecar ships is looking.

    **Two branches that each bumped from one base claim the same number.** The changelog
    conflicts loudly -- both opened `## X.Y.Z` -- but the VERSION HOME does not conflict at
    all: both sides wrote the identical string, so git auto-merges it and one bump is
    discarded in silence. check_version_bump.py skips `Merge ` by prefix, check_changelog.py
    compares only the newest heading against the version home (which the surviving pair
    satisfies), and pre-commit never runs because a merge fires `pre-merge-commit`. Every
    gate passes on a repo that has lost a release.

    So: when two or more parents each moved the version off the merge-base, the merge must
    land STRICTLY ABOVE all of them. Equal to the highest means a bump was dropped --
    commit-merge/SKILL.md "advance the base once per bumping commit, in integration order",
    which scripts/bump_version.py exists to carry out.

    Losing the discarded bump's changelog CONTENT is the same defect seen from the other
    side, and is not checked separately: a resolution that keeps one side's section leaves
    the version home short, which is exactly what this reports.
    """
    parents = parents_of(sha, root)
    if len(parents) < 2:
        return []

    base = (_git("merge-base", "--octopus", *parents, root=root) or "").strip()
    merged = version_at(sha, root)
    base_version = version_at(base, root) if base else None
    if merged is None or base_version is None:
        return []  # no version home on one side: nothing to compare

    bumped = {}
    for parent in parents:
        value = version_at(parent, root)
        if value is not None and value != base_version:
            bumped[parent[:7]] = value
    if len(bumped) < 2:
        return []  # at most one side bumped: no collision, nothing to advance past

    merged_key = _commits.semver_key(merged)
    keys = [
        k for k in (_commits.semver_key(v) for v in bumped.values()) if k is not None
    ]
    if merged_key is None or not keys or merged_key > max(keys):
        return []

    sides = ", ".join(f"{p} -> {v}" for p, v in sorted(bumped.items()))
    return [
        Finding(
            sha[:7],
            "merge-discarded-bump",
            (_git("log", "-1", "--format=%s", sha, root=root) or "").strip(),
            f"{len(bumped)} parents bumped from {base_version} ({sides}), but the merge "
            f"is {merged} — it must advance past both, or a bump is lost",
        )
    ]


def sections_at(rev: str, root: Path | None = None) -> dict[str, str]:
    """`{version: date}` for every released CHANGELOG.md section at `rev`."""
    raw = _git("show", f"{rev}:CHANGELOG.md", root=root)
    if not raw:
        return {}
    return {
        m.group(1): m.group(2)
        for h in _markdown.parse(raw).headings(2)
        if (m := RELEASE_TITLE_RE.fullmatch(h.title)) and RELEASE_RE.match(m.group(1))
    }


def _lagged_brief(sha: str, new: str, root: Path | None = None) -> list[str]:
    """Why each `docs/summary/` member at `sha` is stamped with a version other than `new`.

    The brief's bump-written stamp rides with the version home, never a trailing sweep.
    Beside a generated inventory that is the inventory's alone: an authored member's stamp
    says when a person last read it, and lagging is its normal state.
    """
    brief = _git("show", f"{sha}:docs/summary", root=root)
    if (
        brief is None
        and _git("cat-file", "-e", f"{sha}:docs/summary", root=root) is None
    ):
        return []
    members = {
        path: _git("show", f"{sha}:docs/summary/{path}", root=root) or ""
        for path in (
            _git("ls-tree", "--name-only", f"{sha}:docs/summary", root=root) or ""
        ).split()
        if path.endswith(".md")
    }
    generated = {
        path: raw
        for path, raw in members.items()
        if re.search(r"\A---\n(?:.*\n)*?role: inventory\n", raw)
    }
    lagged: list[str] = []
    for path, raw in (generated or members).items():
        stamp = re.search(r"^target:\n(?:.*\n)*?  version: \"([^\"]+)\"", raw, re.M)
        if stamp and stamp.group(1) != new:
            lagged.append(
                f"version home at {new}, docs/summary/{path} stamped {stamp.group(1)}"
            )
    return lagged


def audit_commit(sha: str, root: Path | None = None) -> list[Finding]:
    """Every COMMITS.md finding attributable to one commit."""
    body = _git("log", "-1", "--format=%B", sha, root=root) or ""
    subject = body.splitlines()[0] if body.splitlines() else ""
    # AUTHOR date, never commit date. A rebase preserves the author date and rewrites
    # the commit date, so comparing a changelog section against the commit date reports
    # every replayed commit as misdated.
    authored = (_git("log", "-1", "--format=%as", sha, root=root) or "").strip()
    short = sha[:7]
    out: list[Finding] = []

    if subject.lower().startswith(_commits.SKIP_PREFIXES):
        return out

    match = _commits.SUBJECT_RE.match(subject)
    if match is None:
        return [
            Finding(
                short,
                "non-conventional-subject",
                subject,
                "expected `<type>(<scope>): <description>`, lowercase",
            )
        ]

    commit_type = match.group("type")
    if commit_type not in _commits.BUMP_BY_TYPE:
        out.append(
            Finding(
                short,
                "unknown-type",
                subject,
                f"`{commit_type}` is not a COMMITS.md type; its bump is undefined",
            )
        )
        return out

    if len(subject) > SUBJECT_MAX:
        out.append(
            Finding(
                short,
                "subject-too-long",
                subject,
                f"{len(subject)} characters, over the {SUBJECT_MAX} allowed",
            )
        )

    old, new = version_at(f"{sha}^", root), version_at(sha, root)
    if old is None or new is None:
        return out  # root commit, or no version home yet: nothing to compare

    breaking = bool(match.group("bang")) or bool(_commits.BREAKING_RE.search(body))
    want = _commits.bump_for(commit_type, breaking, old)
    got = _commits.classify_delta(old, new)

    if got.startswith(("invalid", "unparseable")):
        out.append(Finding(short, "invalid-increment", subject, got))
    elif want != got:
        label = "breaking" if breaking else f"`{commit_type}`"
        out.append(
            Finding(
                short,
                "bump-mismatch",
                subject,
                f"{label} maps to {want}, but the version went {got} ({old} -> {new})",
            )
        )

    footer = _FOOTER_RE.search(body)
    if got != "none" and not got.startswith(("invalid", "unparseable")):
        if footer is None:
            out.append(
                Finding(
                    short,
                    "missing-bump-footer",
                    subject,
                    f"bumped to {new} with no `Bump version to {new}.` line",
                )
            )
        elif footer.group(1) != new:
            out.append(
                Finding(
                    short,
                    "wrong-bump-footer",
                    subject,
                    f"footer says {footer.group(1)}, version home says {new}",
                )
            )

        # One changelog section per bump, opened BY the bumping commit.
        sections = sections_at(sha, root)
        opened = set(sections) - set(sections_at(f"{sha}^", root))
        if new not in opened:
            out.append(
                Finding(
                    short,
                    "no-changelog-section",
                    subject,
                    f"bumped to {new} but opened no `## {new} - DATE` section",
                )
            )
        elif sections[new] != authored:
            out.append(
                Finding(
                    short,
                    "section-date-mismatch",
                    subject,
                    f"section dated {sections[new]}, authored {authored}",
                )
            )

        out.extend(
            Finding(short, "brief-stamp-lagged", subject, detail)
            for detail in _lagged_brief(sha, new, root)
        )
    elif footer is not None:
        out.append(
            Finding(
                short,
                "footer-without-bump",
                subject,
                f"body claims a bump to {footer.group(1)}, version home unchanged",
            )
        )

    return out


def audit_history(revs: list[str], root: Path | None = None) -> list[Finding]:
    """Per-commit findings across `revs` in `root`'s log, plus the whole-log ones."""
    findings: list[Finding] = []
    for sha in revs:
        findings += audit_commit(sha, root)
        findings += audit_merge(sha, root)  # a no-op for everything with one parent

    # Whole-log: a released version with no section ANYWHERE. Per-commit checking cannot
    # see this -- a commit that opened no section may have had one added later, and a
    # version superseded quickly is invisible to check_changelog's newest-only compare.
    present = set(sections_at("HEAD", root))
    held: list[tuple[str, str]] = []
    for sha in reversed(revs):
        version = version_at(sha, root)
        if version and (not held or held[-1][1] != version):
            held.append((sha[:7], version))
    for short, version in held:
        if version not in present:
            findings.append(
                Finding(
                    short,
                    "released-version-unrecorded",
                    "",
                    f"{version} was released and has no CHANGELOG.md section",
                )
            )
    return findings


def default_since(root: Path | None = None) -> tuple[str | None, str]:
    """The commit that introduced `.pre-commit-config.yaml`, and how to describe it.

    The boundary is the point a repo began ENFORCING its conventions. Findings before it
    are prehistory: real, unfixable at any sane cost, and loud enough to bury everything
    actionable.
    """
    log = _git(
        "log",
        "--format=%H",
        "--reverse",
        "--diff-filter=A",
        "--",
        ".pre-commit-config.yaml",
        root=root,
    )
    if not log or not log.split():
        return None, "the whole log (no .pre-commit-config.yaml in history)"
    sha = log.split()[0]
    return sha, f"{sha[:7]} (where .pre-commit-config.yaml first appears)"


def resolve_revs(
    *, all_: bool = False, since: str | None = None, root: Path | None = None
) -> tuple[list[str], str]:
    """Resolve the commits `--all`/`--since` name; return `(revs, label)`.

    The git-repo and `--since` validation are preconditions of the audit, not of any one
    command line, so they sit here and every caller gets them.

    Raises `PackageError` with code `2` when a precondition fails. Printing is left to
    the verb's `main`, which writes the line to stderr.
    """
    if _git("rev-parse", "--git-dir", root=root) is None:
        raise PackageError("check_commit_history: not a git repository", 2)

    if all_:
        spec, label = "HEAD", "the whole log"
    elif since:
        if _git("rev-parse", "--verify", f"{since}^{{commit}}", root=root) is None:
            raise PackageError(f"check_commit_history: no such ref: {since}", 2)
        spec, label = f"{since}..HEAD", f"{since}..HEAD"
    else:
        sha, label = default_since(root)
        spec = "HEAD" if sha is None else f"{sha}^..HEAD"

    revs = (_git("rev-list", spec, root=root) or "").split()
    return revs, label


if __name__ == "__main__":
    not_a_command()
