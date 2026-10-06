"""Terminal text every noun's plaintext renderer shares: a record, a table, a status line.

Nothing about these is noun-specific, so they live once here, beside the JSON renderer. A
noun's ``print_<verb>`` chooses which fields and columns to show and calls these.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


def cell(value: Any) -> str:
    """One value as text: empty for None, compact JSON for a list or object."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def record(result: Mapping[str, Any], keys: Sequence[str] | None = None) -> None:
    """One ``key: value`` line per field, in ``keys`` order when given."""
    names = list(keys) if keys is not None else list(result)
    width = max((len(k) for k in names if k in result), default=0)
    for key in names:
        if key in result:
            print(f"{key.ljust(width)}  {cell(result[key])}")


def table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    """Rows as aligned columns with a header; ``(none)`` when there are no rows."""
    if not rows:
        print("(none)")
        return
    texts = [[cell(row.get(c)) for c in columns] for row in rows]
    widths = [max(len(c), *(len(t[i]) for t in texts)) for i, c in enumerate(columns)]
    print("  ".join(c.upper().ljust(w) for c, w in zip(columns, widths)).rstrip())
    for text in texts:
        print("  ".join(t.ljust(w) for t, w in zip(text, widths)).rstrip())


def line(text: str) -> None:
    """One line of plain text."""
    print(text)


def planned(result: Mapping[str, Any]) -> None:
    """A write verb's dry run: the request it would have sent, and that nothing was sent."""
    query = result.get("query")
    target = result["path"] + (f"?{cell(query)}" if query else "")
    verb = "write" if result["method"] in ("WRITE", "REMOVE") else "send"
    print(f"would {verb}: {result['method']} {target}")
    if result.get("body") is not None:
        print(json.dumps(result["body"], indent=2, ensure_ascii=False))
    if result.get("form"):
        print(f"form: {cell(result['form'])}")
    if result.get("files"):
        print(f"files: {', '.join(result['files'])}")
    print("Dry run: nothing was sent or written.")
