"""Which files a checker reads. One home, beside `_root.py`'s one home for where the repo is.

It lives in `scripts/lib/shared/` because a delivered checker runs from an adopter's flat
`scripts/` with no racecar installed; `src/racecar/lib/_files.py` is a symlink to this file,
so the library and the delivered checkers read the same code.

`_root.py` answers "where does this repo start". This answers the question one layer up:
**which files should a checker open**.

## Hidden DIRECTORIES are skipped. Hidden FILES are not.

The distinction is the whole rule, and getting it wrong is invisible in both directions.

A hidden directory is where a second copy of the repository lives — `.venv`, `.git`,
`.mypy_cache`, `.claude/worktrees`. Reading one makes a verdict depend on the machine
rather than on the repo.

A hidden file is ordinary committed content. `.gitignore`, `.pre-commit-config.yaml`,
`.yamllint`, `.ansible-lint` are files this repo owns and grades, and a checker that cannot
see them is blind to nine files here.

## Why `os.walk` and not `glob`

`glob` will not match a leading dot, so `**/*.md` never descends into `.venv` or
`.claude/worktrees`, where `Path.rglob` walks everything and leaves the caller to
discard what it read. But that rule is a single switch over both meanings of "hidden",
and it takes the files with the directories: under `glob`, `repo_files(root, "*")`
would return **zero** dotfiles. `glob(..., include_hidden=True)` only inverts the
switch, and descends `.venv` again.

`os.walk` separates them, because pruning happens on `dirs` and files are never pruned.
Mutating `dirs[:]` in place is what stops the descent; assigning a new name would not.
Faster than `glob` and it states the rule instead of encoding it as a side effect.

## Every caller names its own extensions

There is no default and no "all files". A checker states what it reads — `("*.md",)` for a
doc checker, `("*.md", "*.py", "*.sh", "*.mk")` for the nomenclature scan — because a
checker that does not know which files it grades cannot say what it covers.

## Gitignored, non-dot directories: pruned when git is available, walked when it is not

A hidden directory (leading dot) is pruned above on the name alone — no git needed. A
GITIGNORED directory need not be dot-prefixed at all: `build/`, `node_modules/`,
`vendor/` are ordinary names a repo excludes on purpose. Walking `build/` would send a
packaging artifact into every caller's path/doc/reachability graph as if it were part of
the repo.

`_ignored_entries()` asks `git ls-files --others --ignored --exclude-standard
--directory`, the same source `check_content_blind.py`'s `published_files` already uses
elsewhere in this delivered set — one behavior, reused. `--directory` collapses a
directory git can prove is entirely untracked-and-ignored to one entry ending in `/`,
which is what the walk below prunes from `dirs` before descending — it never has to
enumerate what is inside. A directory git cannot collapse (something tracked survives
inside it) is walked, and only the individual ignored files git names within
it are skipped; a genuinely tracked file two levels under a mostly-ignored directory is
still found, because git's own answer says so, not a directory-level guess.

This is a SOFT dependency, on purpose, and `git ls-files` does not replace `os.walk`:
`git ls-files` lists FILES, and this function's contract returns directories too (a
checker resolving `deploy-server/example` needs the directory entry, not just the files
under it), so git can inform the prune without becoming the enumeration. Anywhere `git`
is absent, or `root` is not a git repository, `_ignored_entries()` returns empty and the
walk prunes dot-directories only: nothing gitignored-aware, no subprocess run, no error
raised. A delivered checker has no hard git dependency, and a caller who DOES have git
gets a truthful answer instead of a fast, wrong one.
"""

from __future__ import annotations

import contextlib
import fnmatch
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path


# Pruned by NAME, always, with or without git. The one directory that is never a repo's
# own source in any Python project, and the only name hardcoded here.
#
# Everything else a project wants excluded goes through its own declaration
# (`ignore-paths` in `pyproject.toml`) or through `.gitignore`, both of which a reader can
# see. The temptation is to add `build`, `dist`, `node_modules` beside it -- resisted,
# because `build/` is real source in some repos, and a hardcoded name would make racecar
# skip those files and never say so. Reading too much is slow; reading too little is a
# checker that reports OK because it did not look, which is the worse failure by far.
# The one entrant for asking git which files a repo has. One entrant makes the flags a
# caller's argument rather than a module's private habit, which is what lets the memo
# below key on them.
class _LsState:
    """Holds the open scope's memo, or None when no scope is open.

    An OBJECT rather than a bare module-level name because `git_scope` has to rebind the
    memo, and assigning to a bare module name from inside a function requires `global` --
    which pylint reports (W0603) and this module, being delivered to other repos, must not
    carry. Assigning to an ATTRIBUTE is not assignment to the name, so no declaration is
    needed and none is possible to trip over.

    An object rather than a one-entry dict: a mistyped attribute raises AttributeError,
    where a mistyped dict key reads as "no scope is open" and the cache silently stops
    working. A cache that fails by being SLOW is the failure hardest to notice, so it is
    the one worth making impossible to write.
    """

    def __init__(self) -> None:
        self.memo: dict[tuple[str, tuple[str, ...]], str | None] | None = None


_LS_STATE = _LsState()


@contextlib.contextmanager
def git_scope() -> Iterator[None]:
    """Memoise `git_ls` for the duration of ONE operation, then forget it.

    No scope is open by default, and outside one NOTHING is cached. That direction is
    deliberate: a repo's file list is not a constant -- a test scaffolds a repo and commits
    into it, `sync` writes files and asks again -- so a cache that outlived the operation it
    was taken for would answer questions about a tree that has since moved. Slow is
    recoverable; silently stale is not.

    The scope is the unit over which the tree provably does not change: a checker reads, it
    does not write, so every question it asks has one answer for its whole run. That is what
    makes the memo sound with no invalidation protocol -- there is nothing to invalidate,
    because the cache does not outlive the read.

    Re-entrant on purpose. A checker that opens a scope and calls `repo_files`, which opens
    one too, must not have its cache dropped when the inner block exits; the OUTERMOST scope
    owns the lifetime and an inner one is a no-op. Without that, nesting would silently
    disable the cache for the outer caller, and the only symptom would be being slow.
    """
    if _LS_STATE.memo is not None:
        yield  # already inside a scope; the outer one owns the lifetime
        return
    _LS_STATE.memo = {}
    try:
        yield
    finally:
        _LS_STATE.memo = None


def git_ls(root: Path, *args: str) -> str | None:
    """`git ls-files <args>` in `root`, or None when git cannot answer.

    None is "this signal is unavailable" -- git missing, or `root` not a repository -- and
    is deliberately NOT the empty string, which would read as "this repo has no such files".
    Every caller treats the two differently: one falls back to an unfiltered walk, another
    asserts nothing. Collapsing them is how a checker comes to report OK because it did not
    look.

    Cached per `(root, args)` while a `git_scope` is open, and not at all otherwise.
    """
    cache = _LS_STATE.memo
    key = (str(root), args)
    if cache is not None:
        if key in cache:
            return cache[key]
    try:
        out: str | None = subprocess.run(
            ["git", "ls-files", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        out = None
    if cache is not None:
        cache[key] = out
    return out


_NEVER_SOURCE = frozenset({"__pycache__"})

# Hidden directories that ARE repo content, carved out of the rule above BY NAME.
#
# The rule's premise is that a hidden directory holds a second copy of the repository --
# `.venv`, `.git`, `.claude/worktrees` -- so reading one makes a verdict depend on the
# machine. `.racecar/` is the opposite of that in every respect: it is canon racecar
# DELIVERS into a governed repo, it is committed, and it is graded. It is hidden so that an
# adopter's own tree stays legible and so that nobody hand-edits a file the next sync
# overwrites, not because it is machine state.
#
# Carved out here rather than in each checker because a delivered tree that several
# checkers must agree to read is exactly the fact that has to live in one place.
# `.racecar/api-fix/` is run artifacts and stays out, through `.gitignore` and the
# git-ignored walk below, rather than through this rule.
CONTENT_DIRS = frozenset({".racecar"})


def is_hidden_path(relative: Path | str) -> bool:
    """Whether a repo-relative path is hidden, for a checker that filters paths it was
    already handed. Any dot-prefixed segment counts, except a `CONTENT_DIRS` name.

    The one home for "hidden means skip", so a carve-out is declared once rather than in
    every checker that re-derives it. This is the PATH-FILTER half of the rule and it is
    deliberately blunter than `repo_files`: the walk there prunes hidden directories and
    keeps hidden files, because it decides what to open, while a caller here has a
    relative path in hand and wants one yes/no. The doc checkers ask it only of `*.md`,
    where the two readings cannot differ.
    """
    return any(
        part.startswith(".") and part not in CONTENT_DIRS
        for part in Path(relative).parts
    )


def _ignored_entries(root: Path) -> tuple[set[str], set[str]]:
    """`(ignored_dirs, ignored_files)`, both relative-posix, from git's own ignore rules.

    Empty, empty when git is missing or `root` is not a git repository -- callers must
    not treat that as "nothing is ignored here" so much as "this signal is unavailable",
    which is exactly why the walk below falls back to pruning dot-directories only
    rather than asserting cleanliness it cannot back up.
    """
    out = git_ls(root, "--others", "--ignored", "--exclude-standard", "--directory")
    if out is None:
        return set(), set()
    dirs: set[str] = set()
    files: set[str] = set()
    for line in out.splitlines():
        if not line:
            continue
        (dirs if line.endswith("/") else files).add(line.rstrip("/"))
    return dirs, files


# The mode git records for a gitlink -- a submodule reference -- in a tree entry, as
# opposed to the modes it uses for files and directories. Named rather than inlined so the
# digits live in code, where they are a protocol constant, instead of in prose.
_GITLINK_MODE = "160000 "


def _submodule_dirs(root: Path) -> set[str]:
    """Every checked-out git submodule path under `root`, relative-posix.

    A submodule is a THIRD category, and the reason it needs its own query is that neither
    existing rule can reach it. It is not hidden, so the name test misses it. It is
    tracked -- the superproject's index records it as a gitlink, mode `160000` -- so
    `git ls-files --others --ignored` never lists it however much `.gitignore` says
    otherwise; a tracked path cannot be made to look ignored.

    That matters because a submodule's contents are not the adopter's to fix. Editing a
    file inside one changes only that nested repository's history, invisible to the
    superproject unless separately committed and pushed upstream, so a finding raised
    against it cannot be acted on where it was reported.

    Empty on any failure, matching `_ignored_entries`: no signal is not the same claim as
    no submodules, and the walk falls back rather than asserting cleanliness it cannot
    back up.
    """
    out = git_ls(root, "--stage")
    if out is None:
        return set()
    found: set[str] = set()
    for line in out.splitlines():
        # Each line is `<mode> <sha> <stage>\t<path>`. The mode is the only thing that
        # distinguishes a submodule from an ordinary directory of the same name, and
        # `_GITLINK_MODE` is the one git uses for it.
        meta, _, path = line.partition("\t")
        if path and meta.startswith(_GITLINK_MODE):
            found.add(path)
    return found


def repo_files(root: Path, *patterns: str) -> list[Path]:
    """Every path under `root` matching any of `patterns`, skipping hidden directories,
    `__pycache__`, and -- where git can say so -- gitignored ones and checked-out
    submodules.

    What it does NOT do is read the project's own `ignore-paths` declaration. That stays
    with the caller, which is the convention already in place (`check_doc_graph.in_scope`
    applies it after calling this): the declaration is read by one home in `check_docs`,
    and this module is the library half, which must not import a script to reach it.

    Returns files **and** directories: a checker that grades path references has to be able
    to resolve `deploy-server/example` as well as `deploy-server/example/site.yml`.

    Each pattern is matched against both the whole relative path and the basename, so
    `"*.md"` finds markdown at any depth and `"Makefile"` finds every Makefile. At least one
    pattern is required: see the module docstring on why there is no default.
    """
    if not patterns:
        raise ValueError(
            "repo_files needs at least one pattern — a checker states what it reads"
        )
    # One scope around both git questions, so a caller who did not open one still pays each
    # of them once rather than twice. A caller who DID open one keeps their own.
    with git_scope():
        ignored_dirs, ignored_files = _ignored_entries(root)
        submodules = _submodule_dirs(root)
    found: list[Path] = []
    for parent, dirs, files in os.walk(root):
        here = Path(parent)
        # In place. This is the one line that separates "hidden or
        # ignored directory" from "hidden or ignored file"; `files` is filtered per-name
        # below instead, since an ignored file can sit inside an otherwise-tracked dir.
        dirs[:] = [
            d
            for d in dirs
            if (not d.startswith(".") or d in CONTENT_DIRS)
            and d not in _NEVER_SOURCE
            and (here / d).relative_to(root).as_posix() not in ignored_dirs
            and (here / d).relative_to(root).as_posix() not in submodules
        ]
        kept_files = [
            f
            for f in files
            if (here / f).relative_to(root).as_posix() not in ignored_files
        ]
        for name in dirs + kept_files:
            path = here / name
            relative = path.relative_to(root).as_posix()
            if any(
                fnmatch.fnmatch(relative, p) or fnmatch.fnmatch(name, p)
                for p in patterns
            ):
                found.append(path)
    return sorted(found)
