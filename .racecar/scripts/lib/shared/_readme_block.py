"""Marker-delimited generated blocks in a repo-root README.

One home for the splice. The CLI-tree block uses this shape --
a begin marker, an end marker, and a rewrite that moves only the bytes between them -- and
`graph.py` needs exactly the same thing for `## Graphs`. Two copies of a
three-branch string splice is two places for the append-when-absent branch to disagree,
which is the P-02 case in miniature.

Generic over the SECTION TEXT rather than over what produced it. `racecar.surface` renders a
command tree and `graph.py` renders a table of graphs; they share how a block is
delimited and replaced, and nothing else. A helper that also knew how to render would have
to grow a case per caller, which is the coupling this avoids.
"""

from __future__ import annotations

from pathlib import Path


def splice(existing: str, begin: str, end: str, section: str) -> str:
    """`existing` with the `begin`..`end` block replaced by `section`, or appended.

    `section` must carry its own markers -- the caller renders them, because the caller is
    what knows the heading and the regenerate hint that sit inside them.

    Idempotent: splicing the result again reproduces it exactly. That property is what
    makes a staleness predicate possible, so it is the one thing worth stating here.

    **A file missing either marker is returned UNCHANGED.** Two rules, and there is no
    third: both markers present, replace what is between them; otherwise do nothing.

    It never appends. An append-when-absent branch cannot tell a first run from a
    damaged one, and the damaged case is the expensive half: delete
    `<!-- END graphs -->` and leave the body, and the old section stays in
    the file as plain text while a second copy lands at the bottom -- two `## Graphs`
    headings, one stale and orphaned, and no duplicate-heading check anywhere in this
    repo to catch it. A generator that never appends cannot reach that state.

    Markers are SEEDED, not grown. An empty pair is what makes a block exist, which is
    how `tests/slow/test_surface_generate.py` builds an adopter README, and creating one
    is a decision a person makes rather than a side effect of a run.
    """
    if begin in existing and end in existing:
        start = existing.index(begin)
        stop = existing.index(end) + len(end)
        return existing[:start] + section + existing[stop:]
    return existing


def is_stale(readme: Path, begin: str, end: str, section: str) -> bool:
    """True when `readme`'s block is missing or disagrees with `section`.

    Compares the whole spliced file rather than the extracted block, so a marker that has
    been damaged or a block that has drifted position both read as stale -- the question a
    `--check` mode is asking is "would `--write` change this file", and that is exactly
    what this computes.
    """
    existing = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    return splice(existing, begin, end, section) != existing
