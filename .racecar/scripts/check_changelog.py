#!/usr/bin/env python3
"""Assert CHANGELOG.md's headings parse and its newest entry matches the version home.

Delivered to every governed repo and run by `make docs`. The packaging-rule changelog
check (lib/packaging/_changelog) only verifies that a changelog has a valid
Keep-a-Changelog header somewhere; this is the stricter grading: every `## ` heading is
well-formed and unique, and the newest released one matches the declared version, so the
per-version record can neither fall behind the code nor quietly stop being a record.

The version home is resolved per shared/COMMITS.md "Version home" and
arch-python/PACKAGING.md section 8: the library pyproject's `[project].version`
where a `[project]` table exists, else a root `VERSION` file. Both are supported
because both are legal shapes — a repo that publishes nothing has no pyproject
version for VERSION to be redundant with.

The repo is discovered by walking up from the working directory to the nearest `.git`,
the same convention every other delivered checker uses. Deriving it from `__file__`
would be wrong in exactly one case that matters: `racecar check --root <repo>` resolves
racecar's own copy of a checker in preference to the target's, so a `__file__`-relative
root would grade racecar's changelog while claiming to grade the target's.

Complexity: O(n), n = lines in CHANGELOG.md
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from lib.shared import _markdown
from lib.shared._constants import RELEASE_TITLE_RE, UNRELEASED_TITLE
from lib.shared._root import find_repo_root


def newest_changelog_version(changelog: str) -> str | None:
    """Return the version of the newest released CHANGELOG.md entry, or None.

    A released entry is `## X.Y.Z - YYYY-MM-DD`; the `## [Unreleased]` placeholder a fresh
    changelog may carry has no version, so it is not one.
    """
    for heading in _markdown.parse(changelog).headings(2):
        if match := RELEASE_TITLE_RE.fullmatch(heading.title):
            return match.group(1)
    return None


def declared_version(root: Path) -> str | None:
    """Return the repo's version from its single home, or None if there is none.

    Order is COMMITS.md's, not a preference: `[project].version` wins wherever a
    `[project]` table exists, because that is what makes a root `VERSION` file
    redundant. Falling back to `VERSION` is not legacy tolerance — it is the
    correct home for a repo that declares no `[project]`.
    """
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        version = data.get("project", {}).get("version")
        if isinstance(version, str):
            return version
    version_file = root / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return None


def heading_problems(changelog: str) -> list[str]:
    """Return every structural fault in CHANGELOG.md's `## ` headings.

    The version comparison above reads only the NEWEST heading and leaves everything
    below it ungraded. A heading is not
    decoration here: `newest_changelog_version` parses one, `/racecar-commit` appends
    one per bump, and the brief cites them, so a malformed heading silently changes
    what those read rather than failing loudly.

    Two faults, both cheap. A `## ` line that is neither
    `[Unreleased]` nor `X.Y.Z - YYYY-MM-DD` is malformed — a typo'd date or a missing
    separator makes a released section invisible to the regex, so the version check
    skips past it to an older entry and passes. A version appearing twice is a
    duplicate section: whichever copy is lower can never be reached by a reader
    scanning downward for it, and one of the two is stale by definition.

    The malformed-heading arm also catches a misplaced rename: a rename of
    `## [Unreleased]` to a release heading that matches the occurrence inside the intro
    PROSE, where the changelog documents its own format in backticks, instead of the
    heading. That splices the release heading and its
    entries into the middle of a sentence — where they sit indented behind a backtick and
    are invisible to a line-anchored regex — and strands the tail of the sentence at
    column 0 behind the `## [Unreleased]` it quoted, where it reads as a section
    whose body is a paragraph about semver. The stranded tail is a `## ` line that is not
    `[Unreleased]` and not a released entry, so it is flagged here; the displaced release
    heading is caught independently, because the newest heading the file still exposes is
    now an older version than the one declared.
    """
    problems: list[str] = []
    seen: dict[str, int] = {}
    for lineno, _, heading in _markdown.parse(changelog).headings(2):
        if heading == UNRELEASED_TITLE:
            continue
        match = RELEASE_TITLE_RE.fullmatch(heading)
        if match is None:
            problems.append(
                f"CHANGELOG.md:{lineno}: malformed heading `## {heading}` — "
                "expected `## [Unreleased]` or `## X.Y.Z - YYYY-MM-DD`"
            )
            continue
        version = match.group(1)
        if version in seen:
            problems.append(
                f"CHANGELOG.md:{lineno}: duplicate section for {version} "
                f"(already at line {seen[version]})"
            )
        else:
            seen[version] = lineno
    return problems


def _read(
    root: Path, precomputed: tuple[str | None, str | None] | None
) -> tuple[str | None, str | None]:
    """`(version, changelog_text)`, from `precomputed` when given, else read fresh.

    `changelog_text` is None exactly when `CHANGELOG.md` does not exist -- distinct from
    an empty string, which means it exists and is empty (and fails `newest_changelog_version`
    on its own terms).
    """
    if precomputed is not None:
        return precomputed
    changelog_path = root / "CHANGELOG.md"
    text = (
        changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else None
    )
    return declared_version(root), text


def not_graded(
    root: Path, precomputed: tuple[str | None, str | None] | None = None
) -> str | None:
    """Return why the version comparison does not apply to `root`, or None when it does.

    The one home for "this repo has nothing to compare". Three states qualify, and none
    of them is a defect this checker gets to declare — each is either already graded
    elsewhere or explicitly permitted by canon:

      - **No CHANGELOG.md.** PACKAGING.md section 8 makes the file RECOMMENDED, not
        required, and check_packaging already reports its absence as a Finding. A second
        report here would be a second home for one rule, and a harder one than the rule.
      - **No version home.** check_packaging already reports a missing
        `[project].version` as a Blocker. Same reason.
      - **No released section yet.** A repo before its first release carries only
        `## [Unreleased]`, which shared/COMMITS.md "One changelog section per bump"
        describes as the correct state for a commit that bumps nothing. There is no
        released heading for the declared version to disagree with.

    Structural grading is deliberately NOT gated on any of this: `heading_problems` runs
    against whatever CHANGELOG.md exists, so a pre-release repo still has its headings
    checked. Only the version comparison is skipped, and visibly — a silent skip reads as
    a pass, which is how a gate quietly stops gating.

    `precomputed`, an optional `(version, changelog_text)` pair, lets `main()` thread a
    single read of `pyproject.toml` and `CHANGELOG.md` through this, `problem`, and
    `heading_problems` instead of each re-deriving it. A call site that passes only
    `root` reads both files itself.
    """
    version, changelog_text = _read(root, precomputed)
    if version is None:
        return (
            "no version home: neither [project].version in pyproject.toml "
            "nor a root VERSION file"
        )
    if changelog_text is None:
        return "no CHANGELOG.md"
    if newest_changelog_version(changelog_text) is None:
        return "CHANGELOG.md has no released `## X.Y.Z - YYYY-MM-DD` section yet"
    return None


def problem(
    root: Path, precomputed: tuple[str | None, str | None] | None = None
) -> str | None:
    """Return an error message if the version home and newest changelog entry disagree.

    Returns None for any state `not_graded` names, so a caller that skips that
    consultation gets silence rather than a defect report for a legitimate repo.
    """
    if not_graded(root, precomputed) is not None:
        return None
    version, changelog_text = _read(root, precomputed)
    assert changelog_text is not None  # not_graded above already ruled out None
    top = newest_changelog_version(changelog_text)
    if top != version:
        return (
            f"the declared version is {version} but the newest CHANGELOG.md entry "
            f"is {top}; add a {version} entry"
        )
    return None


def findings(root: Path) -> list[dict[str, str]]:
    """Everything this check has to say about `root`. Prints nothing.

    Keys are `level` — `error` for something that fails the gate, `info` for something
    that is merely worth saying — and `message`. An empty list means a clean repo.

    `pyproject.toml` and `CHANGELOG.md` are each read once for the whole run and the
    result threaded through, rather than re-derived by each helper.
    """
    precomputed = _read(root, None)
    _, changelog_text = precomputed
    out: list[dict[str, str]] = []

    skipped = not_graded(root, precomputed)
    if skipped:
        out.append(
            {
                "level": "info",
                "message": f"skipping the version comparison ({skipped})",
            }
        )
    else:
        err = problem(root, precomputed)
        if err:
            out.append({"level": "error", "message": err})

    if changelog_text is not None:
        for fault in heading_problems(changelog_text):
            out.append({"level": "error", "message": fault})
    return out


def render(records: list[dict[str, str]]) -> str:
    """The report `main` prints, built from `findings`. One home for the format."""
    return "\n".join(f"check_changelog: {r['message']}" for r in records)


def failed(records: list[dict[str, str]]) -> int:
    """1 when anything in `records` fails the gate, else 0."""
    return 1 if any(r["level"] == "error" for r in records) else 0


def main() -> int:
    """CLI entry: 0 when the changelog leads with the version home and its headings parse."""
    records = findings(find_repo_root())
    for record in records:
        stream = sys.stderr if record["level"] == "error" else sys.stdout
        print(render([record]), file=stream)
    if failed(records):
        return 1
    print("check_changelog: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
