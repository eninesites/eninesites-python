"""The aeo views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import InspectAeo


def print_inspect(result: InspectAeo) -> None:
    """``aeo inspect`` as text: per URL, its view and how many JSON-LD nodes it emits."""
    pages = result["results"]
    # The site form answers only `url` and `json_ld`; show a column only when some page has it.
    columns = ["url"]
    if any("view" in page for page in pages):
        columns.append("view")
    if any("page_artifacts" in page for page in pages):
        columns.append("artifacts")
    columns.append("json_ld")
    text.table(
        [
            {
                "url": page.get("url"),
                "view": page.get("view"),
                "artifacts": len(page.get("page_artifacts") or []),
                "json_ld": len(page.get("json_ld") or []),
            }
            for page in pages
        ],
        columns,
    )


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
