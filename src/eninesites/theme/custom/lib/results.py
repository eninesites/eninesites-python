"""The shapes the theme custom api returns: one TypedDict per verb.

The one home of every custom-theme result shape, following
``CustomThemeExportImportView`` (``rest.py:1085-1177``): an export is
``{"custom_theme": {name, parent, templates}}``, ``templates`` mapping a template path to
its source. That export, saved with ``--json``, is exactly what ``import --path``
takes back.
"""

from __future__ import annotations

from typing import TypedDict


class CustomTheme(TypedDict, total=False):
    """A site's custom theme: its name, the theme it extends, and its template sources."""

    name: str
    parent: str | None
    templates: dict[str, str]


class ExportCustom(TypedDict):
    """What ``theme custom export`` returns: the custom theme, ready to import elsewhere."""

    domain: str
    custom_theme: CustomTheme


class ImportCustom(TypedDict):
    """What ``theme custom import`` returns: the custom theme saved and the theme now active."""

    domain: str
    name: str
    theme: str
