"""The theme custom views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import ExportCustom, ImportCustom


def print_export(result: ExportCustom) -> None:
    """``theme custom export`` as text: name, parent and template paths (not the sources)."""
    theme = result["custom_theme"]
    text.record({"name": theme.get("name"), "parent": theme.get("parent")})
    for path in sorted(theme.get("templates") or {}):
        text.line(f"  {path}")
    text.line("(use --json to save the templates for `theme custom import --path`)")


def print_import(result: ImportCustom) -> None:
    """``theme custom import`` as text."""
    text.line(
        f"Imported custom theme {result['name']} into {result['domain']} as {result['theme']}"
    )


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
