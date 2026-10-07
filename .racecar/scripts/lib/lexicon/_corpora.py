"""The lexicon: one home for the union of every directory that holds one.

**What a racecar script reads as the lexicon is a `Lexicon`, never a folder.** A repo's
lexicon is the union of zero, one or more directories each holding a lexicon: its own
`docs/lexicon`, the copy racecar delivered (`.racecar/docs/lexicon`, or `docs/rc_lexicon` in
racecar, which authors it), any declared at `[tool.racecar.lexicon] corpora`, and an explicit
`--canon`. `lexicon_corpora(root)` builds it once, where a command reads its arguments, and
every reader is handed that value. How it is built can change; a reader works on whatever
it is handed, from no entries at all to every file in every home.

When each reader was handed a folder and joined the homes itself, each joined them its own
way: one read the delivered params twice, one read the repo's own ontology alone and so
skipped the lexicon check on a repo whose kinds are all delivered. A reader handed a
`Lexicon` has no folder to walk.

A `Lexicon` is a list of entries, one per file in every home, each
`(directory relative to the repo, filename, kind, pnode, origin, position)`, with the
repo root to open them from and the repo's own home for a writer to write into. `kind` and
`pnode` are read from each node's frontmatter once, here. A file with no readable
frontmatter is an entry with an empty kind and pnode; the check that grades nodes says so.

Complexity: O(F), F = files in every home (one frontmatter parse per node)
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from lib.shared import _constants, _frontmatter
from lib.shared._root import same_repository

# The two corpora that JOIN, in resolution order. `docs/lexicon` is the repo's own words;
# `.racecar/docs/lexicon` is the half racecar DELIVERS, at the same relative position in
# every governed repo. Each is ignored when it is not on disk.
#
# Hardcoded rather than declared because there is nothing for a declaration to decide --
# every governed repo has these two or fewer -- and because a repo that had to declare the
# delivered tree before it was read would spend the whole window between the sync and the
# edit reporting every node of a delivered kind as declaring a kind nothing defines.
# Anything BEYOND the pair is declared, at `[tool.racecar.lexicon] corpora` in
# pyproject.toml, which is where a project's own bindings already live.
CORPUS_REL = Path("docs") / "lexicon"

# The provenance stamps racecar writes at the boundary root: git's own tree object id for
# each tree it delivered, ONE PER TREE. Not one umbrella sha over `.racecar/` -- the two
# halves are delivered by different rules and answer different questions, and a single
# number could only ever say "something under here changed", which names nothing and is
# repaired by nothing.
#
# What they buy is ONE question per tree: are these still the bytes racecar shipped? A
# delivered kind node is read as DATA, and a `required:` list edited by hand in the
# delivered half changes what every gate in the repo demands while still looking like canon.
# A delivered CHECKER is worse -- it IS the gate. The stamps do not prevent either; nothing
# in a repo can. They make the tree say so.
#
# Absent stamp means trust it: a tree delivered without a stamp, or placed by hand, is
# not evidence of tampering. A stamp that DISAGREES is, and the lexicon's disagreement
# drops the delivered corpus from the join -- ignored, not an error, because a mangled
# delivery is the author's own doing and it must not take the repo's own lexicon down with
# it.
#
# Read from `lib.shared._constants`, which is the DELIVERED mirror of
# `racecar.lib.delivery.record` -- the side that writes them. This file cannot import the
# library and does not need to: the mirror sits beside it in the same delivered directory,
# and `find_repo_root` already comes from there.
DELIVERY_ROOT = _constants.DELIVERY_ROOT
LEXICON_STAMP_REL = _constants.LEXICON_STAMP_REL
SCRIPTS_STAMP_REL = _constants.SCRIPTS_STAMP_REL

# Paths already reported as mismatched, so a join that runs once per corpus root does not
# print the same line ten times.
_STAMP_REPORTED: set[str] = set()


class LexiconError(Exception):
    """The lexicon cannot be graded at all — a broken run, not a finding."""


#: Where a home came from. The order of a `Lexicon`'s homes is the precedence: a declared
#: home, then the repo's own, then an explicit `--canon`, then the copy racecar delivered.
#: `AUTHORED` is that copy at the position racecar writes it (`docs/rc_lexicon`), `DELIVERED`
#: at the position an adopter receives it (`.racecar/docs/lexicon`).
CUSTOM, OWN, CANON, AUTHORED, DELIVERED = (
    "custom",
    "own",
    "canon",
    "authored",
    "delivered",
)

#: The origins that are canon wherever they appear: what racecar wrote, or a caller named.
CANON_ORIGINS = frozenset({CANON, AUTHORED, DELIVERED})


class Corpus(NamedTuple):
    """One home of the union: a directory holding a lexicon, and where it came from."""

    path: Path
    origin: str


def _pyproject_of(home: Path) -> Path | None:
    """The nearest `pyproject.toml` at or above `home`, or None.

    Walked rather than taken from `find_repo_root`, because this must answer for a corpus
    that is not in a git checkout at all -- a fixture, or a tree being scaffolded.
    """
    for parent in [home.resolve(), *home.resolve().parents]:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _declared_corpora(home: Path) -> list[Path]:
    """The extra corpora `[tool.racecar.lexicon] corpora` names, as paths under the root
    that declares them. Absent table, absent key and a non-list value all mean none.

    Hand-parsed, not `tomllib`: this module is delivered into repos running Python
    versions racecar does not pick, and the one value it wants is a list of strings under
    a named table. A shape it cannot read yields no corpora, which is the same answer as
    declaring none.
    """
    pyproject = _pyproject_of(home)
    if pyproject is None:
        return []
    root = pyproject.parent
    out: list[Path] = []
    in_table = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_table = stripped.rstrip() == "[tool.racecar.lexicon]"
            continue
        if not in_table or not stripped.startswith("corpora"):
            continue
        _, _, value = stripped.partition("=")
        for item in re.findall(r"""["']([^"']+)["']""", value):
            out.append(root / item.rstrip("/"))
    return out


def _is_corpus_root(home: Path) -> bool:
    """Whether `home` is a corpus ROOT (`.../docs/lexicon`) rather than a node inside one.

    The guard that keeps the join from firing on a directory that merely sits under a
    corpus. `docs/lexicon/graph/` holds a CLI noun, and walking up from it would find the
    delivered corpus and fold another repo's kinds into one noun's ontology -- an ontology
    assembled out of position rather than out of a declaration.
    """
    return home.name == CORPUS_REL.name and home.parent.name == CORPUS_REL.parent.name


def _blob_sha(path: Path) -> bytes:
    """git's blob object id for one file, raw. `sha1("blob <len>\\0" + bytes)`."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).digest()


def is_bytecode(name: str) -> bool:
    """Whether `name` is something the interpreter writes beside a delivered module.

    `__pycache__/` and `*.pyc` / `*.pyo`: what `templates/classic/gitignore` ignores, so what
    git leaves out of the tree `tree_sha` has to agree with. The ONE statement of it, because
    it has two readers that must agree: `tree_sha` leaves these out of the hash, and sync
    deletes them from `.racecar/` before it runs. A delete that removed one set while the
    hash skipped another would leave the stamp wrong for whatever fell between them.
    """
    return name == "__pycache__" or name.endswith((".pyc", ".pyo"))


def tree_sha(root: Path) -> str:
    """git's tree object id for a directory, computed without git and without writing.

    **THE AUTHORED HOME.** Sync (`racecar.lib.delivery.deliver`) loads this rather than
    copying it, the same direction `racecar.lexicon.lib._graph` states for the tuple list: a
    delivered file cannot import the library, so the library imports the delivered file and
    there is one implementation. Two spellings of a hash is how a stamp comes to disagree
    with itself on a tree nobody touched -- an accusation of tampering that the tool itself
    manufactured.

    The whole point of matching git's own algorithm rather than inventing a digest is that
    the recorded value is reproducible by hand: `git rev-parse <ref>:.racecar/scripts` in the
    repo that received it prints the same forty characters. A checksum of our own devising
    would be a number only this code can explain.

    Entries sort by name with a directory sorted as `name/` -- git's rule, and getting it
    wrong yields a plausible sha that matches nothing. Mode is `100644` or `100755` off the
    execute bit; symlinks and submodules cannot appear in a delivered corpus of markdown.

    Bytecode is left out (`is_bytecode`), because git leaves it out. Running any delivered
    checker writes `.racecar/scripts/lib/**/__pycache__/`, and hashing it would make
    every later sync rewrite a stamp nothing changed, and write one that matches no
    commit.
    """
    entries: list[tuple[bytes, bytes, bytes]] = []
    for child in sorted(
        (p for p in root.iterdir() if not is_bytecode(p.name)),
        key=lambda p: p.name + ("/" if p.is_dir() else ""),
    ):
        if child.is_dir():
            entries.append(
                (b"40000", child.name.encode(), bytes.fromhex(tree_sha(child)))
            )
        else:
            mode = b"100755" if child.stat().st_mode & 0o111 else b"100644"
            entries.append((mode, child.name.encode(), _blob_sha(child)))
    body = b"".join(mode + b" " + name + b"\0" + sha for mode, name, sha in entries)
    return hashlib.sha1(
        b"tree %d\0" % len(body) + body, usedforsecurity=False
    ).hexdigest()


def _delivered_is_intact(delivery_root: Path, corpus: Path) -> bool:
    """Whether the delivered corpus still holds the bytes the stamp says racecar delivered.

    True when there is no stamp, when it is empty, and when it agrees. False only when a
    stamp exists and names a different tree -- and that False drops the delivered corpus
    from the join rather than raising, with one line on stderr so the drop is not silent.
    A silent skip is the shape of every checker that passes because it read nothing.
    """
    stamp = delivery_root / LEXICON_STAMP_REL
    if not stamp.is_file():
        return True
    recorded = stamp.read_text(encoding="utf-8").split()
    if not recorded or recorded[0] == tree_sha(corpus):
        return True
    key = str(corpus)
    if key not in _STAMP_REPORTED:
        _STAMP_REPORTED.add(key)
        print(
            f"lexicon: {corpus} does not match the tree {stamp} records "
            f"({recorded[0][:12]}) -- the delivered corpus is edited, and it is left OUT "
            "of the join. Re-run the sync to restore it.",
            file=sys.stderr,
        )
    return False


#: The delivered corpus has TWO positions, and they are the same corpus seen from each end of
#: the delivery. `docs/rc_lexicon` is where it is AUTHORED, which is the position racecar
#: itself has and no adopter does; `.racecar/docs/lexicon` is where it LANDS. Both are read
#: here so racecar joins its own canon by POSITION, exactly as an adopter does, and therefore
#: at the same precedence. Declaring it instead (`[tool.racecar.lexicon] corpora`) would
#: put it on the CUSTOM leg, which outranks the repo's own corpus -- the opposite order
#: from the one racecar ships.
#:
#: **AUTHORED FIRST, and that order is the whole of it.** A repo can hold both at once:
#: syncing racecar into itself is allowed, and the manifest's document rows write
#: `.racecar/docs/lexicon/` when it happens. Read received-first, the copy would shadow the
#: file racecar authors -- editing `docs/rc_lexicon/ontology/verb.md` would then change
#: nothing until the next sync, and the provenance stamp would agree because the bytes matched
#: when it was written. Two homes for one fact with the drift invisible, which is the failure
#: this repo exists to catch. Authored beats received, the same way a declared corpus beats
#: the repo's own and the repo's own beats canon: the more specific statement wins.
DELIVERED_RELS = (Path("docs") / "rc_lexicon", Path(DELIVERY_ROOT) / CORPUS_REL)


def _delivered_corpus(own_home: Path) -> Corpus | None:
    """The delivered copy beside the repo's own home, at either of its two positions, or None
    when neither is there.

    Looked for in the repo that holds `own_home` (`own_home` is `<repo>/docs/lexicon`) and
    nowhere above it, so a checkout nested inside another repo never joins that repo's copy.
    Authored first: racecar holds `docs/rc_lexicon` and may also hold a synced
    `.racecar/docs/lexicon`, and the file racecar writes wins over the copy it received.

    A copy whose provenance stamp disagrees with it is not returned at all -- it is dropped
    from the join rather than trusted, and `_delivered_is_intact` says so on stderr.
    """
    repo = own_home.parent.parent
    for rel in DELIVERED_RELS:
        candidate = repo / rel
        if candidate.is_dir():
            if not _delivered_is_intact(repo / DELIVERY_ROOT, candidate):
                return None
            return Corpus(
                candidate, AUTHORED if rel == DELIVERED_RELS[0] else DELIVERED
            )
    return None


class Entry(NamedTuple):
    """One file of the lexicon. Every field is a string or a tuple of strings: hashable."""

    directory: str
    """The file's directory, relative to the repo root (absolute for a `--canon` outside it)."""
    filename: str
    kind: str
    """The node's `kind:`, read once from its frontmatter; empty for a file that declares none."""
    pnode: tuple[str, ...]
    """The node's `pnode:` entries, as written."""
    origin: str
    """Which home the file came from: `OWN`, `DELIVERED`, `AUTHORED`, `CANON` or `CUSTOM`."""
    position: str
    """The file's place within its home, posix: `param/json.md`, `README.md`."""

    @property
    def parts(self) -> tuple[str, ...]:
        """The directories between the home and the file: a noun's chain."""
        return PurePosixPath(self.position).parent.parts

    @property
    def stem(self) -> str:
        return PurePosixPath(self.filename).stem


@dataclass(frozen=True)
class Lexicon:
    """The union: every file of every home, in precedence order, and where to open them."""

    root: Path
    """The repo root every entry's `directory` is relative to."""
    own: Path
    """The repo's own home. A writer writes here; it is a home of the union when it exists."""
    homes: tuple[Corpus, ...]
    """The directories that joined, in precedence order."""
    entries: tuple[Entry, ...]
    """Every file of every home, home by home in precedence order, path order within one."""

    def path(self, entry: Entry) -> Path:
        """Where `entry`'s file is on disk."""
        return self.root / entry.directory / entry.filename

    def nodes(
        self,
        *,
        origins: frozenset[str] | None = None,
        kind: str | None = None,
        under: str = "",
    ) -> list[Entry]:
        """The markdown entries, kept by origin, by kind and by the directory they sit under.

        `under` is a position prefix (`"param"`, `"graph/ontology"`); empty keeps every one.
        Saying which part of the union a reader wants is the reader's job, where it calls.
        """
        prefix = f"{under.strip('/')}/" if under.strip("/") else ""
        return [
            entry
            for entry in self.entries
            if entry.filename.endswith(".md")
            and (origins is None or entry.origin in origins)
            and (kind is None or entry.kind == kind)
            and entry.position.startswith(prefix)
        ]

    def at(self, position: str, origin: str | None = None) -> Entry | None:
        """The entry at `position` that wins (the first home that holds it), or the one from
        the home of `origin`."""
        return next(
            (
                entry
                for entry in self.entries
                if entry.position == position and origin in (None, entry.origin)
            ),
            None,
        )

    def entry_of(self, path: Path) -> Entry | None:
        """The entry for a file of the union, or None for a file that is not one."""
        return next((entry for entry in self.entries if self.path(entry) == path), None)

    def find(self, position: str) -> Path | None:
        """The file at `position` as the union resolves it: the first home that holds it.

        `param/json.md` is the repo's own when it has one, the delivered copy otherwise.
        """
        entry = self.at(position)
        return None if entry is None else self.path(entry)

    def is_canon(self, entry: Entry) -> bool:
        """Whether `entry` is canon, read off where it came from: racecar's copy (authored or
        delivered) or an explicit `--canon`. Anything else is the repo's own."""
        return entry.origin in CANON_ORIGINS


def _homes(root: Path, own: Path | None, canon: Path | None) -> list[Corpus]:
    """The directories that join, in precedence order, each existing, each once.

    The order is the precedence rule, and everything downstream inherits it:

        custom  >  the repo's own  >  an explicit --canon  >  the delivered copy

    Custom first: a corpus a project went out of its way to declare at
    `[tool.racecar.lexicon] corpora` is the most specific statement in the repo. The repo's
    own next. Canon after it, as the fallback: a delivered kind supplies what nothing local
    says, and yields wherever something local does. A repo CAN narrow a delivered kind's
    `required:`, and both kind readers print which copy was shadowed, so a quieter check is
    visible rather than silent.

    The delivered and declared homes join only when the repo's own home sits where a repo's
    lexicon sits (`docs/lexicon`): an own home named elsewhere (`--data`) is read alone.
    """
    own_home = own if own is not None else root / CORPUS_REL
    ordered: list[Corpus] = []
    at_position = own is None or _is_corpus_root(own_home)
    if at_position:
        ordered += [Corpus(path, CUSTOM) for path in _declared_corpora(own_home)]
    ordered.append(Corpus(own_home, OWN))
    if canon is not None:
        ordered.append(Corpus(canon / CORPUS_REL, CANON))
    if at_position:
        delivered = _delivered_corpus(own_home)
        if delivered is not None:
            ordered.append(delivered)
    out: list[Corpus] = []
    seen: set[Path] = set()
    for candidate in ordered:
        if candidate.path.is_dir() and candidate.path.resolve() not in seen:
            seen.add(candidate.path.resolve())
            out.append(candidate)
    return out


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()


def _entries(root: Path, home: Corpus) -> list[Entry]:
    out: list[Entry] = []
    for path in sorted(p for p in home.path.rglob("*") if p.is_file()):
        if is_bytecode(path.name) or any(is_bytecode(part) for part in path.parts):
            continue
        meta = _frontmatter.load(path) if path.suffix == ".md" else {}
        pnode = meta.get("pnode") or []
        out.append(
            Entry(
                directory=_relative(path.parent, root),
                filename=path.name,
                kind=str(meta.get("kind") or ""),
                pnode=tuple(
                    str(p) for p in (pnode if isinstance(pnode, list) else [pnode])
                ),
                origin=home.origin,
                position=path.relative_to(home.path).as_posix(),
            )
        )
    return out


def lexicon_corpora(
    root: Path, own: Path | None = None, canon: Path | None = None
) -> Lexicon:
    """**The one home of the lexicon.** The union of every home `root` has, as one value.

    `own` names the repo's own home where it is not `docs/lexicon` (the CLI's `--data`);
    `canon` is an explicit `--canon` repo, whose lexicon joins as a home tagged canon. A home
    that is not on disk is not joined, and a repo with none yields a `Lexicon` with no
    entries, which every reader treats as nothing to read.

    The checks live here, where the lexicon is loaded, so that reading it never needs one:

    - an explicit `--canon` that holds no lexicon is refused (`LexiconError`), because a
      caller who names a directory asserts the canon is there, and checking something else
      instead is how a run reports OK about a tree it never read;
    - a `--canon` that is another checkout of THIS repository (a git worktree of racecar and
      its main checkout) is this repo, so it adds no home;
    - a delivered copy whose stamp disagrees is left out (`_delivered_is_intact`).
    """
    if canon is not None:
        if not (canon / CORPUS_REL).is_dir():
            raise LexiconError(f"--canon {canon.resolve()} carries no {CORPUS_REL}")
        if same_repository(canon.resolve(), root):
            # Another checkout of this repository (a worktree and its main checkout): its
            # lexicon is this one's, so it adds no home.
            canon = None
    homes = _homes(root, own, canon)
    entries = [entry for home in homes for entry in _entries(root, home)]
    own_home = own if own is not None else root / CORPUS_REL
    return Lexicon(root, own_home, tuple(homes), tuple(entries))


def home_directories(directory: Path) -> list[Path]:
    """The same directory in every home of the union, in precedence order, when `directory`
    sits directly in a repo's own home (`docs/lexicon/ontology`); otherwise `directory` alone.

    For the declaration readers (ontology, topology) that take a directory because they also
    read corpora that are not a lexicon (`architecture/`). Asking here keeps which homes
    exist, and in which order, in this one home. One level only: `docs/lexicon/graph/ontology`
    is a CLI noun named `ontology` inside the lexicon, not a declaration, and joining from it
    would fold another home's kinds into one noun.
    """
    if not _is_corpus_root(directory.parent):
        return [directory]
    lexicon = lexicon_corpora(directory.parent.parent.parent, own=directory.parent)
    found = [
        home.path / directory.name
        for home in lexicon.homes
        if (home.path / directory.name).is_dir()
    ]
    return found or [directory]
