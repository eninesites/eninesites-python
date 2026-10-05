"""Which lines of a markdown document are fenced code, where nothing is a heading or a link.

A fence opens on a line starting with three or more backticks or tildes, after any
indentation. It closes on a line whose marker is the same character and at least as long,
as CommonMark says: `~~~` does not close a backtick fence, and three backticks do not close
four. A line is code from its opening marker through its closing one inclusive, so a caller
that copies code verbatim gets the fences with it.

  `fenced(lines)`  one flag per line, and the marker of a block left open, or None
  `prose(lines)`   (line number from 1, line) for every line outside a fence

A block that never closes makes everything below it code. `fenced` returns the open marker
so a caller that must not silently lose the rest of a document can say so.

Complexity: O(n) in lines
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence

_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})")


def fenced(lines: Sequence[str]) -> tuple[list[bool], str | None]:
    """Whether each line is fenced code, and the marker of a block that never closed."""
    flags: list[bool] = []
    fence: str | None = None
    for line in lines:
        opener = _FENCE.match(line)
        if fence is not None:
            marker = opener.group(2) if opener else ""
            if marker.startswith(fence[0]) and len(marker) >= len(fence):
                fence = None
            flags.append(True)
        elif opener:
            fence = opener.group(2)
            flags.append(True)
        else:
            flags.append(False)
    return flags, fence


def prose(lines: Sequence[str]) -> Iterator[tuple[int, str]]:
    """(line number from 1, line) for every line outside a fenced code block."""
    flags, _ = fenced(lines)
    for number, (line, code) in enumerate(zip(lines, flags), start=1):
        if not code:
            yield number, line
