"""Build a graph from a body of source material.

`check`/`graph`/`perimeter` (this package's other three verbs) all read a tree that
already exists — racecar's own `architecture/` corpus, no `--data`. This module is the
verb that builds one, so the build has a place for a gate.

**Scope — the mechanical half only, not the converters.** Docx/pptx/pdf/xlsx-to-markdown
conversion and e-signature audit-trail extraction need new parsing dependencies in a
standards repo, a separate owner-authorized decision, and are deliberately NOT built
here. `build()` restructures
whatever is at `--data` into the shape `GRAPH.md` describes and classifies what it can
WITHOUT a converter: a markdown source already carries its own content, so it is read
directly; anything else becomes a `document`-kind residue node — the original preserved
verbatim under `files/`, a stub rendering recording that no converter exists for its
format. That residue is not a defect to hide. Per `GRAPH.md` §Coverage: "the residue is
the point" — an honest 80% unmapped fraction for a pile of raw PDFs is exactly what
`unmapped_fraction` exists to say out loud, and it is what tells an operator converters
are the next real gap rather than something this verb quietly worked around.

**Classification, absent a converter.** `racecar.graph.ontology`'s `check()`/`derive()`
read markdown frontmatter — `sample()` walks `.md` files under a corpus and
scores their declared or inferred `kind` against an ontology. `build()` reuses that
verb rather than re-deriving it: sources that are already markdown with frontmatter get
scored for real; everything else has no frontmatter to score, so it is honestly
unclassified rather than guessed at. Per `GRAPH.md` §Vocabulary, "a source is a node of
kind `document`" — that is the one true thing `build()` can say about a raw source
without reading its content, and it is what an unclassified node is stamped with.

**Ambiguity goes to a human.** Two sources that would file to the same
`<category>/<document>/` path — same slugged stem, same classification — are a naming
collision, not a coin flip: the second is suffixed to avoid clobbering the first, and
both are named in `BuildResult.collisions` for a person to resolve, the same policy
`GRAPH.md` states for filename collisions: recorded and reported rather than
auto-resolved.

Part of `lib.graph`; `scripts/graph.py` parses the command line and calls `main`. `run` is
the build and returns its `BuildResult`; `renderer.text` is how that record reads.

Complexity: O(S) in source files copied, plus one ontology derivation.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import time
from pathlib import Path
from typing import Any

import yaml
from lib import not_a_command
from lib.graph.renderer import text
from lib.ontology import _kinds
from lib.shared import _frontmatter
from lib.shared._as_json import run_json

# Never named from the source's own filename (`GRAPH.md` §Naming: "filenames lie").
# Absent a converter there is nothing else to name a raw source FROM, so the slugged
# stem is used and every such node is stamped `status: unknown` — the honest signal
# that this name is provisional, not a claim that it is correct.
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_UNCATEGORIZED = "uncategorized"
_DOCUMENT_KIND = "document"
_LOCK_NAME = ".graph-build.lock"
_ONTOLOGY_FILENAME = "ontology.yaml"


def _slug(stem: str) -> str:
    slugged = _SLUG_RE.sub("-", stem.lower()).strip("-")
    return slugged or "untitled"


@dataclasses.dataclass(frozen=True)
class Collision:
    """Two sources that would file to one `<category>/<document>/` path.

    Reported, never silently resolved by overwrite — `GRAPH.md` §Disciplines states
    this exact policy for filename collisions on a real corpus.
    """

    path: str  # the "<category>/<document>" slug both sources produced
    sources: tuple[Path, ...]


@dataclasses.dataclass(frozen=True)
class BuildResult:
    """What `build()` did, and how completely — coverage is a first-class output.

    `sources_in` and `sources_indexed` are the reconciliation `GRAPH.md` §Disciplines
    requires: a tool that silently indexes less than it found must not read like one
    that had less to find, so the two counts are always both reported and always equal
    on success — a source `build()` cannot write a node for is a hard failure, not a
    silent drop.
    """

    root: Path
    manifest: Path
    sources_in: int
    sources_indexed: int
    unmapped_fraction: float
    by_kind: dict[str, int]
    collisions: tuple[Collision, ...]
    backup: Path | None


def _walk_sources(data: Path) -> list[Path]:
    """Every regular file under `data`, recursively, sorted.

    `rglob`, never a shallow `glob` — a shallow glob silently misses files inside an
    archive subfolder and reports success.
    Sorted so the same corpus indexes in the same order twice.
    """
    return sorted(
        p for p in data.rglob("*") if p.is_file() and p.name != _ONTOLOGY_FILENAME
    )


def _ontology_version(path: Path | None) -> str:
    """A stable version tag for the pinned ontology, never invented.

    `ONTOLOGY.md` §Where an ontology lives: "the version of an ontology is its commit"
    once the ontology is its own tracked file — resolving that needs a repo to walk,
    which a corpus's `--data` is not guaranteed to be. A short content hash is the
    honest fallback: it changes exactly when the ontology does, and it never claims a
    git history that may not exist.
    """
    if path is None or not path.is_file():
        return "unversioned"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:12]


def _classify(
    source: Path, ontology: dict[str, Any] | None
) -> tuple[str | None, dict[str, Any], str]:
    """(kind or None, frontmatter, body) for one source, without inventing either.

    Only a markdown source can be classified at all — it is the only format `build()`
    reads without a converter. `kind` is `None` when the source is not markdown, has no
    frontmatter, or its declared kind is not one the ontology names; the caller stamps
    those as the honest `document` residue kind rather than a guess.
    """
    if source.suffix.lower() != ".md":
        return None, {}, ""
    frontmatter, body = _frontmatter.parse(
        source.read_text(encoding="utf-8", errors="replace")
    )
    if not frontmatter or not ontology:
        return None, frontmatter, body
    # The frontmatter field naming a source's kind: the ontology's own declared
    # override, or `kind` absent one — the same default `lib.ontology._kinds` reads,
    # duplicated here as a two-line literal rather than reaching into that module's
    # private helper for it.
    discriminator = str(ontology.get("discriminator") or "kind")
    raw_kind = frontmatter.get(discriminator)
    kinds = ontology.get("kinds") or {}
    if raw_kind and str(raw_kind) in kinds:
        return str(raw_kind), frontmatter, body
    return None, frontmatter, body


def _backup(dest: Path) -> Path | None:
    """A durable backup of `dest`'s current content, taken before any write below.

    Beside `dest`, on the same filesystem as the tree it protects — NOT under a system
    temp directory: a backup in an ephemeral `/tmp` is gone with the next reboot
    (`GRAPH.md` §Disciplines). `None` when there is nothing yet to protect.
    """
    if not dest.exists() or not any(p.name != _LOCK_NAME for p in dest.iterdir()):
        return None
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    archive = dest.parent / f"{dest.name}.backup-{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(dest, arcname=dest.name)
    return archive


class _ExclusiveLock:
    """One writer per tree, enforced rather than requested.

    Parallel writers given overlapping scope clobber each other's files (`GRAPH.md`
    §Disciplines). An `O_CREAT | O_EXCL` lock file makes a second concurrent `build()`
    against the same `dest` refuse immediately instead of racing.
    """

    def __init__(self, dest: Path) -> None:
        self._path = dest / _LOCK_NAME

    def __enter__(self) -> "_ExclusiveLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError(
                f"{self._path}: another build is already writing this tree "
                "(one writer per tree — see GRAPH.md)"
            ) from exc
        os.close(fd)
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._path.unlink(missing_ok=True)


@dataclasses.dataclass(frozen=True)
class _Ontology:
    """The ontology `build()` pins at the graph root, resolved once up front."""

    declared: dict[str, Any] | None
    name: str
    version: str


def _resolve_ontology(data: Path, meta: Path | None) -> _Ontology:
    """The ontology to pin: at `meta` if given, else `data`'s own declared/derived one.

    When none is named, racecar-ontology is called. A `derive()` proposal is
    descriptive only — it names the ontology `check()` could not fit, it is never
    itself adopted as the pin (adopting a schema is the corpus owner's keystroke,
    same terminus `_kinds.derive` already stops at).
    """
    path: Path | None
    if meta and meta.is_file():
        path = meta
    elif meta and meta.is_dir():
        candidate = meta / _ONTOLOGY_FILENAME
        path = candidate if candidate.is_file() else None
    else:
        candidate = data / _ONTOLOGY_FILENAME
        path = candidate if candidate.is_file() else None

    declared = (
        yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if path
        else _kinds.load_ontology(data)
    )
    fit = _kinds.check(data, path.parent if path else data)
    name = fit.best or (declared or {}).get("name") or "unnamed"
    return _Ontology(declared=declared, name=name, version=_ontology_version(path))


def _rendering_body(name: str, source: Path, kind: str | None, body: str) -> str:
    """The rendering's content: the source's own body when classified, else an
    explicit residue note — never invented content for a format with no converter."""
    if kind:
        return body or f"# {name}\n"
    return (
        f"# {name}\n\nNo converter is available for "
        f"`{source.suffix or '(no extension)'}` sources — the original is preserved "
        f"unmodified at `files/{source.name}`. Content was not extracted; "
        "`status: unknown` reflects that honestly rather than guessing a kind for "
        "this node.\n"
    )


def _write_node(
    source: Path,
    data: Path,
    dest: Path,
    ontology: dict[str, Any] | None,
    *,
    seen_paths: dict[str, list[Path]],
    collisions: list[Collision],
) -> dict[str, Any]:
    """Write one source's node (files/ copy + dated rendering); return its manifest row.

    Category directories and their `README.md` are created on first use, not
    pre-declared — a corpus's category set is only known by walking it.
    """
    kind, _frontmatter, body = _classify(source, ontology)
    category = kind or _UNCATEGORIZED
    node_kind = kind or _DOCUMENT_KIND

    name = _slug(source.stem)
    rel_key = f"{category}/{name}"
    prior = seen_paths.setdefault(rel_key, [])
    if prior:
        name = f"{name}-{len(prior) + 1}"
        collisions.append(Collision(path=rel_key, sources=(prior[0], source)))
    prior.append(source)

    cat_dir = dest / category
    files_dir = cat_dir / "files"
    doc_dir = cat_dir / name
    files_dir.mkdir(parents=True, exist_ok=True)
    doc_dir.mkdir(parents=True, exist_ok=True)
    cat_readme = cat_dir / "README.md"
    if not cat_readme.exists():
        cat_readme.write_text(
            f"---\npnode: [../README.md]\n---\n\n# {category}\n", encoding="utf-8"
        )

    shutil.copy2(source, files_dir / source.name)

    refdate = time.strftime("%Y%m%d", time.gmtime(source.stat().st_mtime))
    status = "draft" if kind else "unknown"
    rendering_fm = {
        "pnode": ["../README.md"],
        "kind": node_kind,
        "status": status,
        "source": f"files/{source.name}",
    }
    rendering_path = doc_dir / f"{name}_{refdate}.md"
    rendering_path.write_text(
        "---\n"
        + yaml.safe_dump(rendering_fm, sort_keys=False)
        + "---\n\n"
        + _rendering_body(name, source, kind, body),
        encoding="utf-8",
    )

    return {
        "path": str(source.relative_to(data)),
        "name": name,
        "rendering": str(rendering_path.relative_to(dest)),
        "category": category,
        "refdate": f"{refdate[:4]}-{refdate[4:6]}-{refdate[6:]}",
        "kind": node_kind,
        "status": status,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


def _write_root(dest: Path, ontology: _Ontology) -> None:
    (dest / "README.md").write_text(
        "---\n"
        + yaml.safe_dump(
            {
                "pnode": [],
                "graph": True,
                "ontology": {"name": ontology.name, "version": ontology.version},
            },
            sort_keys=False,
        )
        + "---\n\n# graph\n",
        encoding="utf-8",
    )


def build(data: Path, dest: Path, meta: Path | None = None) -> BuildResult:
    """Restructure `data` into a graph at `dest`, conforming to the ontology at `meta`.

    `meta` is a path to an `ontology.yaml` (or a directory holding one); when it is
    `None`, the corpus-declared ontology at `data`'s own root is used if `check()`
    fits it, else `derive()`'s proposal (see `_resolve_ontology`).
    """
    if not data.is_dir():
        raise NotADirectoryError(f"{data} is not a directory")

    resolved = _resolve_ontology(data, meta)
    dest.mkdir(parents=True, exist_ok=True)

    with _ExclusiveLock(dest):
        backup = _backup(dest)

        sources = _walk_sources(data)
        by_kind: dict[str, int] = {}
        collisions: list[Collision] = []
        seen_paths: dict[str, list[Path]] = {}
        manifest_rows = [
            _write_node(
                source,
                data,
                dest,
                resolved.declared,
                seen_paths=seen_paths,
                collisions=collisions,
            )
            for source in sources
        ]
        for row in manifest_rows:
            by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1

        _write_root(dest, resolved)

        manifest_path = dest / "manifest.jsonl"
        with manifest_path.open("w", encoding="utf-8") as handle:
            for row in manifest_rows:
                handle.write(json.dumps(row, sort_keys=True))
                handle.write("\n")

    total = len(sources)
    unclassified = by_kind.get(_DOCUMENT_KIND, 0)
    unmapped_fraction = 1.0 if total == 0 else unclassified / total

    return BuildResult(
        root=dest,
        manifest=manifest_path,
        sources_in=total,
        sources_indexed=len(manifest_rows),
        unmapped_fraction=unmapped_fraction,
        by_kind=by_kind,
        collisions=tuple(collisions),
        backup=backup,
    )


def run(data: Path, dest: Path, meta: Path | None = None) -> BuildResult:
    """The `build` verb's record: what `build` wrote at `dest`, and how completely.

    Raises `NotADirectoryError` when `data` is not a directory, and `RuntimeError` when
    another build holds `dest`.
    """
    return build(data, dest, meta=meta)


def _show(data: Path, dest: Path, meta: Path | None) -> int:
    """Run the build and print what landed where; 0, or 1 when it could not run."""
    try:
        result = run(data, dest, meta)
    except (NotADirectoryError, RuntimeError) as exc:
        print(text.refusal("build", exc), file=sys.stderr)
        return 1
    print(text.build(result))
    return 0


def main(
    data: Path, dest: Path, meta: Path | None = None, *, as_json: bool = False
) -> int:
    """Build a graph at `dest` from `data`, and report what landed where; under `as_json`
    the text goes to stderr and stdout carries the exit code, the result this verb declares.
    """
    return run_json(as_json, lambda: _show(data, dest, meta))


if __name__ == "__main__":
    not_a_command()
