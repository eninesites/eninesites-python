"""The term scan: a retired word still cited somewhere in the repo.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A
caller imports what it needs: the tests, the `lexicon` noun's api and the delivered CLI
all reach the same functions instead of loading a script.

Complexity: O(T*F), T = terms, F = files scanned for a citation of one
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from pathlib import Path

from check_docs import ignore_patterns
from lib.lexicon._nodes import (
    CODE_SUFFIXES,
    DOC_SUFFIXES,
    TERM_TREES,
    NomenclatureError,
    _is_command,
    pages,
)
from lib.shared import _frontmatter
from lib.shared._files import repo_files

STATUSES = ("reserved", "retired")

#: The statuses that must name a replacement. A retired string is gone, so a reader needs
#: what replaced it; a reserved word is held, and reservation is excluded from the set that
#: requires one (docs/lexicon/key/status.md).
NEEDS_INSTEAD = frozenset({"retired"})


def instead_disagrees(status: str, instead: str) -> bool:
    """Whether a node's `status` and `instead` break the rule: a status that needs a
    replacement and names none, or a replacement with no status to give it meaning."""
    return (status in NEEDS_INSTEAD and not instead) or (bool(instead) and not status)


CITING_DOCS = {
    Path("arch-python") / "CLI.md",
    Path("CHANGELOG.md"),
}


@dataclass(frozen=True)
class Term:
    """One controlled word, as its node declares it."""

    word: str
    node: str
    status: str
    instead: str


@dataclass(frozen=True)
class Retired:
    """One retired word still cited somewhere in the tree.

    Named for what it IS rather than for being a finding: the grading loop's own record is
    `Finding`, and one module holding two classes by that name is drift.
    """

    path: str
    line: int
    retired: str
    replacement: str

    def where(self) -> str:
        """The file and line the word is cited at, as a finding's subject."""
        return f"{self.path}:{self.line}"

    def message(self) -> str:
        """What is wrong there, as a finding's message."""
        return f"retired term {self.retired!r} — use {self.replacement!r}"

    def render(self) -> str:
        """Format as one audit line, matching racecar's other checkers."""
        return (
            f"  Major    {self.path}:{self.line}  retired term "
            f"{self.retired!r} — use {self.replacement!r}"
        )


def raw_kind(path: pathlib.Path) -> str:
    """The `kind:` a node declares, read without parsing it as a term.

    Silent on an undecodable file: this runs BEFORE the term parse, and raising here would
    replace the caller's own "not valid UTF-8" NomenclatureError with a bare UnicodeDecodeError.
    A file this cannot read is one the caller is about to report properly.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""
    for line in (_frontmatter.block(text) or "").splitlines():
        if line.startswith("kind:"):
            return line.split(":", 1)[1].strip()
    return ""


def read_terms(root: Path) -> list[Term]:
    """Every term node in either tree, as declared. Empty when the repo has no trees.

    A node that declares `status:` must also declare `instead:`, and vice versa: a
    retirement with no replacement tells a reader what to stop writing and not what to
    write, and a replacement with no status is a rule that never fires. Both are hard
    errors rather than skipped nodes, for the reason this whole file exists.
    """
    terms: list[Term] = []
    for tree in TERM_TREES:
        directory = root / tree
        if not directory.is_dir():
            continue
        for path, _ in pages(directory):
            # NOT a blanket README skip. A noun's README can be the only node that
            # defines a word -- `host`, `config`. An index or a schema carries
            # no word.
            if raw_kind(path) in {"index", "schema"}:
                continue
            if path.name == "README.md" and not raw_kind(path):
                continue
            # The nounspace shares this directory with the word trees and is told apart
            # by `kind:`, which is what the ontology is for. A `command` carries
            # `command:` and no `name:` -- what a verb MEANS is the word node's business
            # and lives once, while the command's usage is per-noun.
            head = raw_kind(path)
            # A COMMAND node is excluded: `graph/check.md` is an address, and what `check`
            # MEANS lives once at `verb/check.md`. A noun node is NOT excluded:
            # `host/README.md` is the only node that defines `host`, so skipping nouns
            # would leave the word with no node while every gate stays green.
            if head == "verb" and _is_command(path, directory):
                continue
            where = str(path.relative_to(root))
            try:
                raw = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise NomenclatureError(f"{where}: not valid UTF-8 ({exc})") from exc
            meta = _frontmatter.load(raw)
            name = meta.get("name")
            if not name:
                raise NomenclatureError(f"{where}: term node declares no `name`")
            # YAML reads bare `yes`, `no`, `on` and `off` as BOOLEANS. `name: yes` therefore
            # silently becomes `True`, the retirement of `--yes` matches nothing, and
            # the gate reports OK. Quote it, and say so.
            if not isinstance(name, str):
                raise NomenclatureError(
                    f"{where}: `name: {name}` parsed as {type(name).__name__}, not a string — "
                    "YAML reads bare yes/no/on/off as booleans. Quote it."
                )
            status, instead = meta.get("status", ""), meta.get("instead", "")
            if status and status not in STATUSES:
                raise NomenclatureError(
                    f"{where}: status {status!r} is not one of {STATUSES}. Absence "
                    "means canon; only an exception is declared."
                )
            if instead_disagrees(status, instead):
                raise NomenclatureError(
                    f"{where}: a retirement names its replacement and a replacement needs a "
                    f"status (status={status!r}, instead={instead!r}). A retirement with no "
                    "replacement says what to stop writing but not what to write; a "
                    "replacement with no status is a rule that never fires."
                )
            # A flag's WORD carries its dashes: `--yes` is retired, the English word "yes"
            # is not. Keyed on the node's declared kind, never on which directory it sits
            # in.
            word = f"--{name}" if head == "param" else name
            terms.append(Term(word, where, status, instead))
    return terms


def retirements(terms: list[Term]) -> dict[str, str]:
    """The scannable rules: retired word -> its replacement. Reserved words excluded."""
    return {t.word: t.instead for t in terms if t.status == "retired"}


def _pattern(term: str) -> re.Pattern[str]:
    """Match `term` as a whole word, or exactly when it is a flag.

    A flag is matched literally and bounded on the right only: `--check` must not fire on
    `--check-something`, and there is no left word boundary to assert because `-` is not a
    word character.
    """
    if term.startswith("-"):
        return re.compile(re.escape(term) + r"(?![\w-])")
    # Each word is escaped SEPARATELY and rejoined on `\s+`. Escaping the whole term
    # after substituting the separator would escape the backslash in `\s+` and the
    # pattern would then only match a literal `\s+` — which is to say a multi-word term
    # would silently never match, and its retirement would be unenforced while reading
    # as enforced.
    spaced = r"\s+".join(re.escape(word) for word in term.split())
    return re.compile(r"(?<![\w-])" + spaced + r"(?![\w-])", re.I)


def _needle(term: str) -> str:
    r"""The lowercase literal that MUST appear in a text for `_pattern(term)` to match.

    A necessary condition, not a sufficient one — which is the whole point. `_pattern`
    wraps the term in lookarounds and joins multi-word terms on `\s+`, so the first word
    always appears verbatim; a flag appears whole. Testing `needle in text.lower()`
    therefore never rejects a real match, and rejects almost every non-match for the price
    of a C substring scan instead of a regex pass over the file.

    Without it every term runs against every file, and the regex engine cannot know that
    `lexicon` is absent without walking the text. `str.__contains__` can.
    """
    return term.split()[0].lower()


def _walk(root: Path) -> list[Path]:
    """Every file this checker grades, from the ONE shared walk.

    `repo_files` skips hidden directories, `__pycache__`, everything `.gitignore` names,
    and checked-out submodules; none of that is this checker's to know, and every
    private copy of the rule is one that misses the next addition to it.

    The project's own `ignore-paths` declaration is applied here rather than inside
    `repo_files`, matching `check_doc_graph.in_scope`: the shared walk does the mechanical
    skipping, and the caller applies what the project declared. `drafts/` is covered by
    that declaration.

    Cached because several callers ask the same question.
    """
    if root in _WALK_CACHE:
        return _WALK_CACHE[root]
    declared = ignore_patterns(root)
    out = [
        path
        for path in repo_files(root, "*")
        if path.is_file()
        and not any(r.search(path.relative_to(root).as_posix()) for r in declared)
    ]
    _WALK_CACHE[root] = out
    return out


_WALK_CACHE: dict[Path, list[Path]] = {}

_SKILL_CACHE: dict[Path, list[Path]] = {}


def skill_dirs(root: Path) -> list[Path]:
    """Every directory carrying a SKILL.md, sorted. That is what a skill IS on disk."""
    if root not in _SKILL_CACHE:
        _SKILL_CACHE[root] = sorted(
            {p.parent for p in _walk(root) if p.name == "SKILL.md"}
        )
    return _SKILL_CACHE[root]


_OWNED_CACHE: dict[Path, dict[Path, list[Path]]] = {}


class _TrieNode:
    """One path segment's worth of trie. `skill` is set only where a skill dir ends."""

    __slots__ = ("children", "skill")

    def __init__(self) -> None:
        self.children: dict[str, "_TrieNode"] = {}
        self.skill: Path | None = None


def _owned(root: Path) -> dict[Path, list[Path]]:
    """Every skill directory to the files it OWNS: its own tree, not its children's skills.

    Ownership is "the deepest skill directory above this file", which is a property of the
    file and is therefore answered once for the whole tree. Asking it the other way round --
    per skill, filter the walk, and for each file test `any(other in file.parents)` -- is the
    same question asked `skills x files x nested-skills` times.

    Files under no skill directory belong to nobody and are not returned.

    This is longest-prefix match, the same rule an IP routing table applies to pick its
    most specific route, in its trie-backed form. A skill directory's `.parts` are
    inserted as one path down a trie keyed by path segment, terminal nodes marked with
    the skill they close; placing a file walks its OWN `.parts` down that same trie,
    remembering the deepest skill-marked node crossed.
    That is a single O(depth) descent per file, not a scan of every directory.
    """
    if root in _OWNED_CACHE:
        return _OWNED_CACHE[root]
    directories = skill_dirs(root)
    trie = _TrieNode()
    for directory in directories:
        node = trie
        for part in directory.parts:
            node = node.children.setdefault(part, _TrieNode())
        node.skill = directory
    by_skill: dict[Path, list[Path]] = {d: [] for d in directories}
    for path in _walk(root):
        node = trie
        deepest: Path | None = None
        for part in path.parts:
            nxt = node.children.get(part)
            if nxt is None:
                break
            node = nxt
            if node.skill is not None:
                deepest = node.skill
        if deepest is not None:
            by_skill[deepest].append(path)
    _OWNED_CACHE[root] = by_skill
    return by_skill


def _files(directory: Path, root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """A skill's own files of the given kinds: its own tree, not its children's skills."""
    return sorted(p for p in _owned(root).get(directory, []) if p.suffix in suffixes)


def _docs(directory: Path, root: Path) -> list[Path]:
    """The markdown a skill is made of."""
    return _files(directory, root, DOC_SUFFIXES)


def _exempt(relative: Path) -> bool:
    """Whether a document may name a retired word: it declares one, or it records one."""
    return relative in CITING_DOCS or any(
        tree == relative or tree in relative.parents for tree in TERM_TREES
    )


def scan(
    root: Path, terms: list[Term], retired: dict[str, str]
) -> tuple[dict[str, dict[str, list[str]]], list[Retired]]:
    """Return `(skill -> {consumes, governs}, found)`. Reverse indexes derive later."""
    compiled = [(t.word, _needle(t.word), _pattern(t.word)) for t in terms]
    condemned = [(w, _needle(w), _pattern(w)) for w in retired]
    used: dict[str, dict[str, list[str]]] = {}
    found: list[Retired] = []
    # One read per file. A skill's tree overlaps its neighbours' only through shared
    # parents, but the same file is reached by several relations below, and reading it
    # twice to answer two questions about the same bytes is the cost this cache removes.
    texts: dict[Path, tuple[str, str]] = {}

    def read(path: Path) -> tuple[str, str]:
        """`(text, text.lower())`. The lowered copy is made once and prefiltered against."""
        if path not in texts:
            body = path.read_text(encoding="utf-8", errors="replace")
            texts[path] = (body, body.lower())
        return texts[path]

    def present(
        entries: list[tuple[str, str, re.Pattern[str]]],
        text: str,
        low: str,
        found: set[str] = frozenset(),  # type: ignore[assignment]
    ) -> set[str]:
        """Which terms this text names, beyond those already found.

        `found` is not an optimisation detail leaking out -- the caller is accumulating a
        SET, so a term already in it cannot change the answer no matter how many more files
        name it. Skipping those is the difference between testing every term against every
        file and testing each term until it lands, and the common terms land in the first
        file of a skill.
        """
        return {
            w
            for w, needle, pattern in entries
            if w not in found and needle in low and pattern.search(text)
        }

    for directory in skill_dirs(root):
        name = str(directory.relative_to(root)) or "."
        consumes: set[str] = set()
        governs: set[str] = set()
        for doc in _docs(directory, root):
            text, low = read(doc)
            consumes |= present(compiled, text, low, consumes)
            if _exempt(doc.relative_to(root)):
                continue
            # Only a term the whole document names can be on one of its lines, so the
            # per-line walk runs for the retired words that are actually here -- which is
            # normally none of them, and the loop does not run at all.
            for word in present(condemned, text, low):
                pattern = _pattern(word)
                for number, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        found.append(
                            Retired(
                                str(doc.relative_to(root)), number, word, retired[word]
                            )
                        )
        for source in _files(directory, root, CODE_SUFFIXES):
            text, low = read(source)
            governs |= present(compiled, text, low, governs)
        used[name] = {"consumes": sorted(consumes), "governs": sorted(governs)}
    return used, found
