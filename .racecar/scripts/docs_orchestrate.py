#!/usr/bin/env python3
"""The docs orchestrator: run the deterministic doc pipeline, in dependency order.

Single entry point for the mechanical backbone of ``/racecar-docs``
(``docs-orchestrator/ORCHESTRATION.md``). It COMPOSES the existing checkers —
it re-implements none of them — and runs them as staged gates in the order the
orchestration sequence prescribes:

    1. manifest        check_required_docs.py
    2. content-blind   check_content_blind.py
    3. config-closure  check_config_closure.py (README vs config.toml, if present)
    4. coherence       check_docs.py, check_doc_graph.py, check_file_placement.py,
                       lexicon.py
    5. brief           check_brief.py

The GENERATIVE steps of the sequence (stub a missing doc, regenerate the
machine spine via the llm-summary and surface-doc generators) require judgment
and are the agent's to drive per ORCHESTRATION.md; this backbone is the
deterministic report-and-gate half (R-03: the gate is a script; the model
authors). It collects every stage, prints one consolidated report, and returns
a single exit code (1 if any gate failed).

Checker resolution is location-agnostic so the orchestrator runs both in
racecar's own tree (checkers under the lens dirs) and in an adopter repo
(checkers synced flat into ``<root>/scripts``).

Output:
  - A per-stage report; each checker's own output is passed through.
  - Summary: ``docs_orchestrate: OK`` (exit 0) or
    ``docs_orchestrate: N gate(s) failed`` (exit 1).

Usage:
    python3 <path-to>/docs_orchestrate.py [--root <path>] [--list]

Complexity: O(k) where k = total checkers across PIPELINE stages; each stage's own cost
is that checker script's, not this driver's.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from lib.shared._root import find_repo_root

# (stage, [checkers]) in dependency order. A checker is a filename, or a `(filename, *argv)`
# tuple when it needs arguments. The filename is resolved against the search path; one that
# resolves nowhere is reported skipped.
#
# The argv form exists because a flat tuple of NAMES cannot carry arguments:
# `lexicon.py` would run with no subcommand (printing its help and exiting 0) while
# `check` and `--all` would each be looked up as scripts and reported skipped, and the
# stage would pass with the lexicon never graded through it.
Checker = str | tuple[str, ...]
PIPELINE: tuple[tuple[str, tuple[Checker, ...]], ...] = (
    ("manifest", ("check_required_docs.py",)),
    # Cross-file content closure: the README against `config.toml`. A sibling rather
    # than a branch inside `check_required_docs.py`, whose own docstring scopes it to
    # the repo-root doc SPINE and whose complexity note records O(1) over a fixed path
    # set -- folding this in would falsify both statements.
    ("config-closure", ("check_config_closure.py",)),
    ("content-blind", ("check_content_blind.py",)),
    (
        "coherence",
        (
            "check_docs.py",
            "check_doc_graph.py",
            "check_file_placement.py",
            # Grades the lexicon: every corpus the join yields, so the delivered ontology's
            # kinds are graded here too. `ontology.py` and `topology.py` are deliberately
            # absent -- they are libraries this one imports, with no command line of their
            # own, and a pipeline row that ran them would report `ok` for having done
            # nothing.
            ("lexicon.py", "check", "--all"),
        ),
    ),
    ("brief", ("check_brief.py",)),
)


#: A stage that applies only where the repo holds what it grades, with the reason it does
#: not apply elsewhere. The brief is optional (docs-orchestrator/ORCHESTRATION.md: its
#: absence is never a finding), and racecar.mk's `docs` target skips `check_brief.py`
#: without one; running it anyway would fail every adopter with no brief on "no brief
#: found".
def _has_brief(root: Path) -> bool:
    """Whether the repo holds a brief under `docs/summary/`."""
    return any((root / "docs" / "summary").glob("*.md"))


def _always(_root: Path) -> bool:
    """A stage with no applicability condition applies everywhere."""
    return True


APPLIES: dict[str, tuple[Callable[[Path], bool], str]] = {
    "brief": (_has_brief, "no docs/summary/ brief; a brief is optional"),
}


def _adopted(root: Path) -> bool:
    """Whether racecar was delivered into `root`: it has a `.racecar/`."""
    return (root / ".racecar").is_dir()


#: Checkers that grade racecar's OWN doc conventions -- the required doc set and its
#: frontmatter, the `pnode` graph, the markdown placement whitelist -- rather than a fact
#: about any repo's docs. Run from racecar's checkout against a repo that never adopted
#: racecar (`racecar --root <repo> check`), they would report a convention the repo never
#: took on, so there they do not apply. Every adopter has `.racecar/`, so in an adopter
#: they always run. Broken links and cited paths (`check_docs.py`) apply everywhere.
APPLIES_TO_CHECKER: dict[str, tuple[Callable[[Path], bool], str]] = {
    name: (
        _adopted,
        "racecar not adopted here (no .racecar/); this checks racecar's own doc conventions",
    )
    for name in (
        "check_required_docs.py",
        "check_doc_graph.py",
        "check_file_placement.py",
    )
}


def search_dirs(repo_root: Path) -> list[Path]:
    """Directories to resolve a checker filename against, most-specific first."""
    here = Path(__file__).resolve().parent
    candidates = [here, repo_root / "scripts"]
    seen: set[Path] = set()
    ordered: list[Path] = []
    for d in candidates:
        if d not in seen and d.is_dir():
            seen.add(d)
            ordered.append(d)
    return ordered


def checker_argv(checker: Checker) -> tuple[str, tuple[str, ...]]:
    """`(filename, argv)` for a pipeline entry, whichever of the two forms it is in."""
    if isinstance(checker, str):
        return checker, ()
    return checker[0], tuple(checker[1:])


def resolve_checker(name: str, dirs: list[Path]) -> Path | None:
    """Return the first existing `name` across `dirs`, or None."""
    for d in dirs:
        candidate = d / name
        if candidate.is_file():
            return candidate
    return None


def run_checker(
    script: Path, repo_root: Path, argv: tuple[str, ...] = ()
) -> tuple[int, str]:
    """Run a checker from `repo_root` (it self-discovers via .git); return (rc, out)."""
    proc = subprocess.run(
        [sys.executable, str(script), *argv],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the orchestrator."""
    parser = argparse.ArgumentParser(
        description="Run the deterministic docs pipeline (compose the racecar checkers)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root. Default: discovered via .git walk-up from CWD.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the pipeline stages and the checker each composes, then exit.",
    )
    return parser.parse_args(argv)


def print_pipeline() -> int:
    """Print the pipeline stages and their composed checkers; return 0."""
    print("docs_orchestrate pipeline (dependency order):")
    for stage, checkers in PIPELINE:
        names = [" ".join((checker_argv(c)[0], *checker_argv(c)[1])) for c in checkers]
        print(f"  {stage}: {', '.join(names)}")
    return 0


def findings(repo_root: Path) -> list[dict[str, str]]:
    """One record per checker the pipeline reached, in stage order. Prints nothing.

    Keys are `stage`, `checker`, `status` and `output`. `status` is "ok", "failed"
    or "absent"; "absent" is not a failure, it is how applicability is expressed —
    a repo that did not receive a checker, or holds nothing a stage grades (`APPLIES`),
    has no gate of that kind to fail. An absent stage's `output` says why.

    This returns the run rather than printing it so a caller other than this file's
    own command line can have the results. `main` below renders exactly this, so the
    two cannot drift; `racecar.docs.api.check` calls this directly.
    """
    dirs = search_dirs(repo_root)
    out: list[dict[str, str]] = []
    for stage, checkers in PIPELINE:
        applies, why_not = APPLIES.get(stage, (_always, ""))
        for checker in checkers:
            name, argv = checker_argv(checker)
            mine, why_mine = APPLIES_TO_CHECKER.get(name, (_always, ""))
            if not applies(repo_root) or not mine(repo_root):
                out.append(
                    {
                        "stage": stage,
                        "checker": name,
                        "status": "absent",
                        "output": why_not if not applies(repo_root) else why_mine,
                    }
                )
                continue
            script = resolve_checker(name, dirs)
            if script is None:
                out.append(
                    {"stage": stage, "checker": name, "status": "absent", "output": ""}
                )
                continue
            code, text = run_checker(script, repo_root, argv)
            out.append(
                {
                    "stage": stage,
                    "checker": name,
                    "status": "failed" if code else "ok",
                    "output": text,
                }
            )
    return out


def render(records: list[dict[str, str]]) -> str:
    """The report `main` prints, built from `findings`. One home for the format."""
    lines: list[str] = []
    seen: set[str] = set()
    for r in records:
        if r["stage"] not in seen:
            seen.add(r["stage"])
            lines.append(f"\n=== stage: {r['stage']} ===")
        if r["status"] == "absent":
            why = r["output"] or "not found on the search path"
            lines.append(f"  {r['checker']}: skipped — {why}")
        else:
            lines.append(r["output"].rstrip("\n"))
    failures = sum(1 for r in records if r["status"] == "failed")
    lines.append("")
    lines.append(
        "docs_orchestrate: OK"
        if not failures
        else f"docs_orchestrate: {failures} gate(s) failed"
    )
    return "\n".join(lines)


def failed(records: list[dict[str, str]]) -> int:
    """1 when any checker in the run failed, else 0. The exit code a surface uses."""
    return 1 if any(r["status"] == "failed" for r in records) else 0


def main(argv: list[str] | None = None) -> int:
    """Run the composed docs pipeline and return a single exit code."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.list:
        return print_pipeline()

    repo_root = args.root.resolve() if args.root else find_repo_root()
    records = findings(repo_root)
    print(render(records))
    return failed(records)


if __name__ == "__main__":
    sys.exit(main())
