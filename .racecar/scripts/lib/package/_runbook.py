"""Render a commit runbook: one HEAD guard, then the same per-commit shape N times.

Every `Commit` in a `render()` call gets the identical per-commit block, so there is no
"step 1 is special" to get wrong, because no commit is hand-typed into being different
from the others.

The two questions the per-commit block keeps separate, always:

  1. Does the bookkeeping EDIT need applying? Skip/apply, keyed on the version-home's
     CURRENT content (already at NEW: someone wrote the edit into the working tree
     before this script ran; still at OLD: apply it now). This is the only place a
     commit's own history can vary the control flow.
  2. Does this STEP need to commit? Always yes, unconditionally, once (1) has left the
     bookkeeping at NEW -- guaranteed safe because the single HEAD guard at the top
     already proves no commit in this run has landed yet.

The runbook runs in a git worktree, never the main checkout, and lands on that worktree's
branch. The series is tried in a clone of that worktree, on a throwaway branch
`rc-try/<label>` cut from the commit the branch is at. Each commit brings in your edits to
its own paths, does its bookkeeping and commits there, through the sourced
`commit_preflight.sh`; then the plan's gate runs there once. Only when all of it passes are
the tried commits fetched back and the branch moved to them by a compare-and-swap, and your
index and tree are synced for the paths the run committed -- so a run either lands the whole
series or lands nothing. Your checkout is not touched before landing, so on any failure
there is nothing to put back: the clone is deleted, and the same script can run again.
`--dry-run` stops after the gate.

`package.py commit --plan plan.json` is the one caller that renders and runs a runbook;
`Plan.from_dict` is the one reader of a plan. The generator is the package noun's, delivered
with it, and imports nothing but the standard library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lib import not_a_command


@dataclass(frozen=True)
class Bump:
    """The version-home + changelog + brief edit one commit makes, or does not
    need to make again if it is already sitting in the working tree.

    `inventory` is the bundle's generated member (`docs/summary/<REPO>-INVENTORY.md`). It
    is regenerated after the version home moves, and staged with the commit, so its
    `target.version` is true because the file was recomputed from the tree carrying it.
    The authored members of that bundle are never stamped by a bump: their stamp says when
    a person last read them, and moving it asserts a review that did not happen.

    `briefs` is for a two-file bundle only -- one with no generated member -- whose stamps
    move with the version home, so an adopter with that bundle keeps passing.
    """

    old: str
    new: str
    changelog_section: str
    version_home: str = "pyproject.toml"
    changelog: str = "CHANGELOG.md"
    briefs: tuple[str, ...] = ()
    inventory: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Bump":
        return Bump(
            old=d["old"],
            new=d["new"],
            changelog_section=d["changelog_section"],
            version_home=d.get("version_home", "pyproject.toml"),
            changelog=d.get("changelog", "CHANGELOG.md"),
            briefs=tuple(d.get("briefs", ())),
            inventory=d.get("inventory"),
        )


@dataclass(frozen=True)
class Commit:
    """One commit's worth of a runbook: its message, the paths it stages, and --
    only if this commit bumps -- the edit that bump needs.

    Two, mutually exclusive ways a commit bumps:

    - `bump`: the OLD/NEW pair is already known (a branch's own version-home edit is
      already sitting in the working tree, or the caller has otherwise computed it).
    - `assign_bump`: the commit is landing directly on the trunk with no version-home
      edit of its own yet, e.g. a `/racecar-issue <N>` fix committed straight to
      `main` rather than through a branch + PR -- the commit-msg hook's
      version-bump-gate refuses a bumpable type (`fix`/`feat`/`perf`) with no bump,
      and there is no OLD/NEW to hand it ahead of time because the version the trunk
      is actually at when this commit runs depends on every commit before it in the
      same plan. Set to the conventional type (`"fix"`, `"feat"`, ...); `breaking`
      marks a `!`/`BREAKING CHANGE:` commit, which COMMITS.md downgrades to a minor
      bump pre-1.0. Delegates to `bump_version.py --assign` from the delivered directory,
      which already
      knows how to promote `## [Unreleased]`, compute the next version, and bring the
      brief along (regenerate its inventory, or stamp a two-file bundle) -- this field
      exists so the runbook calls it, not so this module
      reimplements it a second time.

    `changelog_bullet`: this commit's own CHANGELOG entry (bullet text, no heading), written
    under `## [Unreleased]` in the section `changelog_heading` names -- by default the one
    the commit's type maps to (`feat` Added, `fix`/`perf` Fixed, `docs` Documentation,
    anything else Changed). It is skipped when the same text is already there, so the step
    can run twice. COMMITS.md wants every commit's entry written with it, including a
    commit that does not bump -- every commit off the trunk.

    With `assign_bump` the entry is written immediately before `bump_version.py --assign`
    promotes `[Unreleased]`, which is why it is never written there ahead of time: when a
    plan lands several `assign_bump` commits, the FIRST bump would promote every later
    commit's entry along with its own, before those commits had even happened."""

    message: str
    files: tuple[str, ...]
    bump: Bump | None = None
    assign_bump: str | None = None
    breaking: bool = False
    changelog_bullet: str | None = None
    changelog_heading: str | None = None

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Commit":
        bump = Bump.from_dict(d["bump"]) if d.get("bump") else None
        return Commit(
            message=d["message"],
            files=tuple(d["files"]),
            bump=bump,
            assign_bump=d.get("assign_bump"),
            breaking=bool(d.get("breaking", False)),
            changelog_bullet=d.get("changelog_bullet"),
            changelog_heading=d.get("changelog_heading"),
        )


#: What `git rev-parse HEAD` prints, which is what the emitted guard compares against.
_FULL_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class Plan:
    """A whole runbook: identity (for the HEAD/branch guard and the script's own
    log-line prefix) plus the ordered commits.

    `gate` is the command run once on the try branch after the last commit and before
    anything lands: `make check-full` unless the plan says otherwise. It is a field because
    the gate is the repo's to name. Setting it to None lands commits nothing graded as a
    whole, and `check_runbook.py` reports that.

    Every commit is tried in a clone through the delivered `commit_preflight.sh`,
    which the script sources: the full hook suite runs on each commit as it will land, and
    autofixes are re-staged to a fixpoint there. The runbook is that preflight plus landing.

    `cwd`, when set, is baked into the script as a literal `cd '<cwd>'` instead of
    `cd "$(git rev-parse --show-toplevel)"` -- a worktree-scoped runbook (every
    `/racecar-issue <N>` resolution lands in `.claude/worktrees/issue-<N>`) otherwise
    resolves to whatever repo the *caller's* shell happens to be sitting in, which is
    the main checkout the moment someone runs the script from there instead of from
    inside the worktree it was written for. `cwd` makes the script self-locating."""

    label: str
    head_sha: str
    commits: tuple[Commit, ...]
    branch: str | None = None
    cwd: str | None = None
    gate: str | None = "make check-full"

    def __post_init__(self) -> None:
        """Refuse a `head_sha` the emitted guard could never match.

        The guard is `[ "$(git rev-parse HEAD)" = "$EXPECTED" ]`, and `rev-parse` always
        prints 40 characters. An abbreviated sha is the natural thing to paste out of a
        `git log --oneline`, it renders into a guard that looks right, and it refuses on
        every run -- a script that cannot execute rather than one that executes wrongly,
        but only discovered by running it. Nothing else reads this value, so the check is
        the shape rather than the existence of the object.
        """
        if not _FULL_SHA.fullmatch(self.head_sha):
            raise ValueError(
                f"head_sha must be a full 40-character sha, got {self.head_sha!r} — "
                "the HEAD guard compares against `git rev-parse HEAD`, which is never "
                "abbreviated, so this would refuse on every run"
            )

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Plan":
        return Plan(
            label=d["label"],
            head_sha=d["head_sha"],
            commits=tuple(Commit.from_dict(c) for c in d["commits"]),
            branch=d.get("branch"),
            cwd=d.get("cwd"),
            gate=d.get("gate", "make check-full"),
        )


def _sh_str(s: str) -> str:
    """A single-quoted shell literal, safe for arbitrary text (git messages included)."""
    return "'" + s.replace("'", "'\\''") + "'"


def _heredoc(marker: str, body: str) -> str:
    """A quoted (`<<'MARKER'`) heredoc -- no expansion inside, exactly what a drafted
    commit message or changelog section needs, since neither should have `$` or
    backticks interpreted by the shell that writes it to a temp file."""
    text = body if body.endswith("\n") else body + "\n"
    return f"<<{_sh_str(marker)}\n{text}{marker}\n"


_HELPERS = """
bump_version() {
  # $1 = version-home path, $2 = old, $3 = new, $4.. = a two-file bundle's brief paths
  # (a bundle with a generated inventory regenerates it instead). Every caller of this
  # function already knows OLD is the home's CURRENT content -- callers never invoke it
  # speculatively. A brief's stamp moves through the delivered bump_version.py's
  # `rewrite_brief_stamp`, the one home of that rule: it moves `target.version` only,
  # because the same frontmatter carries `generator.version`, which can hold OLD too.
  local home="$1" old="$2" new="$3"
  shift 3
  "$PY" - "$RC" "$home" "$old" "$new" "$@" <<'PYEOF'
import sys, pathlib
rc, home, old, new, briefs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
sys.path.insert(0, rc)
sys.dont_write_bytecode = True  # importing leaves no __pycache__ in the repo
from bump_version import bump_stamps, rewrite_brief_stamp
p = pathlib.Path(home)
text = p.read_text(encoding="utf-8")
target = f'version = "{old}"'
assert text.count(target) == 1, f"expected exactly one {target!r} in {home}"
p.write_text(text.replace(target, f'version = "{new}"'), encoding="utf-8")
for brief in briefs:
    bp = pathlib.Path(brief)
    btext = bp.read_text(encoding="utf-8")
    if not bump_stamps(btext):
        continue  # an authored member beside a generated inventory: last read, not bumped
    moved = rewrite_brief_stamp(btext, old, new)
    assert moved != btext, f'expected a target.version "{old}" stamp in {brief}'
    bp.write_text(moved, encoding="utf-8")
PYEOF
}

mark_added() {
  # $@ = this commit's files. check_brief.py reads the files git tracks, and a file this
  # commit adds is not tracked until it is staged, which happens after the inventory is
  # regenerated. So each listed file that exists and is not tracked is marked intent-to-add
  # first: the inventory then lists what the commit will hold, not what HEAD held.
  # stage_only resets the index to HEAD before staging the list, so the mark does not
  # outlive the commit's bookkeeping. Both paths that regenerate an inventory call this: a
  # plan's own `bump`, and `bump_version.py --assign`, which regenerates it too.
  local p
  for p in "$@"; do
    if [ -e "$p" ] && ! git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
      git add -N -- "$p"
    fi
  done
}

regen_inventory() {
  # $1 = the bundle's generated inventory, $2.. = this commit's files. Rewritten whole by the
  # delivered check_brief.py from the dossier's declarations and the tree, never edited a line
  # at a time, so its target.version is the version home's because the file was recomputed.
  # Idempotent: a second run writes identical bytes, which is what lets a re-run skip nothing.
  local inventory="$1"
  shift
  mark_added "$@"
  "$PY" "$RC/check_brief.py" --apply "$inventory"
}

insert_changelog() {
  # $1 = changelog path, $2 = path to a file holding one released section (its own
  # "## X.Y.Z - DATE" heading included). Inserted directly after "## [Unreleased]" --
  # always the top of the file -- so repeated calls within one script run land each
  # new section directly above the previous one, keeping descending-newest-first order.
  "$PY" - "$1" "$2" <<'PYEOF'
import pathlib, sys
changelog, section_file = sys.argv[1], sys.argv[2]
section = pathlib.Path(section_file).read_text(encoding="utf-8")
p = pathlib.Path(changelog)
text = p.read_text(encoding="utf-8")
marker = "## [Unreleased]\\n"
assert marker in text, f"no ## [Unreleased] heading in {changelog}"
idx = text.index(marker) + len(marker)
p.write_text(text[:idx] + "\\n" + section.rstrip("\\n") + "\\n" + text[idx:], encoding="utf-8")
PYEOF
}

add_unreleased() {
  # $1 = changelog path, $2 = the "### <heading>" to file under, $3 = path to a file holding
  # one bullet. Written inside "## [Unreleased]": appended to that heading's list when the
  # section already has it, else under a new heading at the top of the section. Skipped when
  # the section already holds the same text, so a run that is repeated writes it once.
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import pathlib, sys
changelog, heading, bullet_file = sys.argv[1], sys.argv[2], sys.argv[3]
bullet = pathlib.Path(bullet_file).read_text(encoding="utf-8").rstrip("\\n")
p = pathlib.Path(changelog)
text = p.read_text(encoding="utf-8")
marker = "## [Unreleased]\\n"
assert marker in text, f"no ## [Unreleased] heading in {changelog}"
start = text.index(marker) + len(marker)
end = text.find("\\n## ", start)
end = len(text) if end == -1 else end + 1
section = text[start:end]
if bullet in section:
    print(f"CHANGELOG: entry already under [Unreleased]; not written again")
    sys.exit(0)
head = f"### {heading}\\n"
if head in section:
    at = section.index(head) + len(head)
    nxt = section.find("\\n### ", at)
    if nxt == -1:
        body = section.rstrip("\\n")
        section = body + "\\n" + bullet + section[len(body):]
    else:
        section = section[:nxt].rstrip("\\n") + "\\n" + bullet + "\\n" + section[nxt:]
else:
    section = "\\n" + head + bullet + "\\n" + section
p.write_text(text[:start] + section + text[end:], encoding="utf-8")
PYEOF
}

stage_only() {
  # $1 = progress label, $2.. = this commit's files. `git commit` takes the whole index, so
  # the index must hold this list and nothing else. The clone holds only what this run
  # applied, so a path staged outside the list is a defect in the run itself; refuse, since
  # the clone is deleted at the end and a path set aside there would be lost.
  local step="$1" p listed extra=""
  shift
  listed="$(printf '\n%s' "$@")"$'\n'
  while IFS= read -r p; do
    case "$listed" in
      *$'\n'"$p"$'\n'*) ;;
      *) extra="$extra  $p"$'\n' ;;
    esac
  done < <(git diff --cached --name-only --no-renames)
  if [ -n "$extra" ]; then
    printf '%s: %s refused -- staged, but not in this commit list:\n%s' \
      "$LABEL" "$step" "$extra" >&2
    return 1
  fi
  # Back to HEAD before adding: a removal the apply already staged is then on disk and in
  # the index nowhere, and `git add` refuses a path it can find in neither.
  git reset -q
  git add -- "$@"
}

read_version() {
  # $1 = version-home path. TOML [project].version only, matching COMMITS.md's
  # primary version-home shape.
  grep -o '^version = "[0-9.]*"' "$1" | grep -o '[0-9.]*'
}
"""


#: Keep a Changelog section by conventional type; anything unlisted is a change.
_HEADINGS = {"feat": "Added", "fix": "Fixed", "perf": "Fixed", "docs": "Documentation"}


def _heading(commit: Commit) -> str:
    """The `### ...` a commit's CHANGELOG entry goes under: stated, else by its type."""
    if commit.changelog_heading:
        return commit.changelog_heading.lstrip("#").strip()
    kind = re.match(r"[a-z]+", commit.message.strip())
    return _HEADINGS.get(kind.group(0) if kind else "", "Changed")


def _commit_block(index: int, total: int, commit: Commit) -> str:
    """One commit's block: message + (bookkeeping if bump) + unconditional
    stage/preflight/commit. The SAME shape regardless of index -- nothing here reads
    `index` to decide behavior; it only decides the echoed progress label."""
    n = index + 1
    msg_var = f"MSG_{n}"
    files_var = f"FILES_{n}"
    # The regenerated inventory is part of the bumping commit whether or not the plan
    # listed it: it is the one file the bump itself writes that the author did not.
    inventory = commit.bump.inventory if commit.bump is not None else None
    staged = [
        *commit.files,
        *([inventory] if inventory and inventory not in commit.files else []),
    ]
    files_list = "\n".join(f"  {_sh_str(f)}" for f in staged)
    lines = [
        f'{msg_var}="$TMP_DIR/msg-{n}.txt"',
        f"cat >\"${msg_var}\" {_heredoc('MSG', commit.message)}".rstrip(),
        "",
        f"{files_var}=(",
        files_list,
        ")",
        # Your edits to this commit's paths, brought into the clone (commit_preflight.sh).
        f'pf_apply "$ROOT" "$EXPECTED" "${{{files_var}[@]}}"',
    ]
    if commit.changelog_bullet is not None:
        bullet_var = f"BULLET_{n}"
        lines += [
            f'{bullet_var}="$TMP_DIR/bullet-{n}.md"',
            f"cat >\"${bullet_var}\" {_heredoc('BULLET', commit.changelog_bullet)}".rstrip(),
            "",
            f'add_unreleased CHANGELOG.md {_sh_str(_heading(commit))} "${bullet_var}"',
        ]
        # The entry is this commit's own edit, so it is staged with it. Unstaged, a commit
        # that takes no bump would land without it, and the entry would ride into the
        # next commit that does, or stay in the tree when none follows.
        if "CHANGELOG.md" not in staged:
            lines.append(f'{files_var}+=("CHANGELOG.md")')
    if commit.assign_bump is not None:
        breaking_flag = " --breaking" if commit.breaking else ""
        lines += [
            f'echo "$LABEL: [{n}/{total}] assigning the version bump ({commit.assign_bump}'
            f'{" (breaking)" if commit.breaking else ""}) ..."',
            f'ASSIGN_{n}="$TMP_DIR/assign-{n}.log"',
            f'mark_added "${{{files_var}[@]}}"',
            f'"$PY" "$RC/bump_version.py" --assign {_sh_str(commit.assign_bump)}'
            f'{breaking_flag} --message-file "${msg_var}" | tee "$ASSIGN_{n}"',
            # What the assign wrote is part of this commit, and only the assign knows what
            # that was: it names each file it wrote or regenerated. Its message file is a
            # temp path, never a repo one.
            "while IFS= read -r f; do "
            f'{files_var}+=("$f"); done < <(sed -nE '
            "'s/^  (wrote|regenerated)  ([^/].*)$/\\2/p' "
            f'"$ASSIGN_{n}")',
        ]
    if commit.bump is not None:
        b = commit.bump
        sec_var = f"SEC_{n}"
        brief_args = " ".join(_sh_str(p) for p in b.briefs)
        lines += [
            f'{sec_var}="$TMP_DIR/sec-{n}.md"',
            f"cat >\"${sec_var}\" {_heredoc('SEC', b.changelog_section)}".rstrip(),
            "",
            f'V="$(read_version {_sh_str(b.version_home)})"',
            f'if [ "$V" != {_sh_str(b.old)} ] && [ "$V" != {_sh_str(b.new)} ]; then',
            f'  echo "$LABEL: [{n}/{total}] {_sh_str(b.version_home)} version is neither '
            f'{b.old} nor {b.new}; refusing" >&2',
            "  exit 1",
            "fi",
            f'if [ "$V" = {_sh_str(b.old)} ]; then',
            f'  insert_changelog {_sh_str(b.changelog)} "${sec_var}"',
            f"  bump_version {_sh_str(b.version_home)} {_sh_str(b.old)} {_sh_str(b.new)}"
            + (f" {brief_args}" if brief_args else ""),
            "else",
            f'  echo "$LABEL: [{n}/{total}] bookkeeping already applied; committing it now"',
            "fi",
            # Outside the skip: regenerating is idempotent, and a tree whose version home
            # was already at NEW may still carry an inventory rendered before it moved.
            *(
                [f'regen_inventory {_sh_str(b.inventory)} "${{{files_var}[@]}}"']
                if b.inventory
                else []
            ),
        ]
    lines += [
        f'stage_only "[{n}/{total}]" "${{{files_var}[@]}}"',
        # The commit, in the clone: every hook runs on it, and a hook's autofix is
        # re-staged and the commit retried, to a fixpoint (commit_preflight.sh).
        f'pf_commit "$EDIT" "${msg_var}" "${{{files_var}[@]}}"',
    ]
    return "\n".join(lines)


def render(plan: Plan) -> str:
    """The full runbook text for `plan`. Deterministic: the same `Plan` always
    produces the same script, byte for byte -- a generator, not a drafting aid."""
    n = len(plan.commits)
    header = [
        "#!/usr/bin/env bash",
        f"# Runbook for {plan.label}, generated by package.py commit --"
        " do not hand-edit.",
        "# The series is tried in a clone of this worktree (commit_preflight.sh) and lands",
        "# only if every commit, every hook and the gate pass: all of it or none of it. Your",
        "# checkout is not touched before landing, so a failed run leaves it as it was and the",
        "# same script can simply be run again. A run that LANDED moves HEAD, and the guard",
        "# below then refuses a second one. --dry-run runs the whole trial and lands nothing.",
        "set -euo pipefail",
        (
            f"cd {_sh_str(plan.cwd)}"
            if plan.cwd
            else 'cd "$(git rev-parse --show-toplevel)"'
        ),
        "",
        f"LABEL={_sh_str(plan.label)}",
        f"EXPECTED={_sh_str(plan.head_sha)}",
        '[ "$(git rev-parse HEAD)" = "$EXPECTED" ] || '
        '{ echo "$LABEL: refusing -- HEAD is not $EXPECTED; regenerate the plan" >&2; exit 1; }',
    ]
    if plan.branch:
        header += [
            "",
            'CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"',
            f'[ "$CURRENT_BRANCH" = {_sh_str(plan.branch)} ] || '
            "{ echo \"$LABEL: refusing -- current branch is '$CURRENT_BRANCH', not "
            f'{plan.branch}" >&2; exit 1; }}',
        ]
    try_branch = "rc-try/" + re.sub(r"[^A-Za-z0-9._-]", "-", plan.label)
    header += [
        "",
        "# A runbook lands on the branch of the worktree it runs in, never in the main checkout:",
        "# the main branch moves only by a fast-forward of that branch, afterwards.",
        'if [ "$(git rev-parse --path-format=absolute --git-dir)" = '
        '"$(git rev-parse --path-format=absolute --git-common-dir)" ]; then',
        '  echo "$LABEL: refusing -- run this from a git worktree, not the main checkout" >&2',
        "  exit 2",
        "fi",
        'ORIG="$(git symbolic-ref --short --quiet HEAD)" || '
        '{ echo "$LABEL: refusing -- HEAD is detached; check out the branch to land on" >&2;'
        " exit 1; }",
        f"TRY={_sh_str(try_branch)}",
        'if git rev-parse --verify --quiet "refs/heads/$TRY" >/dev/null; then',
        '  echo "$LABEL: refusing -- $TRY exists from an earlier run; delete it with'
        ' git branch -D $TRY" >&2',
        "  exit 1",
        "fi",
        "",
        "# --no-edit: commit without opening $EDITOR. --dry-run: every commit and the gate run",
        "# in the clone, and nothing lands.",
        "EDIT=-e",
        "DRY=0",
        'for arg in "$@"; do',
        '  case "$arg" in --no-edit) EDIT= ;; --dry-run) DRY=1 ;; esac',
        "done",
        "",
        "if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi",
        "# The delivered scripts import their own lib/; nothing this runs may leave",
        "# __pycache__ in the repo it is committing to.",
        "export PYTHONDONTWRITEBYTECODE=1",
        "# Where racecar's delivered scripts are in THIS repo. Resolved at run time and not",
        "# spelled into each command, because delivery has moved twice -- `scripts/` before",
        "# 0.131.0, then `rc_scripts/`, now `.racecar/scripts/` -- and a runbook is generated",
        "# in one repo for a tree that may be on any of the three.",
        'RC=""',
        "for d in .racecar/scripts rc_scripts scripts; do",
        '  [ -f "$d/check_commit_message.py" ] && { RC="$d"; break; }',
        "done",
        '[ -n "$RC" ] || { echo "$LABEL: racecar scripts not found'
        " (looked in .racecar/scripts, rc_scripts, scripts);"
        " run 'make racecar-sync'\" >&2; exit 1; }",
        "# git commit runs the hooks through whatever `pre-commit` is on PATH, not $PY, so",
        "# the venv's bin goes on PATH whether or not the calling shell activated it.",
        '[ -d .venv/bin ] && PATH="$PWD/.venv/bin:$PATH"',
        'PY="$PWD/$PY"; [ -x "$PY" ] || PY=python3',
        'RC="$PWD/$RC"',
        "",
        'ROOT="$PWD"',
        'TMP_DIR="$(mktemp -d)"',
        "# One definition of how racecar tries a commit: the clone, the hooks, the landing.",
        "# shellcheck source=/dev/null",
        'source "$RC/commit_preflight.sh"',
        _HELPERS.strip("\n"),
        "",
        "LANDED=0",
        "KEEP=0",
        "finish() {",
        "  local status=$?",
        '  cd "$ROOT" || true',
        "  pf_remove",
        '  if [ "$LANDED" != 1 ] && [ "$KEEP" != 1 ]; then',
        '    if [ "$status" = 0 ] && [ "$DRY" = 1 ]; then',
        '      echo "$LABEL: dry run green -- every commit and the gate passed;'
        ' nothing landed (--dry-run)"',
        "    else",
        '      echo "$LABEL: nothing landed -- $ORIG and your files are as they were" >&2',
        "    fi",
        "  fi",
        '  rm -rf "$TMP_DIR"',
        '  exit "$status"',
        "}",
        "trap finish EXIT",
        "",
        "# The trial runs in a clone of this worktree, on $TRY: nothing it does reaches this",
        "# repo until the landing below brings the tried commits back.",
        'pf_clone "$ROOT" "$EXPECTED" "$TRY" "$TMP_DIR"',
        'pf_trunk "$ROOT" "$PY" "$RC" "$ORIG" "$TRY"',
        'cd "$PF_CLONE"',
    ]

    body: list[str] = []
    for i, commit in enumerate(plan.commits):
        body.append(f"\n# {'=' * 85}\n# Commit {i + 1}/{n}\n# {'=' * 85}")
        body.append(_commit_block(i, n, commit))

    footer = [""]
    if plan.gate:
        footer += [
            f'echo "$LABEL: running the gate on $TRY: {plan.gate}"',
            plan.gate,
        ]
    footer += [
        'if [ "$DRY" = 1 ]; then',
        "  exit 0",
        "fi",
        "# Land: bring back the commits every hook and the gate just passed -- fetched from the",
        "# clone, never made again -- and move $ORIG to them only if it is still at $EXPECTED.",
        "# `update-ref` with an old value is a compare-and-swap, so a commit someone else made",
        "# to $ORIG during the run is never overwritten. If $ORIG moved, nothing lands and the",
        "# tried commits are KEPT on $TRY in this repo, to rebase.",
        'TIP="$(git -C "$PF_CLONE" rev-parse HEAD)"',
        'if ! git -C "$ROOT" fetch -q "$PF_CLONE" "refs/heads/$TRY"; then',
        '  echo "$LABEL: could not bring the tried commits back from the clone" >&2',
        "  exit 1",
        "fi",
        'if ! git -C "$ROOT" update-ref "refs/heads/$ORIG" "$TIP" "$EXPECTED"; then',
        "  KEEP=1",
        '  git -C "$ROOT" branch -f "$TRY" "$TIP" || true',
        '  echo "$LABEL: $ORIG moved during the run, so nothing landed. Your commits are'
        ' intact on $TRY: rebase them onto $ORIG, or delete $TRY and re-run." >&2',
        "  exit 1",
        "fi",
        "LANDED=1",
        "# Your index and tree take what landed, for the paths the run committed: your edits",
        "# plus the bookkeeping and autofixes made in the clone. Other paths are untouched.",
        'pf_sync "$ROOT" "$EXPECTED" || true',
        f'echo "$LABEL: all {n} commit(s) landed on $ORIG.'
        ' This script does NOT push -- that stays your call."',
        f'git -C "$ROOT" log -{n} --oneline || true',
        'LEFT="$(git -C "$ROOT" status --short || true)"',
        '[ -z "$LEFT" ] || printf "%s: left uncommitted, in no commit list:\\n%s\\n"'
        ' "$LABEL" "$LEFT" || true',
    ]
    return "\n".join(header + body + footer) + "\n"


if __name__ == "__main__":
    not_a_command()
