"""The audit views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import GetAudit, RunAudit


def print_run(result: RunAudit) -> None:
    """``audit run`` as text: the stored audit's counts."""
    text.record(result)


def print_get(result: GetAudit) -> None:
    """``audit get`` as text: one row per URL, or that no audit has run."""
    if not result["audited"]:
        text.line(f"No audit has run for {result['domain']}; run `audit run` first.")
        return
    text.table(result["results"], ["url", "total_errors", "total_warnings"])


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
